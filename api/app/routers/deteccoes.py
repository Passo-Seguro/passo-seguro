"""POST /deteccoes: detecção de problemas em uma imagem (chamada entre serviços)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.clients.visao import ClienteVisao, VisaoIndisponivel
from app.config import Settings, get_settings
from app.deps import get_visao
from app.erros import ErroApi
from app.schemas.comum import Erro
from app.schemas.deteccoes import Deteccao
from app.seguranca import exigir_token_servico
from app.services import imagens

router = APIRouter(tags=["Deteccoes"])


@router.post(
    "/deteccoes",
    response_model=list[Deteccao],
    operation_id="detectarProblemas",
    summary="Detecta problemas de calçada em uma imagem",
    dependencies=[Depends(exigir_token_servico)],
    responses={
        400: {"model": Erro},
        401: {"model": Erro},
        413: {"model": Erro},
        422: {"model": Erro},
        503: {"model": Erro},
    },
)
def detectar_problemas(
    imagem: Annotated[UploadFile, File(description="Imagem JPEG ou PNG, até 10 MB")],
    settings: Annotated[Settings, Depends(get_settings)],
    visao: Annotated[ClienteVisao, Depends(get_visao)],
) -> list[Deteccao]:
    dados = imagens.ler_upload(imagem, "imagem", settings.max_upload_bytes)
    limpa = imagens.limpar_imagem(dados, "imagem")
    try:
        deteccoes = visao.detectar(limpa.conteudo, limpa.content_type)
    except VisaoIndisponivel:
        # Fora do contrato rc1 (que só prevê 200/400/401/413/422): proposta de acrescentar 503.
        raise ErroApi(503, "visao_indisponivel", "O serviço de visão está indisponível no momento.") from None
    return sorted(deteccoes, key=lambda d: d.confianca, reverse=True)
