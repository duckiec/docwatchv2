import pytest
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db import Base, Incident, save_incident, get_recent_incidents, get_incident_by_id
import app.db as app_db

# Override the database for tests to use an in-memory SQLite database
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
)
app_db.engine = test_engine
app_db.AsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest.fixture(autouse=True, scope="function")
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_incident_lifecycle():
    # Test Create
    new_incident = Incident(
        container_name="test-db-container",
        image_hash="sha256:dummy",
        logs_context="test log",
        env_snapshot='{"ENV":"TEST"}',
        root_cause="Out of memory",
        suggested_fix="docker restart test-db-container",
        ai_latency_ms=120
    )

    saved = await save_incident(new_incident)
    assert saved.id is not None
    assert saved.container_name == "test-db-container"

    # Test Read by ID
    fetched = await get_incident_by_id(saved.id)
    assert fetched is not None
    assert fetched.root_cause == "Out of memory"

    # Test Read Recent
    recent = await get_recent_incidents(limit=1)
    assert len(recent) > 0
    assert recent[0].container_name == "test-db-container"
