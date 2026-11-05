"""POST /assistente: pergunta ao assistente do pedestre (público)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.clients.assistente import AssistenteIndisponivel, ClienteAssistente, resposta_de_contingencia
from app.config import Settings, get_settings
from app.deps import get_assistente
from app.schemas.assistente import PerguntaAssistente, RespostaAssistente
from app.schemas.comum import Erro

router = APIRouter(tags=["Assistente"])


@router.post(
    "/assistente",
    response_model=RespostaAssistente,
    operation_id="perguntarAoAssistente",
    summary="Pergunta ao assistente do pedestre",
    responses={400: {"model": Erro}, 422: {"model": Erro}},
)
def perguntar_ao_assistente(
    corpo: PerguntaAssistente,
    assistente: Annotated[ClienteAssistente, Depends(get_assistente)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RespostaAssistente:
    try:
        return assistente.perguntar(corpo.pergunta)
    except AssistenteIndisponivel:
        # O app continua funcionando sem o assistente: recusa padrão + canal oficial (SP156).
        return resposta_de_contingencia(settings.sp156_url)
