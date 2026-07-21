"""FastAPI app entrypoint. Owns CORS and end-to-end request timing at the
boundary (time.perf_counter(), per CLAUDE.md — measured here, not inside
the pipeline). No database, no auth, no session state: POST /analyze is
the only endpoint; the whole pipeline runs within one request.
"""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from utils.config import load_config

config = load_config()
logging.basicConfig(level=config.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="Loom", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def time_request(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info("%s %s completed in %.2fs", request.method, request.url.path, elapsed)
    response.headers["X-Process-Time"] = f"{elapsed:.3f}"
    return response


app.include_router(router)
