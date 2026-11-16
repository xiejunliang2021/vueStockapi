"""Cloudflare R2 图片上传（S3 API）。

复用存储桶 img-disk，笔记图片放 notes-image/ 文件夹，与 Obsidian 的 ob-image/ 分开。
密钥只放后端服务器 .env，不要进仓库：
    R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    R2_ACCESS_KEY_ID=...
    R2_SECRET_ACCESS_KEY=...
"""

import uuid

import boto3
from botocore.config import Config
from django.conf import settings

CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
}


class R2NotConfigured(Exception):
    pass


def _client():
    if not (
        settings.R2_ENDPOINT_URL
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
    ):
        raise R2NotConfigured("R2 环境变量未配置")
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def upload_image_to_r2(file_obj, ext):
    """上传图片到 notes-image/，返回公网可访问的 URL。"""
    key = f"notes-image/{uuid.uuid4().hex}.{ext}"
    _client().upload_fileobj(
        file_obj,
        settings.R2_BUCKET,
        key,
        ExtraArgs={"ContentType": CONTENT_TYPES.get(ext, "application/octet-stream")},
    )
    return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key}"
