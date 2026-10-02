"""Run after migration, on the server terminal. Never promotes an existing account."""
import asyncio
import getpass
from sqlalchemy import select
from app.auth import hash_password
from app.database import init_db, async_session
from app.models import User, UserRole
from app.schemas import PasswordChange
from app.domain.audit import record_admin_action


async def main():
    account = input("新管理员账号：").strip()
    name = input("管理员姓名：").strip()
    password = getpass.getpass("新密码（至少8位，含字母数字）：")
    if password != getpass.getpass("确认密码："):
        raise RuntimeError("两次密码不一致")
    PasswordChange(current_password="validation-only", new_password=password)
    if not account or not name:
        raise RuntimeError("账号和姓名必填")
    await init_db()
    async with async_session() as db:
        if await db.scalar(select(User.id).where(User.student_id == account)):
            raise RuntimeError("账号已存在，拒绝覆盖或提升权限")
        user = User(student_id=account, name=name, phone="", class_name="管理员", password_hash=hash_password(password), role=UserRole.admin)
        db.add(user)
        await db.flush()
        record_admin_action(db, None, "admin.provision", "user", user.id)
        await db.commit()
    print("管理员已建立；请按学校流程保管账号")


if __name__ == "__main__":
    asyncio.run(main())
