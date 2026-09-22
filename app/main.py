import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import engine
from app.routers import admin, auth, content, inmet, users, weather

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_production()
    yield


app = FastAPI(
    title="PrevClima API",
    version="0.1.0",
    description="API do prototipo conectado de avisos meteorologicos severos.",
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
            "/api/v1/auth/login-mobile",
            "/api/v1/auth/login-professional",
            "/api/v1/auth/register",
        }
    ):
        cookie_token = request.cookies.get("prevclima_csrf", "")
        header_token = request.headers.get("X-CSRF-Token", "")
        if not cookie_token or not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(status_code=403, content={"detail": "Token CSRF inválido"})

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


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    translations = {
        "missing": "Campo obrigatório",
        "string_too_short": "Texto menor que o permitido",
        "string_too_long": "Texto maior que o permitido",
        "literal_error": "Valor inválido",
        "greater_than": "Valor abaixo do limite permitido",
        "less_than_equal": "Valor acima do limite permitido",
    }
    errors = []
    for error in exc.errors():
        message = translations.get(error["type"], error["msg"])
        if error["type"] == "value_error":
            message = str(error.get("ctx", {}).get("error", message))
        errors.append({"loc": error["loc"], "msg": message, "type": error["type"]})
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException):
    translated = {
        "Not Found": "Recurso não encontrado",
        "Method Not Allowed": "Método não permitido",
    }.get(exc.detail, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": translated})


@app.get("/api/health", tags=["operações"])
def health():
    return {"status": "ok"}


@app.get("/api/ready", tags=["operações"])
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "indisponível"})
    return {"status": "pronto"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(weather.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(inmet.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")

public_dir = Path(__file__).resolve().parent.parent / "public"
app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")
