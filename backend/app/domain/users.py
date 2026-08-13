"""User and counselor account use cases."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole


async def get_user_by_student_id(db: AsyncSession, student_id: str) -> User | None:
    return (await db.execute(select(User).where(User.student_id == student_id))).scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def create_user(db: AsyncSession, student_id: str, name: str, phone: str, class_name: str, password_hash: str) -> User:
    user = User(student_id=student_id, name=name, phone=phone, class_name=class_name, password_hash=password_hash)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def set_counselor(db: AsyncSession, student_ids: list[str]) -> int:
    users = list((await db.scalars(select(User).where(User.student_id.in_(student_ids)))).all())
    for user in users:
        user.role = UserRole.counselor
    await db.commit()
    return len(users)


async def create_counselor_user(db: AsyncSession, student_id: str, name: str, phone: str, class_name: str, password_hash: str) -> User:
    user = await get_user_by_student_id(db, student_id)
    if user:
        user.role = UserRole.counselor
        user.name, user.phone, user.class_name = name, phone, class_name
    else:
        user = User(student_id=student_id, name=name, phone=phone, class_name=class_name, password_hash=password_hash, role=UserRole.counselor)
        db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_counselors(db: AsyncSession) -> list[User]:
    return list((await db.scalars(select(User).where(User.role == UserRole.counselor).order_by(User.student_id))).all())
