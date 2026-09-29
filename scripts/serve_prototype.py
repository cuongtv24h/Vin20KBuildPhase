#!/usr/bin/env python3
"""Serve các prototype UI tĩnh (frontend/prototype/) để xem trên máy local.

Dùng:
    python scripts/serve_prototype.py            # http://localhost:4173
    python scripts/serve_prototype.py --port 5000
"""

import argparse
import http.server
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "prototype")
DEFAULT_FILE = "sales_workspace.html"  # SCR-S00; copilot: /sales_copilot.html


class PrototypeHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.abspath(ROOT), **kwargs)

    def do_GET(self):  # noqa: N802 - chuẩn thư viện
        if self.path == "/":
            self.path = "/" + DEFAULT_FILE
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve UI prototypes")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()

    server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), PrototypeHandler)
    print(f"Prototype server: http://localhost:{args.port}/ ({DEFAULT_FILE})")
    server.serve_forever()


if __name__ == "__main__":
    main()
