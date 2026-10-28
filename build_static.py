"""Build the static site for GitHub Pages into docs/.

    python build_static.py

Copies web/, precomputes every default-view API response with the real
engine (so the hosted site loads instantly), and ships the Python analysis
code + CSV so anything not precomputed runs in the browser via Pyodide.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "analysis"))

import api  # noqa: E402
import engine  # noqa: E402

DOCS = ROOT / "docs"
# Must match SUGGESTED in web/app.js
SUGGESTED = [
    "What is the most surprising thing in this data?",
    "Which things go along with higher or lower turnout?",
    "What should I look into next?",
]


def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    shutil.copytree(ROOT / "web", DOCS)
    (DOCS / "config.js").write_text("window.TURNOUT_STATIC = true;\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    for f in ["load.py", "engine.py", "api.py"]:
        (DOCS / "py" / "analysis").mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "analysis" / f, DOCS / "py" / "analysis" / f)
    (DOCS / "py" / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "data" / "turnout_2022.csv", DOCS / "py" / "data" / "turnout_2022.csv")

    api.STATIC = True
    pre = {}

    def add(method, path, payload):
        pre[api.request_key(path, payload)] = api.dispatch(method, path, payload)

    for p in ["/api/meta", "/api/overview", "/api/findings", "/api/data", "/api/ai_status"]:
        add("GET", p, {})
    for m in ["spearman", "pearson"]:
        add("GET", "/api/matrix", {"method": m})
    for g in engine.GROUPS:
        for o in engine.OUTCOMES:
            add("GET", "/api/group", {"group": g, "y": o})
    numeric = engine.OUTCOMES + [p for p in engine.PREDICTORS if p not in ("is_south", "alt_num")] + ["vep"]
    for x in numeric:
        for y in numeric:
            if x != y:
                add("GET", "/api/correlate", {"x": x, "y": y})
    F = engine.findings()
    for focal in {f["focal"] for f in F}:
        add("GET", "/api/spec", {"focal": focal})
    for a in engine.DF.index:
        add("GET", "/api/profile", {"abv": a})
    for f in F:
        for t in f["tests"] + [x[1] for x in f["alternatives"] if x[1]]:
            add("POST", "/api/test", {"finding": f["id"], "test": t, "exclude": []})
        if f["chart"]["kind"] == "residuals":
            add("POST", "/api/regress", {"y": f["chart"]["y"], "terms": f["chart"]["terms"], "exclude": []})
    for q in SUGGESTED:
        for o in engine.OUTCOMES:
            add("POST", "/api/ask", {"question": q, "exclude": [], "outcome": o, "use_ai": False})

    (DOCS / "precomputed.json").write_text(json.dumps(pre, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    (DOCS / "findings.json").write_text(json.dumps(F, allow_nan=False), encoding="utf-8")
    size = (DOCS / "precomputed.json").stat().st_size / 1e6
    print(f"Built docs/ with {len(pre)} precomputed responses ({size:.1f} MB)")


if __name__ == "__main__":
    main()
