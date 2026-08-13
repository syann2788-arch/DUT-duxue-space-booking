from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MediaPurpose, PrivateMedia, local_now


IMAGE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def _validated_image(file: UploadFile) -> tuple[bytes, str]:
    if file.content_type not in IMAGE_SUFFIXES:
        raise HTTPException(400, "仅支持 JPG、PNG、WebP 图片")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, f"单张照片不能超过{settings.MAX_UPLOAD_MB}MB")
    signatures_ok = {
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
    }
    if not signatures_ok[file.content_type]:
        raise HTTPException(400, "文件内容与图片格式不匹配")
    return content, IMAGE_SUFFIXES[file.content_type]


async def store_image(file: UploadFile, user_id: int, prefix: str) -> dict[str, str]:
    """Store a non-sensitive public message image."""
    if prefix not in {"campus_card", "cleanup", "message"}:
        raise ValueError("unsupported upload prefix")
    if prefix != "message":
        raise ValueError("sensitive images must use store_private_image")
    content, suffix = await _validated_image(file)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"message_{uuid4().hex}{suffix}"
    (upload_dir / filename).write_bytes(content)
    return {"url": f"/uploads/{filename}"}


async def store_private_image(
    file: UploadFile,
    user_id: int,
    purpose: str,
    db: AsyncSession,
) -> dict[str, str]:
    try:
        media_purpose = MediaPurpose(purpose)
    except ValueError as exc:
        raise ValueError("unsupported private media purpose") from exc
    content, suffix = await _validated_image(file)
    media_id = str(uuid4())
    storage_key = f"{media_id}{suffix}"
    private_dir = Path(settings.PRIVATE_UPLOAD_DIR)
    private_dir.mkdir(parents=True, exist_ok=True)
    path = private_dir / storage_key
    path.write_bytes(content)
    db.add(PrivateMedia(
        id=media_id,
        owner_id=user_id,
        purpose=media_purpose,
        storage_key=storage_key,
        content_type=file.content_type,
        size_bytes=len(content),
        expires_at=local_now() + timedelta(days=settings.MEDIA_RETENTION_DAYS),
    ))
    try:
        await db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"media_id": media_id}
