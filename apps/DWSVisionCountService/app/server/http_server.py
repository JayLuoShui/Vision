"""兼容需求目录结构的 HTTP 服务模块。"""

from app.http_server import HTTPServer, create_app

__all__ = ["HTTPServer", "create_app"]
