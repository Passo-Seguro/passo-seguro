"""Adiciona modo_deteccao aos relatos (como a categoria foi obtida: real, fake ou nenhuma).

Coluna INTERNA, fora do contrato. Os relatos que já existiam ficam como `nenhuma` (não há
como saber como foram detectados; antes desta migração não havia deploy com dados reais).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "relatos",
        sa.Column("modo_deteccao", sa.String(length=10), server_default="nenhuma", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_relatos_modo_deteccao_valido"),
        "relatos",
        "modo_deteccao IN ('real', 'fake', 'nenhuma')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_relatos_modo_deteccao_valido"), "relatos", type_="check")
    op.drop_column("relatos", "modo_deteccao")
