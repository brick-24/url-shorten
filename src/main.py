from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import SECRET_KEY, STATIC_DIR
from .database import init_db
from .rate_limiting import limiter, rate_limit_handler
from .routes import router


app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.include_router(router)


@app.on_event("startup")
def startup():
    try:
        init_db()
    except Exception as exc:
        print("Database init failed:", exc)
