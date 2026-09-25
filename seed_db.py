import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db import Base, Incident
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def seed():
    async with AsyncSessionLocal() as session:
        new_incident = Incident(
            container_name="nginx-proxy",
            image_hash="sha256:abcd1234efgh5678",
            logs_context="[emerg] 1#1: bind() to 0.0.0.0:80 failed (98: Address already in use)",
            env_snapshot='{"PORT":"80", "NGINX_HOST":"example.com"}',
            root_cause="Port 80 is already bound by another process on the host, causing Nginx to crash on startup.",
            suggested_fix="docker compose stop && docker compose up -d nginx-proxy",
            ai_latency_ms=1450
        )
        session.add(new_incident)
        await session.commit()
        print("Seeded database with dummy incident.")

if __name__ == "__main__":
    asyncio.run(seed())
