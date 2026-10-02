"""Local controlled import; conflicts are rejected, credentials are written to a private file."""
import asyncio
import csv
import json
import os
import secrets
from pathlib import Path
from sqlalchemy import select
from app.database import init_db, async_session
from app.models import User
from app.auth import hash_password
from app.domain.users import create_counselor_user
from app.domain.audit import record_admin_action


async def import_counselors():
    source = Path(os.environ.get("COUNSELOR_CSV_PATH", "../Sheet_20250907.csv"))
    output = Path(os.environ["COUNSELOR_CREDENTIALS_OUTPUT"])
    if output.exists():
        raise RuntimeError("凭据文件已存在，拒绝覆盖")
    rows = list(csv.DictReader(source.open(encoding="utf-8-sig")))
    await init_db()
    accounts = []
    async with async_session() as db:
        for row in rows:
            if row.get("职务") not in {"辅导员", "执行院长", "副院长"} or not row.get("姓名"):
                continue
            phone = row.get("联系方式", "").strip()
            login_id = phone if phone.isdigit() else "staff_" + row["姓名"].strip()
            existing = await db.scalar(select(User).where(User.student_id == login_id))
            if existing and existing.role.value != "counselor":
                raise RuntimeError("账号标识冲突，需人工核验归属")
            if existing:
                continue
            password = "A1" + secrets.token_urlsafe(18)
            await create_counselor_user(db, login_id, row["姓名"], phone, row.get("负责班级", ""), hash_password(password), commit=False)
            accounts.append({"login_id": login_id, "password": password})
        record_admin_action(db, None, "counselor.import", "users", "controlled-cli", {"created": len(accounts)})
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(accounts, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            await db.commit()
        except Exception:
            output.unlink(missing_ok=True)
            raise
    print(f"导入完成：{len(accounts)} 个新账号；初始凭据只写入受控文件，首次登录需换密")


if __name__ == "__main__":
    asyncio.run(import_counselors())
