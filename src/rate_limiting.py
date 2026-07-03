from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .templates import templates


limiter = Limiter(key_func=get_remote_address)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    messages = {
        "/shorten": "You can create at most 20 URLs per hour.",
        "/admin-stats": "You can view stats at most 60 times per hour.",
    }

    return templates.TemplateResponse(
        "rate_limit.html",
        {
            "request": request,
            "message": messages.get(request.url.path, "Too many requests."),
        },
        status_code=429,
    )
