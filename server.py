"""Local server for the 2022 turnout explorer.

    python server.py            # http://localhost:8050
    python server.py --port 9000

Uses only the Python standard library for HTTP; routes live in
analysis/api.py and the statistics in analysis/engine.py.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "analysis"))

import api  # noqa: E402
import engine  # noqa: E402

WEB = ROOT / "web"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, allow_nan=False).encode())

    def _err(self, e):
        traceback.print_exc()
        self._json({"error": f"{type(e).__name__}: {e}"}, 400)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in api.GET:
            try:
                return self._json(api.dispatch("GET", u.path, {k: v[0] for k, v in parse_qs(u.query).items()}))
            except Exception as e:  # noqa: BLE001
                return self._err(e)
        rel = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
        f = (WEB / rel).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        self._send(200, f.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text") or ctype.endswith("javascript") else ""))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path not in api.POST:
            return self._send(404, b"not found", "text/plain")
        try:
            n = int(self.headers.get("Content-Length", 0))
            return self._json(api.dispatch("POST", u.path, json.loads(self.rfile.read(n) or b"{}")))
        except Exception as e:  # noqa: BLE001
            return self._err(e)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8050)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    print("Computing findings from data/turnout_2022.csv ...", flush=True)
    engine.findings()
    print(f"Turnout explorer running at http://{a.host}:{a.port}  (AI: {api.ai_status()})", flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
