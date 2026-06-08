from __future__ import annotations

import asyncio
import struct

from app.protocol import (
    decode_request_from_stream,
    decode_response_from_stream,
    encode_request,
    encode_response,
)
from app.config import Config
from app.schemas import CountResult
from app.tcp_server import TCPServer
from app.utils.errors import HeaderParseError, ImageByteLengthMismatchError


def _reader(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


async def _decode_request(data: bytes):
    return await decode_request_from_stream(_reader(data))


async def _decode_response(data: bytes):
    return await decode_response_from_stream(_reader(data))


def test_encode_decode_request_roundtrip():
    image_bytes = b"abc"
    packet = encode_request({"task_id": "t1", "image_encoding": "jpg"}, image_bytes)
    meta, payload = asyncio.run(_decode_request(packet))
    assert meta.task_id == "t1"
    assert meta.image_len == 3
    assert payload == image_bytes


def test_header_length_error():
    packet = struct.pack(">I", 70 * 1024)
    try:
        asyncio.run(_decode_request(packet))
    except HeaderParseError:
        return
    raise AssertionError("HeaderParseError not raised")


def test_image_len_not_enough():
    packet = encode_request({"task_id": "t1", "image_encoding": "raw_bgr", "image_len": 5}, b"abc")
    try:
        asyncio.run(_decode_request(packet))
    except ImageByteLengthMismatchError:
        return
    raise AssertionError("ImageByteLengthMismatchError not raised")


def test_encode_decode_response_roundtrip():
    packet = encode_response({"code": 0, "parcel_count": 1})
    data = asyncio.run(_decode_response(packet))
    assert data["parcel_count"] == 1


async def _exercise_tcp_result_callback():
    config = Config()
    config.service.host = "127.0.0.1"
    config.service.tcp_port = 0
    results = []
    server = TCPServer(
        config,
        result_callback=lambda result: results.append(result.to_dict()),
    )
    server.counter.load = lambda: None
    server.counter.count_bytes = lambda meta, data: CountResult(
        task_id=meta.task_id,
        code=0,
        message="ok",
        parcel_count=1,
        processing_time_ms=77,
    )

    await server.start()
    port = server.server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    image_bytes = b"jpeg"
    writer.write(
        encode_request(
            {
                "task_id": "T1",
                "image_encoding": "jpg",
                "image_len": len(image_bytes),
            },
            image_bytes,
        )
    )
    await writer.drain()
    response = await decode_response_from_stream(reader)
    writer.close()
    await writer.wait_closed()
    await server.stop()
    return response, results


def test_tcp_server_reports_result_to_callback():
    response, results = asyncio.run(_exercise_tcp_result_callback())

    assert response["parcel_count"] == 1
    assert len(results) == 1
    assert results[0]["task_id"] == "T1"
    assert results[0]["processing_time_ms"] == 77


async def _exercise_failing_result_callback():
    config = Config()
    config.service.host = "127.0.0.1"
    config.service.tcp_port = 0

    def failing_callback(_result):
        raise RuntimeError("ui callback failed")

    server = TCPServer(config, result_callback=failing_callback)
    server.counter.load = lambda: None
    server.counter.count_bytes = lambda meta, data: CountResult(
        task_id=meta.task_id,
        code=0,
        message="ok",
        parcel_count=1,
    )
    await server.start()
    port = server.server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        encode_request(
            {"task_id": "T2", "image_encoding": "jpg", "image_len": 4},
            b"jpeg",
        )
    )
    await writer.drain()
    response = await decode_response_from_stream(reader)
    writer.close()
    await writer.wait_closed()
    await server.stop()
    return response


def test_result_callback_failure_does_not_break_dws_response():
    response = asyncio.run(_exercise_failing_result_callback())

    assert response["code"] == 0
    assert response["parcel_count"] == 1
