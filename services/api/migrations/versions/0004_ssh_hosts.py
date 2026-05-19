"""ssh_hosts: labeled multi-host SSH execution targets

Revision ID: 0004_ssh_hosts
Revises: 0003_model_override
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0004_ssh_hosts"
down_revision = "0003_model_override"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ssh_hosts",
        sa.Column("label", sa.String(length=60), primary_key=True),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False,
                  server_default="ubuntu"),
        sa.Column("port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("private_key_encrypted", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=120), nullable=True),
        sa.Column("created_by", PGUUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ssh_hosts")
