"""POST /deteccoes: detecção de problemas em uma imagem (chamada entre serviços)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.clients.visao import ClienteVisao
from app.config import Settings, get_settings
from app.deps import get_visao
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
    responses={400: {"model": Erro}, 401: {"model": Erro}, 413: {"model": Erro}, 422: {"model": Erro}},
)
def detectar_problemas(
    imagem: Annotated[UploadFile, File(description="Imagem JPEG ou PNG, até 10 MB")],
    settings: Annotated[Settings, Depends(get_settings)],
    visao: Annotated[ClienteVisao, Depends(get_visao)],
) -> list[Deteccao]:
    dados = imagens.ler_upload(imagem, "imagem", settings.max_upload_bytes)
    limpa = imagens.limpar_imagem(dados, "imagem")
    deteccoes = visao.detectar(limpa.conteudo, limpa.content_type)
    return sorted(deteccoes, key=lambda d: d.confianca, reverse=True)
