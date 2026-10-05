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
    """
    Team two interpretation: 
    For this level our goal is to implement the review_contract function, call the ai.ask function, iterate through the response, filter out wrong one and return only the valid ones
    Question: how do we know we need to call the ai.ask function?
    """
    findings = ai.ask("contract_review", spec) #Team2: Call the ai.ask functio
    valid_findings = [] #Team2: initiate a list for the valid responses to return

    #Team2: loop through the returned findings comparing if path exist in the spec, method exit in the spec, evidence_pointer exist in the spec
    for finding in findings:
        path = finding["path"]
        method = finding["method"]
        evidence_pointer = finding["evidence_pointer"]

        print(f"for path: {path}, method: {method}, evidence_pointer: {evidence_pointer}")
        
        # Check 1: Does the path/method exist?
        if path not in spec["paths"] or method not in spec["paths"][path]:
            print(f"path: {path} does not exist")
            continue
        
        # Check 2: Does the evidence_pointer resolve?
        if not resolve_json_pointer(spec, evidence_pointer):
            print(f"evidence_point: {evidence_pointer} does not exist")
            continue
        
        # If both checks pass, keep it
        print(f"finding for path: {path}, method: {method}, evidence_pointer: {evidence_pointer} is valid")
        valid_findings.append(finding)
    print(valid_findings)    
    return valid_findings

def resolve_json_pointer(spec, pointer):
    """Check if a JSON Pointer path exists in spec."""
    if not pointer.startswith("/"):
        return False
    
    keys = pointer[1:].split("/")  # Skip leading "/", then split
    keys = [k.replace("~1", "/") for k in keys]  # Decode ~1 → /
    
    current = spec
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return False
        else:
            return False
    return True


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
    valid_cases = []
    
    for case in cases:
        # Check 1: Required fields present
        if not all(k in case for k in ["name", "method", "path", "input", "expected_status"]):
            continue
        
        # Check 2: Endpoint exists in spec
        path = case["path"]
        method = case["method"].lower()
        if path not in spec["paths"] or method not in spec["paths"][path]:
            continue
        
        # Check 3: expected_status is in the allowlist
        if case["expected_status"] not in [400, 401, 403, 404, 409, 422]:
            continue
        
        valid_cases.append(case)
    
    return valid_cases


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
        # Check if ALL evidence strings appear literally in the logs
        if all(evidence in logs for evidence in candidate["evidence"]):
            return candidate
    
    # No candidate matched
    return {}


def review_migration(v1: dict, v2: dict, ai) -> list[dict]:
    """Level 4 -- return only breaking changes proven by the two contracts.

    ai.ask("migration_review", {...}) returns a list like:
        [
          {
            "id": "BREAK-POST",
            "claim": "POST /orders was removed in v2.",
            "kind": "operation_removed",
            "path": "/orders",
            "method": "post"
          },
          {
            "id": "BREAK-LIMIT",
            "claim": "The limit query parameter became required.",
            "kind": "parameter_became_required",
            "path": "/orders",
            "method": "get",
            "parameter": "limit"
          },
          {
            "id": "BREAK-003",
            "claim": "orderId changed from integer to string.",
            "kind": "schema_changed",
            "path": "/orders/{orderId}",
            "method": "get",
            "parameter": "orderId"
          }
        ]

    Compare each claim against data/openapi-v1.json and data/openapi-v2.json
    (Swagger: http://localhost:8081/api/v1 and http://localhost:8081/api/v2).

    Verify each change by comparing v1 and v2 directly.
      "operation_removed"       -- operation exists in v1 but not in v2.
      "parameter_became_required" -- parameter.required is False in v1
                                     and True in v2.
      "schema_changed"          -- parameter["schema"] differs between v1 and v2.
                                   If the schemas are identical the claim is false.
    """
    findings = ai.ask("migration_review", {"v1": v1, "v2": v2})
    verified = []
    
    for finding in findings:
        kind = finding["kind"]
        path = finding["path"]
        method = finding["method"]
        
        if kind == "operation_removed":
            op_v1 = v1["paths"].get(path, {}).get(method)
            op_v2 = v2["paths"].get(path, {}).get(method)
            if op_v1 is not None and op_v2 is None:
                verified.append(finding)
        
        elif kind == "parameter_became_required":
            param_name = finding["parameter"]
            param_v1 = next((p for p in v1["paths"][path][method].get("parameters", []) 
                           if p["name"] == param_name), None)
            param_v2 = next((p for p in v2["paths"][path][method].get("parameters", []) 
                           if p["name"] == param_name), None)
            if param_v1 and param_v2:
                if not param_v1.get("required", False) and param_v2.get("required", False):
                    verified.append(finding)
        
        elif kind == "schema_changed":
            param_name = finding["parameter"]
            param_v1 = next((p for p in v1["paths"][path][method].get("parameters", []) 
                           if p["name"] == param_name), None)
            param_v2 = next((p for p in v2["paths"][path][method].get("parameters", []) 
                           if p["name"] == param_name), None)
            if param_v1 and param_v2:
                if param_v1.get("schema") != param_v2.get("schema"):
                    verified.append(finding)
    
    return verified
