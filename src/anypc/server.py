"""FastAPI application: receive image + text prompt, relay over ZeroMQ IPC."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile

from .config import Settings
from .ipc import InferenceClient, InferenceTimeout


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Reads Settings from the environment if not given."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = InferenceClient(settings.ipc_endpoint, settings.ipc_timeout_ms)
        client.connect()
        app.state.client = client
        try:
            yield
        finally:
            client.close()

    app = FastAPI(title="anypc inference gateway", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "ipc_endpoint": settings.ipc_endpoint}

    @app.post("/infer")
    async def infer(
        request: Request,
        prompt: str = Form(...),
        image: UploadFile = File(...),
    ):
        data = await image.read()
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"image exceeds max of {settings.max_upload_bytes} bytes",
            )

        metadata = {
            "prompt": prompt,
            "filename": image.filename,
            "content_type": image.content_type,
            "size": len(data),
        }

        client: InferenceClient = request.app.state.client
        try:
            return await client.request(metadata, data)
        except InferenceTimeout as exc:
            raise HTTPException(status_code=504, detail=str(exc))

    return app
