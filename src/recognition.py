# src/recognition.py
import cv2
from ultralytics import YOLO
from math import floor

from src.database.models import VideoObject

# Загружаем модель (YOLOv8n как пример)
model = YOLO("yolov8n.pt")

async def detect_objects_in_video(session, video_id: int, video_path: str):
    """
    Агрегированная статистика по классам:
      - total_count: сколько раз встретился класс
      - avg_confidence: средняя уверенность 
      - best_confidence: максимальная уверенность
      - best_second: время (в секундах), когда была максимальная уверенность
    """
    counts = {}
    sum_conf = {}
    best_conf = {}
    best_second = {}

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    frame_index = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_index += 1

        # Запускаем детектор
        results = model(frame)
        r = results[0]
        boxes = r.boxes  # Detected boxes

        # Обходим каждую найденную детекцию
        for i in range(len(boxes)):
            conf = float(boxes.conf[i])
            cls_id = int(boxes.cls[i])
            label = r.names[cls_id]

            # Увеличиваем счётчик для класса
            counts[label] = counts.get(label, 0) + 1
            # Накопление суммы для среднего
            sum_conf[label] = sum_conf.get(label, 0.0) + conf

            # Максимальная уверенность
            if label not in best_conf or conf > best_conf[label]:
                best_conf[label] = conf
                best_second[label] = frame_index / fps

    cap.release()

    # Сохраняем результаты в БД
    for label, total_count in counts.items():
        avg_conf = sum_conf[label] / total_count
        bc = best_conf[label]
        bs = best_second[label]

        vo = VideoObject(
            video_id=video_id,
            label=label,
            total_count=total_count,
            avg_confidence=avg_conf,
            best_confidence=bc,
            best_second=bs
        )
        session.add(vo)

    await session.commit()
    print(f"Video {video_id} завершено (агрегированная статистика).")
