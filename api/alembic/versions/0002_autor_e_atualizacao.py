"""Adiciona autor_hash (privacidade) e atualizado_em aos relatos.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("relatos", sa.Column("autor_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "relatos",
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_relatos_autor_hash_criado_em", "relatos", ["autor_hash", "criado_em"])


def downgrade() -> None:
    op.drop_index("ix_relatos_autor_hash_criado_em", table_name="relatos")
    op.drop_column("relatos", "atualizado_em")
    op.drop_column("relatos", "autor_hash")
