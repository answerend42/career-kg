from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .api.recommend import RecommendationService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Career KG recommendation service")
    parser.add_argument("--serve", action="store_true", help="start a local HTTP server")
    parser.add_argument("--host", default="127.0.0.1", help="server host")
    parser.add_argument("--port", type=int, default=8080, help="server port")
    parser.add_argument("--input-file", type=Path, help="JSON request file for one-off inference")
    return parser


def load_payload(input_file: Path | None) -> dict[str, Any]:
    if input_file:
        return json.loads(input_file.read_text(encoding="utf-8"))
    sample_path = Path(__file__).resolve().parents[2] / "data" / "demo" / "sample_request.json"
    return json.loads(sample_path.read_text(encoding="utf-8"))


def serve(host: str, port: int) -> None:
    service = RecommendationService()

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json({"status": "ok"})
                return
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/recommend":
                self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except (ValueError, json.JSONDecodeError):
                self._send_json({"error": "invalid json payload"}, status=HTTPStatus.BAD_REQUEST)
                return
            if not isinstance(payload, dict):
                self._send_json({"error": "request body must be a JSON object"}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(service.recommend(payload))

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"serving on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.serve:
        serve(args.host, args.port)
        return

    service = RecommendationService()
    payload = load_payload(args.input_file)
    print(json.dumps(service.recommend(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
