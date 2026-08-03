"""Import local counselor CSV data into the database.

The real Sheet_20250907.csv is intentionally excluded from Git because it can
contain personal information. Copy the example file and replace it locally.
"""
import asyncio
import csv
import os
import sys
sys.path.insert(0, '.')

from app.database import init_db, async_session
from app.models import User, UserRole
from app.auth import hash_password


CSV_PATH = os.getenv(
    "COUNSELOR_CSV_PATH",
    os.path.join(os.path.dirname(__file__), '..', 'Sheet_20250907.csv'),
)


async def import_counselors():
    await init_db()

    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(
            f"Counselor CSV not found: {CSV_PATH}. "
            "Copy Sheet_20250907.example.csv to Sheet_20250907.csv first."
        )

    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("CSV is empty")
        return

    # Parse header
    raw_header = [h.strip().strip('"').strip('﻿') for h in rows[0]]
    header_map = {h: i for i, h in enumerate(raw_header)}
    print(f"Headers: {raw_header}")

    def col(row, *names):
        for n in names:
            if n in header_map:
                val = row[header_map[n]].strip().strip('"')
                return val
        return ""

    async with async_session() as db:
        created = []

        for row in rows[1:]:
            if not row or len(row) < 2:
                continue

            position = col(row, "职务")
            name = col(row, "姓名")
            if not name:
                continue

            # Only import relevant staff
            if position not in ("辅导员", "执行院长", "副院长"):
                continue

            phone = col(row, "联系方式", "电话")
            classes = col(row, "负责班级")

            # Use phone as login ID, or generate staff ID
            if phone and phone != "-" and phone.isdigit():
                login_id = phone
            else:
                login_id = f"staff_{name}"

            password = phone if (phone and phone != "-") else "shuyuan123"

            # Check if already exists
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.student_id == login_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                if existing.role != UserRole.counselor:
                    existing.role = UserRole.counselor
                    print(f"  [更新] {name} -> 已设为辅导员 (login: {login_id})")
                else:
                    print(f"  [跳过] {name} -> 已是辅导员 (login: {login_id})")
                    continue
            else:
                user = User(
                    student_id=login_id,
                    name=name,
                    phone=phone if phone != "-" else "",
                    class_name=classes if classes != "-" else "",
                    password_hash=hash_password(password),
                    role=UserRole.counselor,
                )
                db.add(user)
                print(f"  [新建] {name} ({position}) -> login: {login_id}  password: {password}")

            created.append({
                "name": name,
                "position": position,
                "login_id": login_id,
                "password": password,
            })

        await db.commit()

        print(f"\n===== 导入完成：{len(created)} 位辅导员 =====")
        print(f"{'姓名':<8} {'职务':<8} {'登录账号':<16} {'密码':<16}")
        print("-" * 50)
        for c in created:
            print(f"{c['name']:<8} {c['position']:<8} {c['login_id']:<16} {c['password']:<16}")


if __name__ == "__main__":
    asyncio.run(import_counselors())
