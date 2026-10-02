"""Transactional administrator history. Never include credentials or media bodies."""
from app.models import AdminAuditLog


def record_admin_action(db, actor_id, action, target_type, target_id, details=None):
    db.add(AdminAuditLog(actor_id=actor_id, action=action, target_type=target_type,
                         target_id=str(target_id), details=details or {}))
