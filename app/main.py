"""
Application entrypoint. Wires routers, startup/shutdown hooks, and a global
exception handler so every error response (including ones FastAPI raises
itself, e.g. 422 validation) uses the {data, error} envelope.
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.patients import router as patients_router
from app.api.vapi_webhook import router as vapi_router
from app.config import settings
from app.database import init_db
from app.logging_config import configure_logging

configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("app_startup", environment=settings.ENVIRONMENT)
    yield
    log.info("app_shutdown")


app = FastAPI(
    title="Voice AI Patient Registration",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(patients_router)
app.include_router(vapi_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"data": None, "error": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"data": None, "error": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"data": None, "error": "Internal server error"},
    )


@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}
