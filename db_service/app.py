# db_service/app.py
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import delete
from database import AsyncSessionLocal, engine
import models, schemas, crud
from sqlalchemy.ext.asyncio import AsyncSession

import uvicorn

app = FastAPI(title="Vid-Obj Hub DB Service")

# Создание таблиц при старте
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

# Dependency для работы с базой
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

@app.post("/videos/", response_model=schemas.Video)
async def create_video(video: schemas.VideoCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_video(db, video)

@app.get("/videos/{video_id}", response_model=schemas.Video)
async def read_video(video_id: int, db: AsyncSession = Depends(get_db)):
    db_video = await crud.get_video(db, video_id)
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return db_video

@app.put("/videos/{video_id}", response_model=schemas.Video)
async def update_video_endpoint(video_id: int, video_update: schemas.VideoUpdate, db: AsyncSession = Depends(get_db)):
    db_video = await crud.get_video(db, video_id)
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Сливаем поля из video_update
    update_data = video_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_video, key, value)

    await db.commit()
    await db.refresh(db_video)
    return db_video


@app.get("/videos/", response_model=list[schemas.Video])
async def read_videos(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    videos = await crud.list_videos(db, skip=skip, limit=limit)
    return videos

@app.get("/videos/{video_id}/objects", response_model=list[schemas.VideoObject])
async def read_video_objects(video_id: int, db: AsyncSession = Depends(get_db)):
    objects = await crud.get_video_objects(db, video_id)
    return objects


@app.delete("/videos/{video_id}/objects")
async def delete_objects_for_video(video_id: int, db: AsyncSession = Depends(get_db)):
    """
    Удаляет все VideoObject для данного video_id
    """
    # Убеждаемся, что видео есть
    db_video = await crud.get_video(db, video_id)
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Выполняем удаление
    await db.execute(delete(models.VideoObject).where(models.VideoObject.video_id == video_id))
    await db.commit()
    return {"detail": f"VideoObjects for video {video_id} removed"}


@app.post("/videos/{video_id}/objects", response_model=schemas.VideoObject)
async def create_object_for_video(video_id: int, vo_data: schemas.VideoObjectCreate, db: AsyncSession = Depends(get_db)):
    """
    Создает новую запись VideoObject для данного video_id
    """
    # Проверяем соответствие video_id
    if vo_data.video_id != video_id:
        raise HTTPException(status_code=400, detail="Mismatched video_id in body and path")

    # Проверяем, что видео существует
    db_video = await crud.get_video(db, video_id)
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")

    new_vo = await crud.create_video_object(db, vo_data)
    return new_vo


if __name__ == '__main__':
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
