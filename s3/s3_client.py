# src/s3/s3_client.py
import boto3
from decouple import config

AWS_ACCESS_KEY = config("AWS_ACCESS_KEY")
AWS_SECRET_KEY = config("AWS_SECRET_KEY")
AWS_ENDPOINT_URL = config("AWS_ENDPOINT_URL")  # например, "https://storage.yandexcloud.net"
S3_BUCKET = config("S3_BUCKET")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    endpoint_url=AWS_ENDPOINT_URL  # важно для Yandex Cloud
)

def upload_fileobj(fileobj, key: str) -> str:
    """
    Загрузка файла (fileobj — любой файловый-like объект) в S3 под указанным ключом.
    Возвращает публичный URL (если бакет публичен) или https-ссылку.
    """
    s3_client.upload_fileobj(fileobj, S3_BUCKET, key)
    # Формируем URL объекта
    return f"{AWS_ENDPOINT_URL}/{S3_BUCKET}/{key}"
