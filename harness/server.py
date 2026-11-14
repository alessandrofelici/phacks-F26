"""Web UI for Repro Bot. Standard library only.

    python -m harness.server [--port 8000]

Then open http://localhost:8000. Listens on localhost only.
"""
from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import runs
from .common import list_tasks, run_dir
from .score import load_key

STATIC = Path(__file__).resolve().parent / "static"
RUN_PATH = re.compile(r"^/api/runs/([a-z0-9][a-z0-9-]*)$")
STOP_PATH = re.compile(r"^/api/runs/([a-z0-9][a-z0-9-]*)/stop$")
APPROVAL_PATH = re.compile(r"^/api/runs/([a-z0-9][a-z0-9-]*)/approvals/([a-z0-9-]+)$")
LOG_PATH = re.compile(r"^/api/runs/([a-z0-9][a-z0-9-]*)/file$")


class Handler(BaseHTTPRequestHandler):
    server_version = "ReproBotHarness/1"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def _error(self, code: int, message: str) -> None:
        self._json({"error": message}, code)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 100_000:
            return {}
        try:
            data = json.loads(self.rfile.read(length))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/tasks":
            tasks = []
            for t in list_tasks():
                tasks.append({"task_id": t["task_id"], "title": t["title"], "source": t["source"],
                              "paper_url": t.get("paper_url"), "instructions": t.get("instructions"),
                              "questions": t["questions"], "limits": t.get("limits"),
                              "has_answer_key": load_key(t["task_id"]) is not None})
            return self._json({"tasks": tasks, "real_agent_available": runs.real_agent_available()})
        if url.path == "/api/runs":
            return self._json({"runs": runs.list_runs()})
        if url.path == "/api/batches":
            return self._json({"batches": runs.list_batches(), "running": runs.batch_running()})
        m = RUN_PATH.match(url.path)
        if m:
            since = int((parse_qs(url.query).get("since") or ["0"])[0] or 0)
            detail = runs.run_detail(m.group(1), since)
            return self._json(detail) if detail else self._error(404, "unknown run")
        m = LOG_PATH.match(url.path)
        if m:
            return self._run_file(m.group(1), (parse_qs(url.query).get("path") or [""])[0])
        return self._error(404, "not found")

    def _run_file(self, run_id: str, rel: str) -> None:
        """Serve a text file from inside a run directory (evidence and logs)."""
        rdir = run_dir(run_id)
        if rdir is None or not rdir.is_dir() or not rel:
            return self._error(404, "not found")
        target = (rdir / rel).resolve()
        if rdir.resolve() not in target.parents or not target.is_file() or ".harness" in target.parts:
            return self._error(404, "not found")
        self._send(200, target.read_bytes()[:200_000], "text/plain; charset=utf-8")

    def do_POST(self):
        url = urlparse(self.path)
        body = self._body()
        try:
            if url.path == "/api/runs":
                run_id = runs.start_run(str(body.get("task_id", "")), str(body.get("agent", "real")),
                                        bool(body.get("auto_approve", False)))
                return self._json({"run_id": run_id}, 201)
            if url.path == "/api/batches":
                runs.start_batch(str(body.get("agent", "real")))
                return self._json({"ok": True}, 201)
            m = STOP_PATH.match(url.path)
            if m:
                return self._json({"stopped": runs.stop_run(m.group(1))})
            m = APPROVAL_PATH.match(url.path)
            if m:
                runs.decide(m.group(1), m.group(2), str(body.get("decision", "")), str(body.get("note", ""))[:500])
                return self._json({"ok": True})
        except ValueError as exc:
            return self._error(400, str(exc))
        return self._error(404, "not found")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repro Bot web UI.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Repro Bot harness: http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
