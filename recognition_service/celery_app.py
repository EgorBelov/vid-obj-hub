# recognition_service/celery_app.py
import os
from celery import Celery
from decouple import config

BROKER_URL = config("BROKER_URL")

celery_app = Celery(
    "recognition_service",
    broker=BROKER_URL,
)

# Какие-то настройки по желанию
celery_app.conf.update(
    result_expires=3600,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    # можно определить очередь:
    # task_default_queue='recognition_queue'
)

import recognition_service.detect