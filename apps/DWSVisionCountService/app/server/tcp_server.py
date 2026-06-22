"""兼容需求目录结构的 TCP 服务模块。"""

from app.tcp_server import TCPServer, run_tcp_server

__all__ = ["TCPServer", "run_tcp_server"]
