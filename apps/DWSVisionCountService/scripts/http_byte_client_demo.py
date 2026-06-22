from __future__ import annotations

import argparse
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080/api/v1/parcel/count_bytes")
    parser.add_argument("--image", required=True)
    parser.add_argument("--task_id", required=True)
    parser.add_argument("--encoding", default="jpg")
    args = parser.parse_args()

    image_bytes = Path(args.image).read_bytes()
    response = requests.post(
        args.url,
        params={"task_id": args.task_id, "image_encoding": args.encoding},
        data=image_bytes,
        headers={"Content-Type": "application/octet-stream"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    print(f"parcel_count={data.get('parcel_count')} processing_time_ms={data.get('processing_time_ms')}")


if __name__ == "__main__":
    main()
