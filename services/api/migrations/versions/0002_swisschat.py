"""swisschat: integration_credentials + conversations.external_id

Revision ID: 0002_swisschat
Revises: 0001_initial
Create Date: 2026-05-18
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_swisschat"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_credentials",
        sa.Column("name", sa.String(length=60), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("data_encrypted", sa.Text(), nullable=True),
        sa.Column("public", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "conversations",
        sa.Column("external_id", sa.String(length=120), nullable=True),
    )
    op.create_index("ix_conversations_external_id", "conversations", ["external_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_external_id", table_name="conversations")
    op.drop_column("conversations", "external_id")
    op.drop_table("integration_credentials")
