# db_service/crud.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import models, schemas

async def get_video(session: AsyncSession, video_id: int):
    result = await session.execute(select(models.Video).where(models.Video.id == video_id))
    return result.scalars().first()

async def create_video(session: AsyncSession, video: schemas.VideoCreate):
    db_video = models.Video(**video.dict())
    session.add(db_video)
    await session.commit()
    await session.refresh(db_video)
    return db_video

async def list_videos(session: AsyncSession, skip: int = 0, limit: int = 100):
    result = await session.execute(select(models.Video).offset(skip).limit(limit))
    return result.scalars().all()

async def get_video_objects(session: AsyncSession, video_id: int):
    result = await session.execute(select(models.VideoObject).where(models.VideoObject.video_id == video_id))
    return result.scalars().all()

async def create_video_object(session: AsyncSession, video_object: schemas.VideoObjectCreate):
    db_vo = models.VideoObject(**video_object.dict())
    session.add(db_vo)
    await session.commit()
    await session.refresh(db_vo)
    return db_vo

async def update_video(db: AsyncSession, video_id: int, video_data: dict):
    # Находим объект
    result = await db.execute(select(models.Video).where(models.Video.id == video_id))
    db_video = result.scalars().first()
    if not db_video:
        return None
    # Обновляем поля
    for key, value in video_data.items():
        setattr(db_video, key, value)
    await db.commit()
    await db.refresh(db_video)
    return db_video

async def get_video_by_hash(db: AsyncSession, video_hash: str):
    res = await db.execute(select(models.Video).where(models.Video.video_hash == video_hash))
    return res.scalars().first()
