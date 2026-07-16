"""FastAPI entry point - aisim.api.server:app (see §十三).

Starts the CompanyHub on startup; exposes REST routes + WebSocket.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aisim.api.routes import router as api_router
from aisim.api.state import hub
from aisim.api.ws import ws_router, ws_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    # Inject the WebSocket broadcaster into the Hub so Tick/Agent events can be pushed to the frontend
    hub.on_frontend_event = ws_manager.broadcast
    logger.info("CompanyHub 启动...")
    try:
        await hub.start()
    except Exception:  # noqa: BLE001
        logger.exception("CompanyHub 启动失败 (是否缺少 Redis? 检查 REDIS_HOST/REDIS_PASSWORD)")
    yield
    await hub.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="ai-sim-company Company Hub", version="0.1.0", lifespan=lifespan)
    # Allow the frontend (e.g. localhost:3000/3007) to access REST cross-origin; WS is not subject to CORS.
    # In production this should be changed to specific origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.include_router(ws_router)
    return app


app = create_app()
