"""conversations.model_override

Revision ID: 0003_model_override
Revises: 0002_swisschat
Create Date: 2026-05-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_model_override"
down_revision = "0002_swisschat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("model_override", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "model_override")
