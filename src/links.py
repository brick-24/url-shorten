import random
import string

from sqlalchemy.orm import Session

from .config import SHORT_CODE_LENGTH
from .models import ClickLog, URLMap


def generate_code(length: int = SHORT_CODE_LENGTH):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def create_url_map(db: Session, original_url: str, owner: dict):
    record = URLMap(
        original_url=original_url,
        short_code=generate_code(),
        admin_key=generate_code(SHORT_CODE_LENGTH * 2),
        owner_id=owner["id"],
        owner_login=owner["login"],
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def log_click(db: Session, url_map_id: int, ip_address: str, user_agent: str, referer: str):
    click = ClickLog(
        url_map_id=url_map_id,
        ip_address=ip_address,
        user_agent=user_agent,
        referer=referer,
    )

    db.add(click)
    db.commit()


def get_click_logs(db: Session, url_map_id: int):
    return (
        db.query(ClickLog)
        .filter(ClickLog.url_map_id == url_map_id)
        .order_by(ClickLog.timestamp.desc())
        .all()
    )


def get_click_stats(db: Session, url_map_id: int):
    total = db.query(ClickLog).filter(ClickLog.url_map_id == url_map_id).count()

    ips = db.query(ClickLog.ip_address).filter(ClickLog.url_map_id == url_map_id).distinct().all()
    unique_ips = len([row[0] for row in ips])

    first = (
        db.query(ClickLog.timestamp)
        .filter(ClickLog.url_map_id == url_map_id)
        .order_by(ClickLog.timestamp.asc())
        .first()
    )
    last = (
        db.query(ClickLog.timestamp)
        .filter(ClickLog.url_map_id == url_map_id)
        .order_by(ClickLog.timestamp.desc())
        .first()
    )

    return {
        "total": total,
        "unique_ips": unique_ips,
        "first_seen": first[0] if first else None,
        "last_seen": last[0] if last else None,
    }


def get_url_by_key(db: Session, key: str):
    return db.query(URLMap).filter(URLMap.short_code == key).first()


def get_user_links(db: Session, owner_id: str):
    return db.query(URLMap).filter(URLMap.owner_id == owner_id).all()
