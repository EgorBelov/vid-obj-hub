# db_service/schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class VideoBase(BaseModel):
    telegram_file_id: str
    s3_url: Optional[str] = None
    user_id: int
    status: Optional[str] = "pending"

class VideoCreate(BaseModel):
    telegram_file_id: str
    user_id: int
    video_hash: str          # ← обязательно
    s3_url: str | None = None
    status: str = "pending"
    upload_time: datetime


class Video(VideoBase):
    id: int
    upload_time: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class VideoObjectBase(BaseModel):
    label: str
    total_count: int
    avg_confidence: float
    best_confidence: float
    best_second: float

class VideoObjectCreate(BaseModel):
    video_id: int
    label: str
    total_count: int
    avg_confidence: float
    best_confidence: float
    best_second: float

    class Config:
        orm_mode = True

class VideoObject(VideoObjectBase):
    id: int
    video_id: int

    class Config:
        orm_mode = True

class VideoUpdate(BaseModel):
    status: Optional[str] = None
    s3_url: Optional[str] = None

