# src/database/models.py
from datetime import datetime
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey

Base = declarative_base()

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    telegram_file_id = Column(String, unique=True, index=True)
    local_path = Column(String)  # путь к локальному файлу видео
    user_id = Column(Integer)
    upload_time = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # "pending", "processing", "processed"

    # Новая связь к сводной таблице
    objects_summary = relationship("VideoObject", back_populates="video")

class VideoObject(Base):
    """
    Сводная информация о том, сколько объектов класса 'label' найдено в данном видео
    """
    __tablename__ = "video_objects"

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id"))
    label = Column(String)       # "person", "car" и т.п.
    total_count = Column(Integer)  # общее число обнаружений
    avg_confidence = Column(Float, default=0.0) # средняя уверенность (при желании)

    best_confidence = Column(Float, default=0.0)
    best_second = Column(Float, default=0.0)

    video = relationship("Video", back_populates="objects_summary")