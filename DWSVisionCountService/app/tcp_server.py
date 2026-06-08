"""TCP byte 生产服务。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from loguru import logger

from app.config import Config
from app.protocol import decode_request_from_stream, encode_response
from app.schemas import CountResult
from app.utils.errors import HeaderParseError, VisionServiceError
from app.vision.counter import ParcelCounter


class TCPServer:
    """支持长连接串行请求的 TCP 服务。"""

    def __init__(
        self,
        config: Config,
        result_callback: Callable[[CountResult], None] | None = None,
    ):
        self.config = config
        self.counter = ParcelCounter(config)
        self.server: asyncio.Server | None = None
        self.result_callback = result_callback

    async def start(self, host: str | None = None, port: int | None = None) -> None:
        self.counter.load()
        self.server = await asyncio.start_server(
            self._handle_client,
            host or self.config.service.host,
            port or self.config.service.tcp_port,
        )
        addr = self.server.sockets[0].getsockname() if self.server.sockets else ""
        logger.info("TCP server listening on {}", addr)

    async def serve_forever(self) -> None:
        if self.server is None:
            await self.start()
        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        logger.info("client connected: {}", peer)
        while True:
            try:
                meta, image_bytes = await asyncio.wait_for(
                    decode_request_from_stream(
                        reader,
                        max_image_bytes=self.config.service.max_image_bytes,
                    ),
                    timeout=self.config.service.request_timeout_ms / 1000,
                )
                result = await asyncio.to_thread(self.counter.count_bytes, meta, image_bytes)
                writer.write(encode_response(result.to_dict()))
                await writer.drain()
                self._notify_result(result)
            except asyncio.IncompleteReadError:
                break
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                break
            except HeaderParseError as exc:
                if "incomplete request header" in exc.message:
                    break
                result = CountResult(
                    task_id="",
                    code=exc.code,
                    message=exc.message,
                    model="yolo26n-seg-openvino",
                )
                try:
                    writer.write(encode_response(result.to_dict()))
                    await writer.drain()
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                    break
            except VisionServiceError as exc:
                result = CountResult(
                    task_id="",
                    code=exc.code,
                    message=exc.message,
                    model="yolo26n-seg-openvino",
                )
                try:
                    writer.write(encode_response(result.to_dict()))
                    await writer.drain()
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                    break
            except Exception as exc:
                logger.exception("client request failed: {}", exc)
                result = CountResult(
                    task_id="",
                    code=5000,
                    message=str(exc),
                    model="yolo26n-seg-openvino",
                )
                try:
                    writer.write(encode_response(result.to_dict()))
                    await writer.drain()
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                    break
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        logger.info("client disconnected: {}", peer)

    def _notify_result(self, result: CountResult) -> None:
        if self.result_callback is None:
            return
        try:
            self.result_callback(result)
        except Exception as exc:
            logger.exception("result callback failed: {}", exc)


async def run_tcp_server(config: Config) -> TCPServer:
    server = TCPServer(config)
    await server.start()
    return server
