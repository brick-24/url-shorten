from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
import random
import string
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import os
from dotenv import load_dotenv

load_dotenv()

from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
templates = Jinja2Templates(directory="src/templates")

# tables
class URLMap(Base):
    __tablename__ = "url_map"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, nullable=False)
    short_code = Column(String, unique=True, index=True, nullable=False)
    admin_key = Column(String, unique=True, index=True, nullable=False)


class ClickLog(Base):
    __tablename__ = "click_log"

    id = Column(Integer, primary_key=True, index=True)
    url_map_id = Column(Integer, index=True)
    ip_address = Column(String, nullable=False)
    user_agent = Column(String)
    referer = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)

# db functions
def log_click(db: Session, url_map_id: int, ip_address: str, user_agent: str, referer: str):
    click = ClickLog(
        url_map_id=url_map_id,
        ip_address=ip_address,
        user_agent=user_agent,
        referer=referer,
        timestamp=datetime.utcnow(),
    )

    db.add(click)
    db.commit()


def get_click_logs(db: Session, url_map_id: int):
    return db.query(ClickLog).filter(
        ClickLog.url_map_id == url_map_id
    ).order_by(ClickLog.timestamp.desc()).all()


def get_click_stats(db: Session, url_map_id: int):
    total = db.query(ClickLog).filter(ClickLog.url_map_id == url_map_id).count()

    ips = db.query(ClickLog.ip_address).filter(
        ClickLog.url_map_id == url_map_id
    ).distinct().all()

    unique_ips = len([row[0] for row in ips])

    first = db.query(ClickLog.timestamp).filter(
        ClickLog.url_map_id == url_map_id
    ).order_by(ClickLog.timestamp.asc()).first()

    last = db.query(ClickLog.timestamp).filter(
        ClickLog.url_map_id == url_map_id
    ).order_by(ClickLog.timestamp.desc()).first()

    return {
        "total": total,
        "unique_ips": unique_ips,
        "first_seen": first[0] if first else None,
        "last_seen": last[0] if last else None,
    }


def get_url_by_key(db: Session, key: str):
    return db.query(URLMap).filter(URLMap.short_code == key).first()

app = FastAPI()
init_db()
app.mount("/static", StaticFiles(directory="src/static"), name="static")


class URLRequest(BaseModel):
    url: str


@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/health")
def health():
    return {"status": "ok"}

length = 5
@app.post("/shorten", response_class=HTMLResponse)
def shorten(request: Request, url: str = Form(...), db: Session = Depends(get_db)):

    key = "".join(random.choices(string.ascii_letters + string.digits, k=length))
    admin_key = "".join(random.choices(string.ascii_letters + string.digits, k=length * 2))

    record = URLMap(
        original_url=url,
        short_code=key,
        admin_key=admin_key
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    short_url = f"http://localhost:8000/{key}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "short_url": short_url,
            "short_code": key,
            "original_url": record.original_url,
            "admin_key": admin_key
        }
    )


@app.get("/{key}")
def open_short_url(key: str, request: Request, db: Session = Depends(get_db)):
    record = get_url_by_key(db, key)

    if not record:
        raise HTTPException(status_code=404, detail="Short URL not found")

    xfwd = request.headers.get("X-Forwarded-For")

    ip = xfwd.split(",")[0].strip() if xfwd else (
        request.client.host if request.client else "0.0.0.0"
    )

    user_agent = request.headers.get("user-agent")
    referer = request.headers.get("Referer")

    try:
        log_click(db, record.id, ip, user_agent, referer)
    except:
        pass

    return RedirectResponse(url=record.original_url, status_code=307)


@app.post("/admin-stats", response_class=HTMLResponse)
def admin_stats_form(
    request: Request,
    short_code: str = Form(...),
    admin_key: str = Form(...),
    db: Session = Depends(get_db)
):

    record = db.query(URLMap).filter(URLMap.short_code == short_code).first()

    if not record or record.admin_key != admin_key:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "Invalid short code or admin key"
            }
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
            "original_url": record.original_url
        }
    )