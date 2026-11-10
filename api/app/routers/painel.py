"""GET /painel: prioridades por subprefeitura (público).

Lê o painel.json exportado pelo pipeline de dados (PAINEL_BLOB_URL em produção, PAINEL_JSON_PATH
em desenvolvimento) e valida contra o schema do contrato. Sem arquivo: 404 `painel_indisponivel`;
arquivo ou leitura com problema: 503 `painel_invalido`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.comum import Erro
from app.schemas.painel import PrioridadeSubprefeitura
from app.services.painel import ler_painel

router = APIRouter(tags=["Painel"])


@router.get(
    "/painel",
    response_model=list[PrioridadeSubprefeitura],
    operation_id="obterPainel",
    summary="Prioridades por subprefeitura",
    responses={404: {"model": Erro}, 503: {"model": Erro}},
)
def obter_painel(settings: Annotated[Settings, Depends(get_settings)]) -> list[PrioridadeSubprefeitura]:
    return ler_painel(settings.painel_json_path, blob_url=settings.painel_blob_url)
