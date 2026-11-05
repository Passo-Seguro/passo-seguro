from pydantic import BaseModel, Field

from app.dominio import Categoria, Prioridade
from app.schemas.comum import DataHoraSP


class PrioridadeSubprefeitura(BaseModel):
    """Linha da view `vw_prioridades` (camada Ouro), por subprefeitura."""

    subprefeitura: str
    prioridade: Prioridade
    relatos_abertos: int = Field(ge=0)
    relatos_por_categoria: dict[Categoria, int]
    tempo_medio_ate_reparo_dias: float | None = Field(default=None, ge=0)
    atualizado_em: DataHoraSP
