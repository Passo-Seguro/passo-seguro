"""Tipos compartilhados pelos schemas de resposta."""

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import BaseModel, PlainSerializer

FUSO_SP = ZoneInfo("America/Sao_Paulo")


def _para_sp(valor: datetime) -> str:
    """Datas saem em ISO 8601 no fuso de São Paulo, como nos exemplos do contrato."""
    return valor.astimezone(FUSO_SP).replace(microsecond=0).isoformat()


DataHoraSP = Annotated[datetime, PlainSerializer(_para_sp, return_type=str, when_used="json")]


class DetalheErro(BaseModel):
    campo: str
    problema: str


class Erro(BaseModel):
    codigo: str
    mensagem: str
    detalhes: list[DetalheErro] | None = None
