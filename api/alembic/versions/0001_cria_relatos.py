"""Cria a tabela de relatos (PostGIS).

Revision ID: 0001
Revises:
Create Date: 2026-11-05
"""

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "relatos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "localizacao",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("foto_chave", sa.String(length=255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("categoria", sa.String(length=30), nullable=True),
        sa.Column("confianca", sa.Float(), nullable=True),
        sa.Column("fonte", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="novo", nullable=False),
        sa.Column("confirmacoes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("subprefeitura", sa.String(length=100), nullable=True),
        sa.Column("prioridade", sa.String(length=10), nullable=True),
        sa.Column("simulado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_relatos")),
        sa.CheckConstraint(
            "categoria IN ('buraco', 'piso_danificado', 'obstaculo', 'veiculo_na_calcada')",
            name=op.f("ck_relatos_categoria_valida"),
        ),
        sa.CheckConstraint(
            "status IN ('novo', 'revisao_humana', 'validado', 'encaminhado', 'resolvido', 'rejeitado')",
            name=op.f("ck_relatos_status_valido"),
        ),
        sa.CheckConstraint("fonte IN ('app', 'robo')", name=op.f("ck_relatos_fonte_valida")),
        sa.CheckConstraint(
            "prioridade IN ('alta', 'media', 'baixa')", name=op.f("ck_relatos_prioridade_valida")
        ),
        sa.CheckConstraint("confianca >= 0 AND confianca <= 1", name=op.f("ck_relatos_confianca_entre_0_e_1")),
        sa.CheckConstraint("confirmacoes >= 0", name=op.f("ck_relatos_confirmacoes_nao_negativas")),
    )
    op.create_index("ix_relatos_localizacao", "relatos", ["localizacao"], postgresql_using="gist")
    op.create_index("ix_relatos_status_criado_em", "relatos", ["status", "criado_em"])


def downgrade() -> None:
    op.drop_index("ix_relatos_status_criado_em", table_name="relatos")
    op.drop_index("ix_relatos_localizacao", table_name="relatos", postgresql_using="gist")
    op.drop_table("relatos")
