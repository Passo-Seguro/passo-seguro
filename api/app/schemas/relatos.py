"""Schemas de relatos, iguais aos do contrato (openapi.yaml)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.dominio import Categoria, FonteRelato, Prioridade, StatusRelato
from app.schemas.comum import DataHoraSP

Confianca = Field(ge=0, le=1)


class Relato(BaseModel):
    id: UUID
    criado_em: DataHoraSP
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    foto_url: str
    descricao: str | None = Field(default=None, max_length=1000)
    categoria: Categoria | None
    confianca: float | None = Confianca
    fonte: FonteRelato
    status: StatusRelato
    confirmacoes: int = Field(ge=0)
    subprefeitura: str | None = None
    prioridade: Prioridade | None = None


class RelatoCriado(BaseModel):
    id: UUID
    categoria: Categoria | None
    confianca: float | None = Confianca
    status: StatusRelato = Field(description="A API sempre cria o relato como `novo`.")


class Paginacao(BaseModel):
    pagina: int = Field(ge=1)
    tamanho: int = Field(ge=1, le=100)
    total_itens: int = Field(ge=0)
    total_paginas: int = Field(ge=0)
    tem_proxima: bool


class ListaRelatos(BaseModel):
    itens: list[Relato]
    paginacao: Paginacao


# --- Emenda rc2 do contrato (só valem quando HABILITAR_RC2=true) -----------------------


class RelatoProximo(BaseModel):
    """Relato no mapa público: sem foto, sem descrição, sem autor, localização a ~100 m."""

    id: UUID
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    categoria: Categoria | None
    status: StatusRelato
    prioridade: Prioridade | None
    confirmacoes: int = Field(ge=0)


class RelatoResumo(BaseModel):
    """Relato do próprio cidadão (tela "meus relatos")."""

    id: UUID
    criado_em: DataHoraSP
    categoria: Categoria | None
    status: StatusRelato
    foto_url: str


class AtualizacaoRelato(BaseModel):
    """Corpo do PATCH /relatos/{id}. Parcial: só os campos enviados mudam."""

    model_config = ConfigDict(extra="forbid")

    # Sem `| None` de propósito: enviar `null` explícito é erro, não "não mudar".
    categoria: Categoria = Field(default=None)
    status: StatusRelato = Field(default=None)
    subprefeitura: str = Field(default=None, min_length=1, max_length=100)
    prioridade: Prioridade = Field(default=None)
    confirmacoes: int = Field(default=None, ge=0)
