# recognition_service/detect.py
import os
import tempfile
import cv2
from math import floor
import requests
import httpx
from ultralytics import YOLO
from decouple import config

from recognition_service.celery_app import celery_app

# Загружаем модель YOLOv8n (предполагается, что файл yolov8n.pt находится в рабочем каталоге или доступен)
model = YOLO("yolo12n.pt")

# URL DB-сервиса, например "http://localhost:8000"
DB_SERVICE_URL = config("DB_SERVICE_URL", default="http://localhost:8000")

@celery_app.task(name="process_video_task")
def process_video_task(video_id: int):
    """
    Задача для агрегированного распознавания объектов в видео,
    которая обращается к DB-сервису по HTTP API.
    Для каждого класса объекта вычисляются:
      - total_count: число появлений,
      - avg_confidence: средняя уверенность,
      - best_confidence: максимальная уверенность,
      - best_second: время (в секундах), когда наблюдалась максимальная уверенность.
    """
    try:
        # 1. Получаем информацию о видео через DB-сервис
        with httpx.Client() as client:
            video_resp = client.get(f"{DB_SERVICE_URL}/videos/{video_id}")
            if video_resp.status_code != 200:
                return f"Video id={video_id} not found!"
            video_data = video_resp.json()
            
            # Для обработки нам нужен s3_url
            s3_url = video_data.get("s3_url")
            if not s3_url:
                client.put(f"{DB_SERVICE_URL}/videos/{video_id}", json={"status": "error"})
                return f"No s3_url in DB for video id={video_id}!"
            
            # Обновляем статус видео на "processing"
            client.put(f"{DB_SERVICE_URL}/videos/{video_id}", json={"status": "processing"})
        
        # 2. Скачиваем видео из S3 во временный файл
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmpfile:
            response = requests.get(s3_url, stream=True)
            if response.status_code != 200:
                with httpx.Client() as client:
                    client.put(f"{DB_SERVICE_URL}/videos/{video_id}", json={"status": "error"})
                return f"Error downloading {s3_url}"
            for chunk in response.iter_content(chunk_size=8192):
                tmpfile.write(chunk)
            tmp_path = tmpfile.name

        # 3. Обрабатываем видео: собираем агрегированную статистику
        counts = {}      # {label: count}
        sum_conf = {}    # {label: cumulative confidence}
        best_conf = {}   # {label: maximum confidence}
        best_sec = {}    # {label: second when max confidence recorded}

        cap = cv2.VideoCapture(tmp_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_index = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_index += 1

            try:
                results = model(frame)
            except Exception:
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
                except Exception:
                    continue

                counts[label] = counts.get(label, 0) + 1
                sum_conf[label] = sum_conf.get(label, 0.0) + conf
                if label not in best_conf or conf > best_conf[label]:
                    best_conf[label] = conf
                    best_sec[label] = frame_index / fps

        cap.release()
        os.remove(tmp_path)  # Очистим временный файл

        if not counts:
            # Если объекты не обнаружены, обновляем статус и выходим
            with httpx.Client() as client:
                client.put(f"{DB_SERVICE_URL}/videos/{video_id}", json={"status": "processed"})
            return f"Video {video_id} processed successfully, but no objects detected."

        # 4. Обновляем агрегированные данные через DB-сервис:
        with httpx.Client() as client:
            # Сначала удаляем старые агрегированные записи для этого видео
            client.delete(f"{DB_SERVICE_URL}/videos/{video_id}/objects")

            # Затем для каждого label создаем новую запись
            for label, total_count in counts.items():
                avg_conf = sum_conf[label] / total_count
                payload = {
                    "video_id": video_id,
                    "label": label,
                    "total_count": total_count,
                    "avg_confidence": avg_conf,
                    "best_confidence": best_conf[label],
                    "best_second": best_sec[label]
                }
                post_resp = client.post(f"{DB_SERVICE_URL}/videos/{video_id}/objects", json=payload)
                # Можно добавить проверку post_resp.status_code

            # Обновляем статус видео на "processed"
            client.put(f"{DB_SERVICE_URL}/videos/{video_id}", json={"status": "processed"})

        return f"Video {video_id} processed successfully with {len(counts)} labels."
    except Exception as e:
        return f"Error processing video {video_id}: {str(e)}"
