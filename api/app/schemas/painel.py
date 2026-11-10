from typing import Any

from pydantic import BaseModel, Field, model_serializer

from app.dominio import Categoria, Prioridade
from app.schemas.comum import DataHoraSP

# Campos opcionais do contrato: quando o pipeline não os envia, ficam FORA da resposta
# (no contrato não são "nullable", então `null` seria uma resposta inválida).
_OPCIONAIS = (
    "reclamacoes_calcada_sp156",
    "reclamacoes_guia_sarjeta_sp156",
    "atropelamentos_pedestres",
    "pedestres_mortos",
    "indice_prioridade",
)


class PrioridadeSubprefeitura(BaseModel):
    """Linha da view `vw_prioridades` (camada Ouro), por subprefeitura."""

    subprefeitura: str
    prioridade: Prioridade
    relatos_abertos: int = Field(ge=0)
    relatos_por_categoria: dict[Categoria, int]
    tempo_medio_ate_reparo_dias: float | None = Field(default=None, ge=0)
    atualizado_em: DataHoraSP
    # Indicadores reais (SP156 e Infosiga), todos opcionais.
    reclamacoes_calcada_sp156: int | None = Field(default=None, ge=0)
    reclamacoes_guia_sarjeta_sp156: int | None = Field(default=None, ge=0)
    atropelamentos_pedestres: int | None = Field(default=None, ge=0)
    pedestres_mortos: int | None = Field(default=None, ge=0)
    indice_prioridade: float | None = Field(default=None, ge=0, le=1)

    @model_serializer(mode="wrap")
    def _sem_opcionais_nulos(self, proximo: Any) -> dict[str, Any]:
        dados = proximo(self)
        for campo in _OPCIONAIS:
            if dados.get(campo) is None:
                dados.pop(campo, None)
        return dados
