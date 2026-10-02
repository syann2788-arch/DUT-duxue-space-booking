"""Controlled password recovery; plaintext credentials are never persisted or audited."""
import hashlib
import secrets
from datetime import timedelta
from sqlalchemy import select
from fastapi import HTTPException
from app.auth import hash_password, verify_password
from app.models import User, PasswordResetCredential, local_now
from app.domain.audit import record_admin_action


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


async def issue_reset(db, user_id, actor_id, admin_password, reason):
    actor = await db.get(User, actor_id)
    if not actor or not verify_password(admin_password, actor.password_hash):
        raise HTTPException(403, "管理员密码校验失败")
    if user_id == actor_id:
        raise HTTPException(400, "本人请使用修改密码功能")
    user = await db.get(User, user_id, with_for_update=True, populate_existing=True)
    if not user or not user.is_active:
        raise HTTPException(404, "用户不存在或已停用")
    now = local_now()
    previous = (await db.scalars(select(PasswordResetCredential).where(
        PasswordResetCredential.user_id == user_id,
        PasswordResetCredential.consumed_at.is_(None)))).all()
    for row in previous:
        row.consumed_at = now
    credential = secrets.token_urlsafe(32)
    expires = now + timedelta(minutes=30)
    db.add(PasswordResetCredential(user_id=user_id, token_hash=digest(credential),
                                  expires_at=expires, created_by=actor_id))
    record_admin_action(db, actor_id, "password_reset.issue", "user", user_id, {"reason": reason})
    await db.commit()
    return {"credential": credential, "expires_at": expires, "message": "仅交给已核验的本人，30分钟内有效"}


async def reset_password(db, credential, new_password):
    token_hash = digest(credential)
    row = await db.scalar(select(PasswordResetCredential).where(PasswordResetCredential.token_hash == token_hash))
    if not row:
        raise HTTPException(400, "重置凭证无效或已过期")
    user = await db.get(User, row.user_id, with_for_update=True, populate_existing=True)
    row = await db.scalar(select(PasswordResetCredential).where(
        PasswordResetCredential.token_hash == token_hash).with_for_update().execution_options(populate_existing=True))
    now = local_now()
    if not row or row.consumed_at or row.expires_at <= now or not user or not user.is_active:
        raise HTTPException(400, "重置凭证无效或已过期")
    user.password_hash = hash_password(new_password)
    user.session_version += 1
    user.must_change_password = False
    # Revoke the old WeChat binding during manual recovery; rebind after password login.
    user.wechat_openid = None
    row.consumed_at = now
    record_admin_action(db, row.created_by, "password_reset.complete", "user", user.id)
    await db.commit()


async def change_password(db, user_id, current_password, new_password):
    user = await db.get(User, user_id, with_for_update=True, populate_existing=True)
    if not user or not verify_password(current_password, user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    if verify_password(new_password, user.password_hash):
        raise HTTPException(400, "新密码不能与当前密码相同")
    user.password_hash = hash_password(new_password)
    user.session_version += 1
    user.must_change_password = False
    pending = (await db.scalars(select(PasswordResetCredential).where(
        PasswordResetCredential.user_id == user_id,
        PasswordResetCredential.consumed_at.is_(None)))).all()
    for row in pending:
        row.consumed_at = local_now()
    record_admin_action(db, user_id, "password.change", "user", user_id)
    await db.commit()
