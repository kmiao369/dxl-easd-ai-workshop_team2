"""Participant file -- improve these working-but-unreliable baselines.

Quick start
-----------
1. Run  python demo.py          to see the raw AI output for all four levels.
2. Edit the functions below one at a time.
3. Run  python score.py --team "Your Team" --open   to see your score and a
   visual report in the browser.

The API being reviewed has three endpoints (see http://localhost:8081/api/v1):

    GET  /orders               list orders, optional ?limit=<int>
    POST /orders               create an order  (Bearer auth required)
    GET  /orders/{orderId}     fetch one order  (Bearer auth required)

The AI assistant (ai.ask(...)) always returns a list of dicts. The shapes are
shown in the comments below. Your job is to filter that list so only items
that are verifiable against real evidence survive.
"""

def is_valid_finding(finding: dict, spec: dict) -> bool:
        """Check if finding is supported by the spec."""
        path = finding.get("path")
        method = finding.get("method")
        evidence_pointer = finding.get("evidence_pointer")

        # Check 1: Does the endpoint exist?
        if path not in spec.get("paths", {}):
            return False
        if method not in spec["paths"][path]:
            return False

        # Check 2: Does the evidence pointer resolve?
        found, _ = resolve_json_pointer(spec, evidence_pointer)
        return found

def review_contract(spec: dict, ai) -> list[dict]:
    """Level 1 -- return only findings supported by the OpenAPI contract.

    ai.ask("contract_review", spec) returns a list like:
        [
          {
            "id": "AUTH-001",
            "claim": "GET /orders has no authentication requirement.",
            "path": "/orders",
            "method": "get",
            "evidence_pointer": "/paths/~1orders/get"
          },
          ...
          {
            "id": "SEC-001",
            "claim": "DELETE /customers is publicly accessible.",
            "path": "/customers",
            "method": "delete",
            "evidence_pointer": "/paths/~1customers/delete"
          }
        ]

    Compare each finding against the OpenAPI v1 document in
    data/openapi-v1.json (same spec as http://localhost:8081/api/v1).

    Tip: check two things for each finding before keeping it.
      1. Does spec["paths"][finding["path"]][finding["method"]] exist?
      2. Does the evidence_pointer resolve to a real location inside spec?
         JSON Pointer: split on "/" first, then decode ~1 to "/" inside a key.
         "/paths/~1orders/get" is spec["paths"]["/orders"]["get"].
         It is not "//orders" -- the slash belongs to the key name "/orders".
    """
    def resolve_json_pointer(obj: dict, pointer: str) -> tuple[bool, any]:
        """
        Resolve a JSON Pointer and return (found, value).
        JSON Pointer: split on "/", decode ~1 to "/" in keys.
        Example: "/paths/~1orders/get" → spec["paths"]["/orders"]["get"]
        """
        if not pointer.startswith("/"):
            return False, None

        parts = pointer[1:].split("/")  # Skip leading "/" then split
        current = obj

        for part in parts:
            # Decode ~1 to / and ~0 to ~
            part = part.replace("~1", "/").replace("~0", "~")

            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return False
            else:
                return False

        return True, current

    def is_valid_finding(finding: dict, spec: dict) -> bool:
        """Check if finding is supported by the spec."""
        path = finding.get("path")
        method = finding.get("method")
        evidence_pointer = finding.get("evidence_pointer")

        # Check 1: Does the endpoint exist?
        if path not in spec.get("paths", {}):
            return False
        if method not in spec["paths"][path]:
            return False

        # Check 2: Does the evidence pointer resolve?
        found, _ = resolve_json_pointer(spec, evidence_pointer)
        return found

    # Get AI findings
    findings = ai.ask("contract_review", spec)

    # Filter to only valid findings
    return [f for f in findings if is_valid_finding(f, spec)]


