"""兼容需求目录结构的协议模块。"""

from app.protocol import (
    decode_request_from_stream,
    decode_response_from_stream,
    encode_request,
    encode_response,
)

__all__ = [
    "encode_request",
    "decode_request_from_stream",
    "encode_response",
    "decode_response_from_stream",
]
