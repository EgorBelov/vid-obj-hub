import os
import cv2
from math import floor
from celery import shared_task
from ultralytics import YOLO
from decouple import config

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Используем абсолютный импорт для корректного разрешения
from recognition_service.celery_app import celery_app
from src.database.models import Video, VideoObject

# Загружаем модель YOLOv8n (предполагается, что веса лежат в yolov8n.pt)
model = YOLO("yolov8n.pt")

DB_URL_SYNC = config("DATABASE_URL_SYNC")
engine = create_engine(DB_URL_SYNC, echo=False)
SessionLocal = sessionmaker(bind=engine)

@celery_app.task(name="process_video_task")
def process_video_task(video_id: int):
    """
    Задача Celery: агрегированное распознавание объектов в видео.
    Для каждого класса объекта считается:
      - total_count: количество появлений,
      - avg_confidence: средняя уверенность,
      - best_confidence: максимальная уверенность,
      - best_second: секунда видео, когда уверенность была максимальной.
    """
    session = SessionLocal()
    try:
        video = session.query(Video).filter_by(id=video_id).one_or_none()
        if not video:
            return f"Video id={video_id} not found!"

        if not video.local_path or not os.path.exists(video.local_path):
            video.status = "error"
            session.commit()
            return f"File {video.local_path} not found!"

        video.status = "processing"
        session.commit()

        counts = {}      # {label: количество}
        sum_conf = {}    # {label: суммарная уверенность}
        best_conf = {}   # {label: максимальная уверенность}
        best_sec = {}    # {label: секунда с максимальной уверенностью}

        cap = cv2.VideoCapture(video.local_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_index = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_index += 1

            try:
                results = model(frame)
            except Exception as e:
                # Если возникла ошибка при обработке кадра, пропускаем его
                continue

            if not results or len(results) == 0:
                continue

            r = results[0]
            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for i in range(len(boxes)):
                try:
                    conf = float(boxes.conf[i])
                    cls_id = int(boxes.cls[i])
                    label = r.names[cls_id]
                except Exception as ex:
                    continue

                counts[label] = counts.get(label, 0) + 1
                sum_conf[label] = sum_conf.get(label, 0.0) + conf

                if label not in best_conf or conf > best_conf[label]:
                    best_conf[label] = conf
                    best_sec[label] = frame_index / fps

        cap.release()

        if not counts:
            video.status = "processed"
            session.commit()
            return f"Video {video_id} processed successfully, but no objects detected."

        # Удаляем предыдущие агрегированные записи для данного видео (если есть)
        session.query(VideoObject).filter_by(video_id=video_id).delete()

        for label, total_count in counts.items():
            avg_conf = sum_conf[label] / total_count
            vo = VideoObject(
                video_id=video_id,
                label=label,
                total_count=total_count,
                avg_confidence=avg_conf,
                best_confidence=best_conf[label],
                best_second=best_sec[label]
            )
            session.add(vo)

        video.status = "processed"
        session.commit()

        return f"Video {video_id} processed successfully with {len(counts)} labels."

    except Exception as e:
        # Логирование ошибки (вы можете добавить self.retry() если хотите повтор)
        return f"Error processing video {video_id}: {str(e)}"
    finally:
        session.close()