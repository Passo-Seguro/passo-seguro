"""POST /relatos e GET /relatos (contrato rc1).

Os endpoints da emenda rc2 (próximos, meus-relatos, PATCH) ficam isolados em `rc2.py`.
"""

import logging
import re
from datetime import datetime
from math import ceil
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy.orm import Session

from app.clients.visao import ClienteVisao, VisaoIndisponivel
from app.config import Settings, get_settings
from app.db.session import get_db
from app.deps import get_armazenamento, get_visao
from app.dominio import FonteRelato, ModoDeteccao, StatusRelato
from app.erros import ErroApi
from app.schemas.comum import Erro
from app.schemas.relatos import ListaRelatos, Paginacao, RelatoCriado
from app.seguranca import exigir_token_dispositivo, exigir_token_servico, hash_autor
from app.services import imagens
from app.services import relatos as servico
from app.storage import Armazenamento

log = logging.getLogger("passo_seguro.relatos")
router = APIRouter(tags=["Relatos"])


def fora_da_area(lat: float, lon: float, settings: Settings) -> bool:
    """True se o ponto estiver fora da área de atendimento (padrão: município de São Paulo)."""
    caixa = settings.caixa_permitida
    return caixa is not None and not caixa.contem(lat, lon)


def validar_coordenadas(lat: float, lon: float, settings: Settings) -> None:
    """422 `fora_da_area` se o ponto estiver fora da área (usado só em POST /relatos)."""
    if fora_da_area(lat, lon, settings):
        raise ErroApi(
            422,
            "fora_da_area",  # código próprio: o app mostra "toque no mapa dentro da cidade"
            "Os dados enviados não são válidos.",
            [
                {
                    "campo": "lat",
                    "problema": "a localização está fora da área de atendimento (município de São Paulo)",
                }
            ],
        )


# ISO 8601 com data, hora e FUSO obrigatórios. Estrito de propósito: o Pydantic aceitaria
# "0.5" como carimbo de tempo (1970), e o contrato diz `date-time`.
_DATA_HORA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?([Zz]|[+\- ]\d{2}:\d{2})$")


def _ler_data_hora(texto: str, campo: str) -> datetime:
    erro = ErroApi(
        400,
        "requisicao_invalida",
        "A requisição está malformada.",
        [
            {
                "campo": campo,
                "problema": "deve ser uma data e hora ISO 8601 com fuso, por exemplo 2026-11-04T00:00:00-03:00",
            }
        ],
    )
    if not _DATA_HORA_ISO.match(texto):
        raise erro
    # Um "+" sem codificar na URL chega como espaço (…T00:00:00+03:00 -> "… 03:00").
    normalizado = re.sub(r" (\d{2}:\d{2})$", lambda m: "+" + m.group(1), texto)
    try:
        return datetime.fromisoformat(normalizado)
    except ValueError:
        raise erro from None


@router.post(
    "/relatos",
    status_code=201,
    response_model=RelatoCriado,
    operation_id="criarRelato",
    summary="Cria um relato de problema na calçada",
    responses={400: {"model": Erro}, 401: {"model": Erro}, 413: {"model": Erro}, 422: {"model": Erro}},
)
def criar_relato(
    foto: Annotated[UploadFile, File(description="Foto JPEG ou PNG, até 10 MB")],
    lat: Annotated[float, Form(ge=-90, le=90)],
    lon: Annotated[float, Form(ge=-180, le=180)],
    fonte: Annotated[FonteRelato, Form()],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    visao: Annotated[ClienteVisao, Depends(get_visao)],
    armazenamento: Annotated[Armazenamento, Depends(get_armazenamento)],
    descricao: Annotated[str | None, Form(max_length=1000)] = None,
    # --- emenda rc2 (ignorados enquanto HABILITAR_RC2=false) ---
    autor_id: Annotated[UUID | None, Form()] = None,
    x_device_token: Annotated[str | None, Header()] = None,
) -> RelatoCriado:
    if settings.habilitar_rc2 and fonte == FonteRelato.ROBO:
        exigir_token_dispositivo(settings, x_device_token)
    validar_coordenadas(lat, lon, settings)

    dados = imagens.ler_upload(foto, "foto", settings.max_upload_bytes)
    imagem = imagens.limpar_imagem(dados, "foto")

    relato_id = uuid4()
    chave = f"relatos/{relato_id}.{imagem.extensao}"
    armazenamento.salvar(chave, imagem.conteudo, imagem.content_type)

    # A visão pode estar fora do ar ou não detectar nada: o relato NÃO se perde. Fica sem
    # categoria e sem confiança (nulos), e a triagem decide o que fazer.
    categoria = confianca = None
    modo = ModoDeteccao.NENHUMA
    try:
        deteccoes = visao.detectar(imagem.conteudo, imagem.content_type)
    except VisaoIndisponivel:
        deteccoes = []
    if deteccoes:
        categoria, confianca = deteccoes[0].classe.value, deteccoes[0].confianca
        modo = visao.modo  # real ou fake; falha ou lista vazia ficam em `nenhuma`

    autor_hash = hash_autor(autor_id, settings.salt_autor) if (settings.habilitar_rc2 and autor_id) else None
    try:
        servico.criar(
            db,
            id=relato_id,
            lat=lat,
            lon=lon,
            foto_chave=chave,
            descricao=descricao,
            fonte=fonte.value,
            categoria=categoria,
            confianca=confianca,
            autor_hash=autor_hash,
            modo_deteccao=modo,
        )
    except Exception:
        db.rollback()
        armazenamento.remover(chave)  # não deixa foto órfã
        raise

    return RelatoCriado(id=relato_id, categoria=categoria, confianca=confianca, status=StatusRelato.NOVO)


@router.get(
    "/relatos",
    response_model=ListaRelatos,
    operation_id="listarRelatos",
    summary="Lista relatos, paginados",
    dependencies=[Depends(exigir_token_servico)],
    responses={400: {"model": Erro}, 401: {"model": Erro}},
)
def listar_relatos(
    db: Annotated[Session, Depends(get_db)],
    armazenamento: Annotated[Armazenamento, Depends(get_armazenamento)],
    status: Annotated[StatusRelato | None, Query(description="Filtra pelo status")] = None,
    criado_desde: Annotated[
        str | None, Query(description="Só relatos criados a partir deste instante (ISO 8601 com fuso)")
    ] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListaRelatos:
    linhas, total = servico.listar(
        db,
        status=status.value if status else None,
        criado_desde=_ler_data_hora(criado_desde, "criado_desde") if criado_desde is not None else None,
        pagina=pagina,
        tamanho=tamanho,
    )
    return ListaRelatos(
        itens=[servico.para_schema(linha, armazenamento) for linha in linhas],
        paginacao=Paginacao(
            pagina=pagina,
            tamanho=tamanho,
            total_itens=total,
            total_paginas=ceil(total / tamanho),
            tem_proxima=pagina * tamanho < total,
        ),
    )
