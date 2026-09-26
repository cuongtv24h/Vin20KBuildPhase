"""Điểm khởi động sidecar: `python -m src.pricing_sidecar --socket-path ...`."""

import argparse
import asyncio

from src.pricing_sidecar.server import serve

DEFAULT_SOCKET_PATH = "./data/pricing.sock"


def main() -> None:
    parser = argparse.ArgumentParser(description="PricePolicy Deterministic Math Engine (C-06)")
    parser.add_argument("--socket-path", default=DEFAULT_SOCKET_PATH, help="Đường dẫn Unix Domain Socket")
    args = parser.parse_args()
    asyncio.run(serve(args.socket_path))


if __name__ == "__main__":
    main()
