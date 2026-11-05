"""POST /assistente: pergunta ao assistente do pedestre (público)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.clients.assistente import ClienteAssistente
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
) -> RespostaAssistente:
    return assistente.perguntar(corpo.pergunta)
