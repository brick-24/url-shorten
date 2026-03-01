from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import random
import string
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base


DATABASE_URL = "sqlite:///./src/dev_db/shortener.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


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

def log_click(url_map_id: int, ip_address: str, user_agent: str, referer: str):
    db = SessionLocal()
    try:
        click = ClickLog(
            url_map_id=url_map_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer,
            timestamp=datetime.utcnow(),
        )
        db.add(click)
        db.commit()
    finally:
        db.close()


def get_click_logs(url_map_id: int):
    db = SessionLocal()
    try:
        return db.query(ClickLog).filter(
            ClickLog.url_map_id == url_map_id
        ).order_by(ClickLog.timestamp.desc()).all()
    finally:
        db.close()


def get_click_stats(url_map_id: int):
    db = SessionLocal()
    try:
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
    finally:
        db.close()

def get_url_by_key(key: str):
    db = SessionLocal()
    try:
        return db.query(URLMap).filter(URLMap.short_code == key).first()
    finally:
        db.close()

################
app = FastAPI()
init_db()


class URLRequest(BaseModel):
    url: str


@app.get("/health")
def home():
    return {"status": "ok"}


length = 5


@app.post("/shorten")
def shorten(data: URLRequest):
    db = SessionLocal()
    try:
        key = "".join(random.choices(string.ascii_letters + string.digits, k=length))
        admin_key = "".join(random.choices(string.ascii_letters + string.digits, k=length * 2))

        record = URLMap(
            original_url=data.url,
            short_code=key,
            admin_key=admin_key
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return {
            "short_url": f"http://localhost:8000/{key}",
            "short_code": key,
            "admin_key": admin_key,
            "original_url": record.original_url,
        }

    finally:
        db.close()


@app.get("/{key}")
def open_short_url(key: str, request: Request):
    record = get_url_by_key(key)

    if not record:
        raise HTTPException(status_code=404, detail="Short URL not found")

    xfwd = request.headers.get("X-Forwarded-For")
    ip = xfwd.split(",")[0].strip() if xfwd else (
        request.client.host if request.client else "0.0.0.0"
    )

    user_agent = request.headers.get("user-agent")
    referer = request.headers.get("Referer")

    try:
        log_click(record.id, ip, user_agent, referer)
    except:
        pass

    return RedirectResponse(url=record.original_url, status_code=307)


@app.get("/admin/{short_code}/stats")
def admin_stats(short_code: str, admin_key: str, include_ips: bool = False):
    db = SessionLocal()
    try:
        record = db.query(URLMap).filter(URLMap.short_code == short_code).first()
        if not record:
            raise HTTPException(status_code=404, detail="Short URL not found")
        if record.admin_key != admin_key:
            raise HTTPException(status_code=403, detail="Forbidden")

        stats = get_click_stats(record.id)
        logs = get_click_logs(record.id)

        ips = None
        if include_ips:
            ips = sorted(list({log.ip_address for log in logs}))

        return {
            "short_code": short_code,
            "original_url": record.original_url,
            "total_clicks": stats.get("total"),
            "unique_ips": stats.get("unique_ips"),
            "first_seen": stats.get("first_seen"),
            "last_seen": stats.get("last_seen"),
            "ips": ips,
            "logs": [
                {
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat(),
                    "user_agent": log.user_agent,
                    "referer": log.referer,
                }
                for log in logs
            ],
        }
    finally:
        db.close()