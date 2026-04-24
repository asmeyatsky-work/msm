"""Fake Vertex + metadata server used by the E2E compose stack."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8090


class H(BaseHTTPRequestHandler):
    def _send_json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/token"):
            self._send_json(200, {"access_token": "fake", "expires_in": 3600})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        self.rfile.read(length)
        if self.path.startswith("/explain"):
            self._send_json(200, {
                "explanations": [{"attributions": [{
                    "baselineOutputValue": 1.0,
                    "featureAttributions": {"rpc_7d": 0.3, "rpc_14d": 0.2}
                }]}]
            })
        else:
            self._send_json(200, {"predictions": [2.5]})

    def log_message(self, *a, **k): pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