def design_negative_tests(spec: dict, ai) -> list[dict]:
    """Level 2 -- return runnable test ideas for operations that really exist.

    ai.ask("negative_tests", spec) returns a list like:
        [
          {
            "name": "zero limit",
            "method": "get",
            "path": "/orders",
            "input": {"limit": 0},
            "expected_status": 400
          },
          ...
          {
            "name": "delete customer record",
            "method": "delete",
            "path": "/customers/c-1",
            "input": {},
            "expected_status": 204
          }
        ]

    Compare each test case against the OpenAPI v1 document in
    data/openapi-v1.json (same spec as http://localhost:8081/api/v1).

    Tip: keep a test case only if ALL of these are true.
      1. spec["paths"][case["path"]][case["method"]] exists.
      2. expected_status is one of 400, 401, 403, 404, 409, or 422.
         A 204 from a non-existent endpoint is a red flag.
      3. The case has all required fields: name, method, path, input,
         expected_status.
    """
    cases = ai.ask("negative_tests", spec)

    filtered = []
    for case in cases:
        # Check all required fields exist
        if not all(k in case for k in ["name", "method", "path", "input", "expected_status"]):
            continue

        # Check path and method exist in spec
        if case["path"] not in spec["paths"]:
            continue
        if case["method"] not in spec["paths"][case["path"]]:
            continue

        # Check expected_status is in the allowed list
        if case["expected_status"] not in [400, 401, 403, 404, 409, 422]:
            continue

        filtered.append(case)

    return filtered


def diagnose_incident(logs: str, ai) -> dict:
    """Level 3 -- select a diagnosis whose evidence appears in the logs.

    ai.ask("incident_diagnosis", logs) returns a list of candidates:
        [
          {
            "cause": "A DNS outage prevented all clients from reaching the API.",
            "evidence": ["dns_resolution_failed", "upstream_host_not_found"]
          },
          {
            "cause": "The 2.4.1 database-pool change exhausted connections.",
            "evidence": [
              "deploy version=2.4.1 change=orders-db-pool",
              "db_pool_wait_ms=1850 active=20 max=20",
              "status=503 error=db_pool_timeout"
            ]
          }
        ]

    Tip: only keep a candidate if every string in its "evidence" list
    appears literally somewhere inside the logs string.
    The log file is at  data/incident.log  -- open it to see what is there.
    """
    candidates = ai.ask("incident_diagnosis", logs)

    for candidate in candidates:
        # Check if every evidence string appears in the logs
        if all(evidence in logs for evidence in candidate["evidence"]):
            return candidate

    # No valid diagnosis found
    return None

#     return ai.ask("incident_diagnosis", logs)[0]   # [0] is unverified; fix it

def review_migration(v1: dict, v2: dict, ai) -> list[dict]:
    findings = ai.ask("migration_review", {"v1": v1, "v2": v2})

    verified = []
    for finding in findings:
        if finding["kind"] == "operation_removed":
            # Check operation exists in v1 but not in v2
            v1_op = v1["paths"].get(finding["path"], {}).get(finding["method"])
            v2_op = v2["paths"].get(finding["path"], {}).get(finding["method"])
            if v1_op and not v2_op:
                verified.append(finding)

        elif finding["kind"] == "parameter_became_required":
            # Check required changed False → True
            v1_param = next((p for p in v1["paths"][finding["path"]][finding["method"]].get("parameters", [])
                           if p["name"] == finding["parameter"]), None)
            v2_param = next((p for p in v2["paths"][finding["path"]][finding["method"]].get("parameters", [])
                           if p["name"] == finding["parameter"]), None)
            if v1_param and v2_param:
                if not v1_param.get("required", False) and v2_param.get("required", False):
                    verified.append(finding)

        elif finding["kind"] == "schema_changed":
            # Extract parameter schema from v1
            v1_params = v1["paths"][finding["path"]][finding["method"]].get("parameters", [])
            v1_param = next((p for p in v1_params if p["name"] == finding["parameter"]), None)
            v1_schema = v1_param.get("schema", {}) if v1_param else None

            # Extract parameter schema from v2
            v2_params = v2["paths"][finding["path"]][finding["method"]].get("parameters", [])
            v2_param = next((p for p in v2_params if p["name"] == finding["parameter"]), None)
            v2_schema = v2_param.get("schema", {}) if v2_param else None

            # Compare schemas
            # Check schemas actually differ
            if v1_schema and v2_schema and v1_schema != v2_schema:
                verified.append(finding)

#             v1_schema = # extract parameter schema from v1
#             v2_schema = # extract parameter schema from v2
#             if v1_schema != v2_schema:
#                 verified.append(finding)

    return verified