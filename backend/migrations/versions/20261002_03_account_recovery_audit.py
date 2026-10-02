"""Session revocation, one-time password recovery and administrator audit history."""
from alembic import op
import sqlalchemy as sa
from app.models import AdminAuditLog, PasswordResetCredential

revision = "20261002_03"
down_revision = "20260813_02"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    if "session_version" not in columns:
        op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    if "must_change_password" not in columns:
        op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    AdminAuditLog.__table__.create(bind, checkfirst=True)
    PasswordResetCredential.__table__.create(bind, checkfirst=True)


def downgrade():
    raise RuntimeError("账号与审计迁移不可破坏性降级；请按运行手册恢复发布前备份")
