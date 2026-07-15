"""FastAPI 入口 - aisim.api.server:app (见 §十三)。

启动时拉起 CompanyHub; 暴露 REST 路由 + WebSocket。
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
    # 把 WebSocket 广播器注入 Hub，使 Tick/Agent 事件能推到前端
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
    # 允许前端 (如 localhost:3000/3007) 跨域访问 REST; WS 不受 CORS 限制。
    # 生产环境应改成具体 origin。
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
