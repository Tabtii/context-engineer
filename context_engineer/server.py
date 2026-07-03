"""ConText HTTP API Server (MCP-kompatibel).

Endpoints:
    POST /query   — {"question": "..."} → {"text": "...", "sources": [...]}
    GET  /stats   — DB stats
    POST /build   — {"path": "..."} → {"files": N, "chunks": M}
    GET  /health  — {"status": "ok"}
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from context_engineer import ConText


class ConTextHandler(BaseHTTPRequestHandler):
    engine: ConText  # set by run_server

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "version": "0.1.0"})
        elif self.path == "/stats":
            self._send_json(200, self.engine.stats())
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/query":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)
                question = data.get("question")
                if not question:
                    self._send_json(400, {"error": "missing 'question'"})
                    return
                top_k = int(data.get("top_k", 20))
                temperature = float(data.get("temperature", 0.3))
                answer = self.engine.query(
                    question, top_k=top_k, temperature=temperature
                )
                self._send_json(200, {
                    "text": answer.text,
                    "sources": [s.to_dict() for s in answer.sources],
                    "tokens": {
                        "prompt": answer.prompt_tokens,
                        "completion": answer.completion_tokens,
                    },
                    "latency_ms": answer.latency_ms,
                })
            except Exception as e:
                self._send_json(500, {"error": str(e)})
        elif self.path == "/build":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)
                path = data.get("path")
                if not path:
                    self._send_json(400, {"error": "missing 'path'"})
                    return
                stats = self.engine.build(path)
                self._send_json(200, stats)
            except Exception as e:
                self._send_json(500, {"error": str(e)})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass  # Quiet


def run_server(engine: ConText, host: str = "127.0.0.1", port: int = 8765):
    ConTextHandler.engine = engine
    server = HTTPServer((host, port), ConTextHandler)
    server.serve_forever()


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else ".context/store.db"
    run_server(ConText(db_path=db))
