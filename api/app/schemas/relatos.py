"""Schemas de relatos, iguais aos do contrato (openapi.yaml)."""

from uuid import UUID

from pydantic import BaseModel, Field

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
