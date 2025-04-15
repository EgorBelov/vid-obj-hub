# src/database/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from decouple import config


DB_URL = config('DATABASE_URL')

engine = create_async_engine(DB_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db(Base):
    """
    Создание таблиц при первом запуске (если их нет).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
