from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.protocol import decode_response_from_stream, encode_request  # noqa: E402


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--image", required=True)
    parser.add_argument("--task_id", required=True)
    parser.add_argument("--encoding", default="jpg")
    args = parser.parse_args()

    image_bytes = Path(args.image).read_bytes()
    header = {
        "task_id": args.task_id,
        "image_encoding": args.encoding,
        "image_len": len(image_bytes),
        "barcode": args.task_id,
    }
    reader, writer = await asyncio.open_connection(args.host, args.port)
    writer.write(encode_request(header, image_bytes))
    await writer.drain()
    response = await decode_response_from_stream(reader)
    writer.close()
    await writer.wait_closed()
    print(f"parcel_count={response.get('parcel_count')} processing_time_ms={response.get('processing_time_ms')}")


if __name__ == "__main__":
    asyncio.run(main_async())
