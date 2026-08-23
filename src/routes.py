from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .auth import oauth, require_login
from .config import GOOGLE_CALLBACK_URL, PUBLIC_SHORT_URL_BASE
from .database import get_db, get_public_db
from .links import (
    create_url_map,
    get_click_logs,
    get_click_stats,
    get_url_by_key,
    get_user_links,
    log_click,
)
from .models import URLMap
from .rate_limiting import limiter
from .templates import templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    if not require_login(request):
        return templates.TemplateResponse("login.html", {"request": request})

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": request.session.get("user"),
        },
    )


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/login")
async def login(request: Request):
    redirect_uri = str(request.url_for("github_callback")).replace("http://", "https://")
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/auth/github/callback")
async def github_callback(request: Request):
    token = await oauth.github.authorize_access_token(request)

    resp = await oauth.github.get("user", token=token)
    profile = resp.json()

    request.session["user"] = {
        "id": str(profile["id"]),
        "login": profile["login"],
        "avatar": profile["avatar_url"],
        "provider": "github",
    }

    return RedirectResponse("/")


@router.get("/login/google")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, GOOGLE_CALLBACK_URL)


@router.get("/auth/google/callback")
async def google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    profile = token.get("userinfo")

    if profile is None:
        resp = await oauth.google.get("userinfo", token=token)
        profile = resp.json()

    request.session["user"] = {
        "id": f"google:{profile['sub']}",
        "login": profile.get("email"),
        "avatar": profile.get("picture"),
        "provider": "google",
    }

    return RedirectResponse("/")


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


@router.post("/shorten", response_class=HTMLResponse)
@limiter.limit("20/hour")
def shorten(request: Request, url: str = Form(...), db: Session = Depends(get_db)):
    record = create_url_map(db, url, request.session["user"])
    short_url = f"{PUBLIC_SHORT_URL_BASE}/{record.short_code}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "short_url": short_url,
            "short_code": record.short_code,
            "original_url": record.original_url,
            "admin_key": record.admin_key,
        },
    )


@router.get("/my-links", response_class=HTMLResponse)
def my_links(request: Request, db: Session = Depends(get_db)):
    if "user" not in request.session:
        return templates.TemplateResponse("login.html", {"request": request})

    user = request.session["user"]
    links = get_user_links(db, user["id"])

    return templates.TemplateResponse(
        "my_links.html",
        {
            "request": request,
            "links": links,
            "user": user,
        },
    )


@router.get("/{key}")
def open_short_url(key: str, request: Request, db: Session = Depends(get_public_db)):
    record = get_url_by_key(db, key)

    if not record:
        raise HTTPException(status_code=404, detail="Short URL not found")

    xfwd = request.headers.get("X-Forwarded-For")
    ip = xfwd.split(",")[0].strip() if xfwd else (request.client.host if request.client else "0.0.0.0")

    user_agent = request.headers.get("user-agent")
    referer = request.headers.get("Referer")

    try:
        log_click(db, record.id, ip, user_agent, referer)
    except Exception:
        pass

    return RedirectResponse(url=record.original_url, status_code=307)


@router.post("/admin-stats", response_class=HTMLResponse)
@limiter.limit("60/hour")
def admin_stats_form(
    request: Request,
    short_code: str = Form(...),
    admin_key: str = Form(...),
    db: Session = Depends(get_db),
):
    if not require_login(request):
        return templates.TemplateResponse("login.html", {"request": request})

    record = db.query(URLMap).filter(URLMap.short_code == short_code).first()

    if not record or record.admin_key != admin_key:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "Invalid short code or admin key",
            },
        )

    stats = get_click_stats(db, record.id)
    logs = get_click_logs(db, record.id)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "logs": logs,
            "stats_url": short_code,
            "original_url": record.original_url,
        },
    )
