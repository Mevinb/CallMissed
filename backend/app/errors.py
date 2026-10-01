from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        {"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status
    )


def upstream_error(status: int):
    errors = {
        400: (
            422,
            "provider_rejected",
            "CallMissed rejected this request. Try a different prompt or configuration.",
        ),
        401: (
            503,
            "provider_auth",
            "CallMissed authentication failed. Ask the app owner to check the server API key.",
        ),
        402: (
            503,
            "credits_exhausted",
            "The CallMissed account has insufficient credits. Ask the app owner to top up.",
        ),
        403: (
            503,
            "provider_permission",
            "This API key or plan cannot use the selected service. Ask the app owner to check permissions.",
        ),
        404: (
            503,
            "model_unavailable",
            "The configured CallMissed model is unavailable. Ask the app owner to update it.",
        ),
        429: (
            429,
            "provider_limit",
            "CallMissed is at its rate or quota limit. Wait a moment before trying again.",
        ),
    }
    return AppError(
        *errors.get(
            status,
            (
                502,
                "provider_unavailable",
                "CallMissed is unavailable right now. Please try again later.",
            ),
        )
    )
