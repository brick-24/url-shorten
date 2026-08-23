from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String

from .database import Base


class URLMap(Base):
    __tablename__ = "url_map"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, nullable=False)
    short_code = Column(String, unique=True, index=True, nullable=False)
    admin_key = Column(String, unique=True, index=True, nullable=False)
    owner_id = Column(String, index=True, nullable=False)
    owner_login = Column(String, index=True, nullable=False)


class ClickLog(Base):
    __tablename__ = "click_log"

    id = Column(Integer, primary_key=True, index=True)
    url_map_id = Column(Integer, index=True)
    ip_address = Column(String, nullable=False)
    user_agent = Column(String)
    referer = Column(String)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
