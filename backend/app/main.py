from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import (
    calendar,
    dashboard,
    files,
    health,
    inbox,
    meta,
    notifications,
    projects,
    settings,
    stats,
    sync,
    tasks,
    team,
    workflow,
)
from .db import init_db
from .services.scheduler import shutdown_scheduler, start_scheduler


def configure_logging() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    handler = RotatingFileHandler(
        config.LOG_DIR / "workbench.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), handler],
        force=True,
    )


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("workbench db ready: %s", config.DB_PATH)
    if os.environ.get("WORKBENCH_NO_SCHEDULER") != "1":
        start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="任务管理工作台",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8787",
        "http://localhost:8787",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health.router,
    meta.router,
    dashboard.router,
    tasks.router,
    tasks.board_router,
    projects.router,
    inbox.router,
    calendar.router,
    team.router,
    stats.router,
    files.router,
    notifications.router,
    settings.router,
    sync.router,
    workflow.router,
):
    app.include_router(router, prefix="/api")


def _load_private_extension() -> None:
    """Load an optional extension from backend/app/private/ (gitignored)."""
    try:
        from .private import register_private
    except ImportError:
        return
    except Exception:  # noqa: BLE001
        logger.exception("failed to import private extension")
        return
    try:
        register_private(app)
        logger.info("private extension loaded")
    except Exception:  # noqa: BLE001
        logger.exception("failed to register private extension")


_load_private_extension()


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


if config.WEB_DIST.exists():
    assets = config.WEB_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = config.WEB_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(config.WEB_DIST / "index.html")


@app.get("/")
def root():
    if config.WEB_DIST.exists():
        return FileResponse(config.WEB_DIST / "index.html")
    return {
        "service": "任务管理工作台",
        "status": "backend only",
        "docs": "/docs",
        "hint": "前端开发时运行 pnpm --dir web dev",
    }
