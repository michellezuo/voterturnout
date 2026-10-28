"""API routes shared by the local server (server.py) and the in-browser
Python runtime used on the static GitHub Pages build (web/worker.js).
"""
from __future__ import annotations

import json

import engine

try:  # the AI layer needs a server-side key, so it is absent in the browser
    import ai
except Exception:  # noqa: BLE001
    ai = None

STATIC = False  # set to True by the browser worker


def _excl(p):
    v = p.get("exclude", "")
    if isinstance(v, list):
        return v
    return [s for s in v.split(",") if s]


def ai_status():
    if STATIC or ai is None:
        return dict(available=False, reason="AI interpretation needs a private server holding an API key, so it is off on the hosted version. Run the site locally to use it.")
    return ai.status()


GET = {
    "/api/overview": lambda p: engine.overview(),
    "/api/data": lambda p: engine.records(_excl(p)),
    "/api/findings": lambda p: engine.findings(),
    "/api/correlate": lambda p: engine.clean(engine.correlate(p["x"], p.get("y", "turnout_rate_vep"), _excl(p))),
    "/api/matrix": lambda p: engine.clean(engine.corr_matrix(p.get("method", "spearman"), _excl(p))),
    "/api/group": lambda p: engine.clean(engine.group_compare(p.get("group", "region"), p.get("y", "turnout_rate_vep"), _excl(p))),
    "/api/spec": lambda p: engine.clean(engine.spec_curve(p["focal"], "turnout_rate_vep", _excl(p))),
    "/api/profile": lambda p: engine.clean(engine.state_profile(p["abv"], _excl(p))),
    "/api/screen": lambda p: engine.clean(engine.predictor_screen(p.get("y", "turnout_rate_vep"), _excl(p))),
    "/api/ai_status": lambda p: ai_status(),
    "/api/meta": lambda p: engine.clean(dict(vars=engine.VARS, plain=engine.PLAIN, groups=engine.GROUPS, predictors=engine.PREDICTORS,
                                             outcomes=engine.OUTCOMES, control_pool=engine.CONTROL_POOL, tests=engine.TESTS,
                                             collinear={k: sorted(v) for k, v in engine.COLLINEAR.items()})),
}


def _ask(b):
    res = engine.ask(b["question"], b.get("exclude"), b.get("outcome"))
    if b.get("use_ai") and not STATIC and ai is not None:
        res["ai"] = ai.interpret(b["question"], res)
    return res


POST = {
    "/api/regress": lambda b: engine.clean(engine.regression(b.get("y", "turnout_rate_vep"), b.get("terms", []), b.get("exclude"))),
    "/api/selection": lambda b: engine.selection_compare(b.get("selected", []), b.get("y", "turnout_rate_vep"), b.get("exclude")),
    "/api/test": lambda b: engine.run_test(b["finding"], b["test"], b.get("exclude")),
    "/api/ask": _ask,
}


def dispatch(method: str, path: str, payload: dict):
    table = GET if method == "GET" else POST
    if path not in table:
        raise KeyError(f"unknown route {method} {path}")
    return table[path](payload)


def dispatch_json(method: str, path: str, payload_json: str) -> str:
    """Entry point for the browser worker: JSON in, JSON out."""
    try:
        return json.dumps({"ok": True, "data": dispatch(method, path, json.loads(payload_json))}, allow_nan=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})


def request_key(path: str, payload: dict) -> str:
    """Canonical key for precomputed responses; mirrored in web/app.js (reqKey)."""
    clean = {k: v for k, v in payload.items() if v is not None and v != ""}
    return path + "|" + json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def use_precomputed_findings(findings_json: str):
    """Skip the slow findings pipeline in the browser by reusing the build-time result."""
    data = json.loads(findings_json)
    engine.findings = lambda: data
