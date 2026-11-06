"""GET /painel: prioridades por subprefeitura (público).

Etapa 1: devolve dados de exemplo. A leitura do arquivo exportado pelo pipeline de dados
entra na etapa de integração.
"""

from fastapi import APIRouter

from app.schemas.comum import Erro
from app.schemas.painel import PrioridadeSubprefeitura
from app.services.exemplos import PAINEL_EXEMPLO

router = APIRouter(tags=["Painel"])


@router.get(
    "/painel",
    response_model=list[PrioridadeSubprefeitura],
    operation_id="obterPainel",
    summary="Prioridades por subprefeitura",
    responses={404: {"model": Erro}},
)
def obter_painel() -> list[PrioridadeSubprefeitura]:
    return PAINEL_EXEMPLO
