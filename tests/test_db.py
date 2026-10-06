from pathlib import Path

from sqlalchemy import create_engine, text


DATABASE_URL = "sqlite:///./src/dev_db/dev_db.sqlite"


def test_local_database_connection():
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar()

    assert result == 1
    assert Path("./src/dev_db/dev_db.sqlite").exists()