"""DWSVisionCountService 启动入口。"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from loguru import logger

from app.config import Config
from app.logger import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DWSVisionCountService")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--mode", choices=["tcp", "http", "both"], default=None)
    parser.add_argument("--serve-tcp", action="store_true", help="兼容旧参数")
    parser.add_argument("--serve-http", action="store_true", help="兼容旧参数")
    return parser.parse_args()


async def run_tcp(config: Config) -> None:
    from app.tcp_server import TCPServer

    server = TCPServer(config)
    await server.serve_forever()


def run_http(config: Config) -> None:
    from app.http_server import HTTPServer

    HTTPServer(config).run()


async def run_both(config: Config) -> None:
    import uvicorn
    from app.http_server import create_app
    from app.tcp_server import TCPServer

    tcp = TCPServer(config)
    await tcp.start()
    app = create_app(config)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.service.host,
            port=config.service.http_port,
            log_level="info",
        )
    )
    await server.serve()


def _resolve_config(path: str) -> Config:
    config_path = Path(path)
    if not config_path.exists() and Path("config.yaml").exists():
        config_path = Path("config.yaml")
    return Config.from_yaml(config_path)


def main() -> None:
    args = parse_args()
    config = _resolve_config(args.config)
    setup_logging(config)
    mode = args.mode
    if args.serve_tcp:
        mode = "tcp"
    if args.serve_http:
        mode = "http"
    mode = mode or "tcp"
    logger.info("starting {} in {} mode", config.service.name, mode)
    if mode == "http":
        run_http(config)
    elif mode == "both":
        asyncio.run(run_both(config))
    else:
        asyncio.run(run_tcp(config))


if __name__ == "__main__":
    main()
