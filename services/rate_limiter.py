from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')


def get_identifier(request: Request) -> str:
    """
    Get identifier for rate limiting.
    Uses user ID if authenticated, otherwise falls back to IP address.
    """
    # Check if user is authenticated (from JWT middleware)
    if hasattr(request.state, 'user') and request.state.user:
        return f"user:{request.state.user.get('id', get_remote_address(request))}"

    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Create limiter with Redis storage
limiter = Limiter(
    key_func=get_identifier,
    storage_uri=REDIS_URL,
    strategy="fixed-window"
)


ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://mogetajob.vercel.app",
]


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded errors with CORS headers"""
    origin = request.headers.get("origin", "")

    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }

    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": exc.detail
        },
        headers=headers
    )
