import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.api.dependencies import ClientIdError, client_id_error_handler
from app.core.config import (
    APP_NAME,
    APP_VERSION,
    CLEANUP_INTERVAL_SECONDS,
    CORS_ORIGINS,
    DEBUG,
    ENABLE_CLEANUP_TASK,
)
from app.core.paths import FRONTEND_DIST_DIR
from app.db import init_db
from app.services.cleanup import run_cleanup
from app.utils.time import utc_now_naive


logger = logging.getLogger(__name__)


async def _cleanup_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(run_cleanup, utc_now_naive())
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Background cleanup failed")

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cleanup_task = None

    if ENABLE_CLEANUP_TASK:
        cleanup_task = asyncio.create_task(_cleanup_loop())

    try:
        yield
    finally:
        if cleanup_task is not None:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    debug=DEBUG,
    lifespan=lifespan,
)
app.add_exception_handler(ClientIdError, client_id_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# check_dir=False lets the API start before the frontend has been built.
app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIST_DIR), check_dir=False),
    name="static",
)
app.include_router(api_router)
