/* Runs the project's own Python analysis code (analysis/*.py) in the browser
 * via Pyodide, for the static GitHub Pages build. Used only for requests that
 * were not precomputed at build time (custom exclusions, free-text questions…).
 */
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

const FILES = ["py/analysis/load.py", "py/analysis/engine.py", "py/analysis/api.py", "py/data/turnout_2022.csv"];

const ready = (async () => {
  const py = await loadPyodide();
  await py.loadPackage(["numpy", "pandas", "scipy", "statsmodels"]);
  py.FS.mkdirTree("/app/analysis");
  py.FS.mkdirTree("/app/data");
  for (const f of FILES) {
    const txt = await (await fetch(f)).text();
    py.FS.writeFile("/app/" + f.replace(/^py\//, ""), txt);
  }
  const findings = await (await fetch("findings.json")).text();
  py.globals.set("FINDINGS_JSON", findings);
  py.runPython(`
import sys
sys.path.insert(0, "/app/analysis")
import api
api.STATIC = True
api.use_precomputed_findings(FINDINGS_JSON)
`);
  return py;
})();

onmessage = async (e) => {
  const { id, method, path, payload } = e.data;
  try {
    const py = await ready;
    py.globals.set("REQ", JSON.stringify(payload));
    const out = py.runPython(`api.dispatch_json(${JSON.stringify(method)}, ${JSON.stringify(path)}, REQ)`);
    postMessage({ id, ...JSON.parse(out) });
  } catch (err) {
    postMessage({ id, ok: false, error: String(err) });
  }
};
ready.then(() => postMessage({ ready: true })).catch((err) => postMessage({ ready: false, error: String(err) }));
