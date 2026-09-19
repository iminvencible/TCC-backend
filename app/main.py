import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import engine
from app.routers import admin, auth, content, users, weather

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_production()
    yield


app = FastAPI(
    title="PrevClima API",
    version="0.1.0",
    description="API for the connected severe-weather prototype.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if (
        request.url.path.startswith("/api/")
        and request.method in {"POST", "PATCH", "PUT", "DELETE"}
        and request.cookies.get("prevclima_access")
        and request.url.path
        not in {
            "/api/v1/auth/login",
            "/api/v1/auth/login-professional",
            "/api/v1/auth/register",
        }
    ):
        cookie_token = request.cookies.get("prevclima_csrf", "")
        header_token = request.headers.get("X-CSRF-Token", "")
        if not cookie_token or not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "font-src 'self'; img-src 'self' data: https:; "
        "script-src 'self' https://unpkg.com; connect-src 'self'"
    )
    return response


@app.get("/api/health", tags=["operations"])
def health():
    return {"status": "ok"}


@app.get("/api/ready", tags=["operations"])
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(weather.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")

public_dir = Path(__file__).resolve().parent.parent / "public"
app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")
