from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings
from .errors import AppError, app_error_handler
from .models import LoginRequest
from .security import Sessions, RateLimiter
from .services.callmissed import CallMissed
from .services.voice import DEFAULT_CONNECTOR
from .routes import chat, images, voice


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Buffer only small API requests before parsing so chunked bodies are bounded too.
        if scope["method"] in ("POST", "PUT", "PATCH"):
            body = bytearray()
            while True:
                packet = await receive()
                if packet["type"] == "http.disconnect":
                    return
                body.extend(packet.get("body", b""))
                if len(body) > 200000:
                    return await JSONResponse(
                        {
                            "error": {
                                "code": "body_too_large",
                                "message": "Request is too large.",
                            }
                        },
                        413,
                    )(scope, receive, send)
                if not packet.get("more_body"):
                    break
            consumed = False

            async def replay():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {
                        "type": "http.request",
                        "body": bytes(body),
                        "more_body": False,
                    }
                return await receive()

            return await self.app(scope, replay, send)
        return await self.app(scope, receive, send)


def create_app(settings=None, transport=None, voice_connector=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=20),
            timeout=60,
        ) as client:
            app.state.settings = settings
            app.state.sessions = Sessions(settings)
            app.state.limiter = RateLimiter(settings, client)
            app.state.callmissed = CallMissed(settings, client)
            app.state.voice_connector = voice_connector or DEFAULT_CONNECTOR
            app.state.voice_sessions = set()
            yield

    app = FastAPI(
        title="CallMissed AI Playground",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.app_env == "development" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.app_env == "development" else None,
    )
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_exception_handler(AppError, app_error_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Check your input. Prompts must be nonempty and within the character limit.",
                }
            },
            422,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected server error occurred.",
                }
            },
            500,
        )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "microphone=(self), camera=()"
        response.headers["Cache-Control"] = (
            "no-store" if request.url.path.startswith("/api/") else "no-cache"
        )
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "provider_configured": bool(settings.callmissed_api_key.get_secret_value()),
        }

    @app.get("/api/session")
    async def session(request: Request):
        authorized = False
        try:
            request.app.state.sessions.verify(request.cookies.get("playground_session"))
            authorized = True
        except AppError:
            pass
        return {
            "authorized": authorized,
            "access_code_required": bool(settings.demo_access_code.get_secret_value()),
            "provider_configured": bool(settings.callmissed_api_key.get_secret_value()),
            "models": {
                "chat": settings.chat_model,
                "image": settings.image_model,
                "voice": settings.voice_llm_model,
            },
            "voice_max_seconds": settings.voice_max_seconds,
        }

    @app.post("/api/session")
    async def login(body: LoginRequest, request: Request):
        state = request.app.state
        state.sessions.check_origin(request.headers.get("origin"))
        await state.limiter.hit(
            request.client.host if request.client else "unknown", "login", 10, 60
        )
        token = state.sessions.login(body.access_code)
        response = JSONResponse({"authorized": True})
        response.set_cookie(
            "playground_session",
            token,
            max_age=28800,
            httponly=True,
            secure=settings.app_env == "production",
            samesite="lax",
            path="/",
        )
        return response

    @app.delete("/api/session")
    async def logout(request: Request):
        request.app.state.sessions.check_origin(request.headers.get("origin"))
        response = JSONResponse({"authorized": False})
        response.delete_cookie("playground_session", path="/")
        return response

    for router in (chat.router, images.router, voice.router):
        app.include_router(router, prefix="/api")

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        async def frontend(path: str):
            if path.startswith("api/"):
                return JSONResponse(
                    {"error": {"code": "not_found", "message": "Endpoint not found."}},
                    404,
                )
            allowed = {"pcm-capture.js", "favicon.svg"}
            return FileResponse(dist / path if path in allowed else dist / "index.html")

    return app


app = create_app()
