import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .security import install_log_redaction

log = logging.getLogger("ckh")


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_log_redaction()
    init_db()
    task = None
    if get_settings().enable_scheduler:
        from .jobs import scheduler_loop
        task = asyncio.create_task(scheduler_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="Creator Knowledge Hub", version="0.1.0", lifespan=lifespan)

from .routers import api  # noqa: E402

app.include_router(api.router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception):  # safe error message: no internals leaked
    log.exception("unhandled error")
    return JSONResponse({"detail": "Internal error"}, status_code=500)


_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = (_dist / path).resolve()
        if path and f.is_file() and _dist in f.parents:  # no path traversal outside dist
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
