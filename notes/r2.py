"""Cloudflare R2 图片上传（S3 API）。

复用存储桶 img-disk，笔记图片放 notes-image/ 文件夹，与 Obsidian 的 ob-image/ 分开。
密钥只放后端服务器 .env，不要进仓库：
    R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    R2_ACCESS_KEY_ID=...
    R2_SECRET_ACCESS_KEY=...

默认压缩（2026-11-20）：上传的图片在入库前压缩一次，只为前端展示留够清晰度——
最长边超过 1600px 时等比缩小（只缩不放），JPEG 质量 85；带透明通道的转 WebP；
GIF 原样上传（不动图不拆帧）；压缩失败时回退原图上传，不中断。
同时去掉 EXIF（含拍摄方向与 GPS），并按 EXIF 方向先摆正图片。
"""

import io
import uuid

import boto3
from botocore.config import Config
from django.conf import settings
from PIL import Image, ImageOps

CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
}

# 展示用图的上限：1600px 在手机与电脑上都够清晰
MAX_DIMENSION = 1600
JPEG_QUALITY = 85
WEBP_QUALITY = 85

# 不压缩的格式：GIF 动图原样上传，避免拆帧或丢动画
PASSTHROUGH_EXTS = {"gif"}


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


def _compress_image(file_obj, ext):
    """压缩图片，返回 (文件对象, 最终扩展名)。

    最长边超过 1600px 时等比缩小；无透明通道转 JPEG（质量 85），
    带透明通道转 WebP（质量 85）。任何一步失败都回退原图，
    保证上传不因压缩中断。
    """
    try:
        file_obj.seek(0)
        img = Image.open(file_obj)
        img = ImageOps.exif_transpose(img)
        if max(img.size) > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )
        buf = io.BytesIO()
        if has_alpha:
            img.convert("RGBA").save(buf, "WEBP", quality=WEBP_QUALITY, method=6)
            return buf, "webp"
        img.convert("RGB").save(
            buf, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True
        )
        return buf, "jpg"
    except Exception:
        try:
            file_obj.seek(0)
        except Exception:
            pass
        return file_obj, ext


def upload_image_to_r2(file_obj, ext):
    """上传图片到 notes-image/，返回公网可访问的 URL。

    默认先压缩（见模块说明），GIF 原样上传。
    """
    if ext in PASSTHROUGH_EXTS:
        data, final_ext = file_obj, ext
    else:
        data, final_ext = _compress_image(file_obj, ext)
    try:
        data.seek(0)
    except Exception:
        pass
    key = f"notes-image/{uuid.uuid4().hex}.{final_ext}"
    _client().upload_fileobj(
        data,
        settings.R2_BUCKET,
        key,
        ExtraArgs={"ContentType": CONTENT_TYPES.get(final_ext, "application/octet-stream")},
    )
    return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key}"
