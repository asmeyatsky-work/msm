"""Mock Vertex endpoint for staging.

Returns a constant prediction so scoring-api's /v1/score returns 200
before a real Vertex AI model is registered. Replace with a real
endpoint secret value once the ml-pipeline train job has run.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class H(BaseHTTPRequestHandler):
    def _json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        _ = self.rfile.read(length)
        if self.path.endswith(":explain"):
            self._json(200, {
                "explanations": [{"attributions": [{
                    "baselineOutputValue": 2.5,
                    "featureAttributions": {
                        "cerberus_score": 0.5,
                        "rpc_7d": 0.3,
                        "rpc_14d": 0.2,
                        "rpc_30d": 0.1,
                    },
                }]}]
            })
            return
        # Default: prediction path (:predict or similar)
        self._json(200, {"predictions": [2.5]})

    def log_message(self, *args, **kwargs):  # silence default log noise
        return


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"mock-vertex listening on 0.0.0.0:{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
