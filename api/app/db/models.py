"""Modelo do banco. Os valores de categoria/status/prioridade/fonte são os do contrato."""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Index, Integer, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dominio import Categoria, FonteRelato, Prioridade, StatusRelato


def _em(coluna: str, valores) -> str:
    lista = ", ".join(f"'{v.value}'" for v in valores)
    return f"{coluna} IN ({lista})"


class Relato(Base):
    __tablename__ = "relatos"
    __table_args__ = (
        CheckConstraint(_em("categoria", Categoria), name="categoria_valida"),
        CheckConstraint(_em("status", StatusRelato), name="status_valido"),
        CheckConstraint(_em("fonte", FonteRelato), name="fonte_valida"),
        CheckConstraint(_em("prioridade", Prioridade), name="prioridade_valida"),
        CheckConstraint("confianca >= 0 AND confianca <= 1", name="confianca_entre_0_e_1"),
        CheckConstraint("confirmacoes >= 0", name="confirmacoes_nao_negativas"),
        Index("ix_relatos_localizacao", "localizacao", postgresql_using="gist"),
        Index("ix_relatos_status_criado_em", "status", "criado_em"),
        Index("ix_relatos_autor_hash_criado_em", "autor_hash", "criado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Ponto (lon, lat) em WGS84. Geography: distâncias em metros, sem conversão de graus.
    localizacao = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False)
    # Chave da foto no armazenamento (a URL é montada pela interface de storage).
    foto_chave: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    # Nulos quando a visão não detectou nada ou estava fora do ar.
    categoria: Mapped[str | None] = mapped_column(String(30))
    confianca: Mapped[float | None] = mapped_column(Float)
    fonte: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatusRelato.NOVO.value, server_default=StatusRelato.NOVO.value
    )
    confirmacoes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    subprefeitura: Mapped[str | None] = mapped_column(String(100))
    prioridade: Mapped[str | None] = mapped_column(String(10))
    # HMAC-SHA256(SALT_AUTOR, autor_id) em hexadecimal. O autor_id em si NUNCA é guardado,
    # e nem ele nem o hash saem pela API ou pelos logs.
    autor_hash: Mapped[str | None] = mapped_column(String(64))
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # Dado fictício gerado por scripts/gerar_dados_simulados.py. Não aparece na API; serve
    # para separar e apagar (docs/dados-simulados.md).
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
