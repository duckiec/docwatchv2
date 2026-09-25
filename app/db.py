from typing import Optional
from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, DateTime, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from app.config import settings

Base = declarative_base()

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    container_name = Column(String(255), index=True, nullable=False)
    image_hash = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    logs_context = Column(Text, nullable=True)
    env_snapshot = Column(Text, nullable=True)  # JSON string
    
    # AI Classification
    root_cause = Column(Text, nullable=True)
    suggested_fix = Column(Text, nullable=True)
    ai_latency_ms = Column(Integer, nullable=True)

# Remove the sqlite+aiosqlite:// prefix if user just passed a raw path, but in config we default to sqlite+aiosqlite:////data/docwatch.db
# We inject pragmas to enable WAL mode for vastly improved concurrent performance with SQLite
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}, # needed for SQLite
)

from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-20000")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_recent_incidents(limit: int = 50):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Incident).order_by(Incident.timestamp.desc()).limit(limit)
        )
        return result.scalars().all()

async def get_incident_by_id(incident_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        return result.scalars().first()

async def save_incident(incident: Incident):
    async with AsyncSessionLocal() as session:
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident
