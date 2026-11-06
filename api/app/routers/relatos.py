"""POST /relatos e GET /relatos.

Etapa 1: o POST valida a entrada de verdade, mas NÃO grava (devolve o resultado da visão
de exemplo) e o GET lê de uma lista de exemplo. A Etapa 2 troca isso pelo banco.
"""

from datetime import datetime
from math import ceil
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.clients.visao import ClienteVisao
from app.config import Settings, get_settings
from app.deps import get_visao
from app.dominio import FonteRelato, StatusRelato
from app.erros import ErroApi
from app.schemas.comum import Erro
from app.schemas.relatos import ListaRelatos, Paginacao, RelatoCriado
from app.seguranca import exigir_token_servico
from app.services import imagens
from app.services.exemplos import RELATOS_EXEMPLO

router = APIRouter(tags=["Relatos"])

_ERROS = {400: {"model": Erro}, 401: {"model": Erro}, 413: {"model": Erro}, 422: {"model": Erro}}


def validar_coordenadas(lat: float, lon: float, settings: Settings) -> None:
    """422 se o ponto estiver fora da área de atendimento (padrão: município de São Paulo)."""
    caixa = settings.caixa_permitida
    if caixa is not None and not caixa.contem(lat, lon):
        raise ErroApi(
            422,
            "dados_invalidos",
            "Os dados enviados não são válidos.",
            [
                {
                    "campo": "lat",
                    "problema": "a localização está fora da área de atendimento (município de São Paulo)",
                }
            ],
        )


@router.post(
    "/relatos",
    status_code=201,
    response_model=RelatoCriado,
    operation_id="criarRelato",
    summary="Cria um relato de problema na calçada",
    responses={k: v for k, v in _ERROS.items() if k != 401},
)
def criar_relato(
    foto: Annotated[UploadFile, File(description="Foto JPEG ou PNG, até 10 MB")],
    lat: Annotated[float, Form(ge=-90, le=90)],
    lon: Annotated[float, Form(ge=-180, le=180)],
    fonte: Annotated[FonteRelato, Form()],
    settings: Annotated[Settings, Depends(get_settings)],
    visao: Annotated[ClienteVisao, Depends(get_visao)],
    descricao: Annotated[str | None, Form(max_length=1000)] = None,
) -> RelatoCriado:
    validar_coordenadas(lat, lon, settings)
    dados = imagens.ler_upload(foto, "foto", settings.max_upload_bytes)
    imagem = imagens.limpar_imagem(dados, "foto")
    deteccoes = visao.detectar(imagem.conteudo, imagem.content_type)
    melhor = deteccoes[0] if deteccoes else None
    return RelatoCriado(
        id=uuid4(),
        categoria=melhor.classe if melhor else None,
        confianca=melhor.confianca if melhor else None,
        status=StatusRelato.NOVO,
    )


@router.get(
    "/relatos",
    response_model=ListaRelatos,
    operation_id="listarRelatos",
    summary="Lista relatos, paginados",
    dependencies=[Depends(exigir_token_servico)],
    responses={k: v for k, v in _ERROS.items() if k in (400, 401)},
)
def listar_relatos(
    status: Annotated[StatusRelato | None, Query(description="Filtra pelo status")] = None,
    criado_desde: Annotated[datetime | None, Query(description="Só relatos criados a partir deste instante")] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListaRelatos:
    if criado_desde is not None and criado_desde.tzinfo is None:
        raise ErroApi(
            400,
            "requisicao_invalida",
            "A requisição está malformada.",
            [{"campo": "criado_desde", "problema": "deve informar o fuso, por exemplo -03:00"}],
        )
    itens = [
        r
        for r in RELATOS_EXEMPLO
        if (status is None or r.status == status) and (criado_desde is None or r.criado_em >= criado_desde)
    ]
    total = len(itens)
    inicio = (pagina - 1) * tamanho
    return ListaRelatos(
        itens=itens[inicio : inicio + tamanho],
        paginacao=Paginacao(
            pagina=pagina,
            tamanho=tamanho,
            total_itens=total,
            total_paginas=ceil(total / tamanho),
            tem_proxima=inicio + tamanho < total,
        ),
    )
