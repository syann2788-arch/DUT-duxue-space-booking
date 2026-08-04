from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.config import settings


IMAGE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def store_image(file: UploadFile, user_id: int, prefix: str) -> dict[str, str]:
    if prefix not in {"campus_card", "cleanup", "message"}:
        raise ValueError("unsupported upload prefix")
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

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    owner_part = "" if prefix == "message" else f"_{user_id}"
    filename = f"{prefix}{owner_part}_{uuid4().hex}{IMAGE_SUFFIXES[file.content_type]}"
    (upload_dir / filename).write_bytes(content)
    return {"url": f"/uploads/{filename}"}
