"""HTTP byte 调试服务。"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import FastAPI, Header, Query, Request

from app.config import Config
from app.schemas import ImageMeta
from app.vision.counter import ParcelCounter


def create_app(config: Config, counter: ParcelCounter | None = None) -> FastAPI:
    """创建 FastAPI app。"""
    counter = counter or ParcelCounter(config)
    counter.load()
    app = FastAPI(title=config.service.name, version=config.service.version)

    @app.get("/health")
    async def health():
        return counter.health()

    @app.post("/api/v1/parcel/count_bytes")
    async def count_bytes(
        request: Request,
        task_id: Annotated[str, Query()],
        image_encoding: Annotated[str, Query()] = "encoded",
        width: Annotated[int | None, Query()] = None,
        height: Annotated[int | None, Query()] = None,
        channels: Annotated[int | None, Query()] = None,
        pixel_format: Annotated[str | None, Query()] = None,
        barcode: Annotated[str | None, Query()] = None,
    ):
        image_bytes = await request.body()
        meta = ImageMeta(
            task_id=task_id,
            barcode=barcode,
            image_encoding=image_encoding,
            image_len=len(image_bytes),
            width=width,
            height=height,
            channels=channels,
            pixel_format=pixel_format,
        )
        return counter.count_bytes(meta, image_bytes).to_dict()

    @app.post("/api/v1/parcel/count_json_header")
    async def count_json_header(
        request: Request,
        x_dws_meta: Annotated[str, Header(alias="X-DWS-Meta")],
    ):
        image_bytes = await request.body()
        header = json.loads(x_dws_meta)
        header["image_len"] = len(image_bytes)
        meta = ImageMeta(**header)
        return counter.count_bytes(meta, image_bytes).to_dict()

    @app.get("/api/v1/config")
    async def get_config():
        return {
            "service": config.service.__dict__,
            "model": config.model.__dict__,
            "preprocess": config.preprocess.__dict__,
            "postprocess": config.postprocess.__dict__,
        }

    return app


class HTTPServer:
    """兼容旧 main 的 HTTPServer 包装。"""

    def __init__(self, config: Config):
        self.config = config
        self.counter = ParcelCounter(config)
        self.app = create_app(config, self.counter)

    def run(self, host: str | None = None, port: int | None = None) -> None:
        import uvicorn

        uvicorn.run(
            self.app,
            host=host or self.config.service.host,
            port=port or self.config.service.http_port,
        )
