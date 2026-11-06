"""Endpoints da emenda 1.0.0-rc2 do contrato, ISOLADOS neste router.

Só são montados quando HABILITAR_RC2=true (ver main.py). Enquanto o grupo não aprovar a
emenda (PR feat/contratos-rc2), a API publica apenas os contratos da rc1.

- GET   /relatos/proximos  (público)  mapa: sem foto e sem descrição, lat/lon a 3 casas
- GET   /meus-relatos      (público)  pelo cabeçalho X-Autor-Id
- PATCH /relatos/{id}      app (X-Autor-Id) corrige a categoria; triagem (Bearer) atualiza o andamento
"""

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.deps import get_armazenamento
from app.dominio import StatusRelato
from app.erros import ErroApi
from app.routers.relatos import fora_da_area
from app.schemas.comum import Erro
from app.schemas.relatos import AtualizacaoRelato, Relato, RelatoProximo, RelatoResumo
from app.seguranca import extrair_bearer, hash_autor, nao_autenticado, tokens_iguais
from app.services import relatos as servico
from app.storage import Armazenamento

router = APIRouter(tags=["Relatos"])


@router.get(
    "/relatos/proximos",
    response_model=list[RelatoProximo],
    operation_id="listarRelatosProximos",
    summary="Lista relatos próximos de um ponto (para o mapa público)",
    responses={400: {"model": Erro}},
)
def listar_relatos_proximos(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    raio_m: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> list[RelatoProximo]:
    if fora_da_area(lat, lon, settings):
        # Fora de São Paulo o mapa simplesmente não tem relatos: lista vazia, não é erro.
        return []
    return [
        RelatoProximo(
            id=linha.relato.id,
            # LGPD: a localização pública sai arredondada a 3 casas (~100 m); a exata fica no banco.
            lat=round(linha.lat, 3),
            lon=round(linha.lon, 3),
            categoria=linha.relato.categoria,
            status=linha.relato.status,
            prioridade=linha.relato.prioridade,
            confirmacoes=linha.relato.confirmacoes,
        )
        for linha in servico.proximos(db, lat=lat, lon=lon, raio_m=raio_m)
    ]


@router.get(
    "/meus-relatos",
    response_model=list[RelatoResumo],
    operation_id="listarMeusRelatos",
    summary="Lista os relatos do próprio cidadão",
    responses={400: {"model": Erro}},
)
def listar_meus_relatos(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    armazenamento: Annotated[Armazenamento, Depends(get_armazenamento)],
    x_autor_id: Annotated[UUID, Header()],
) -> list[RelatoResumo]:
    relatos = servico.do_autor(db, hash_autor(x_autor_id, settings.salt_autor))
    return [
        RelatoResumo(
            id=r.id,
            criado_em=r.criado_em,
            categoria=r.categoria,
            status=r.status,
            foto_url=armazenamento.url(r.foto_chave),
        )
        for r in relatos
    ]


def _proibido(mensagem: str) -> ErroApi:
    return ErroApi(403, "proibido", mensagem)


@router.patch(
    "/relatos/{id}",
    response_model=Relato,
    operation_id="atualizarRelato",
    summary="Corrige um relato (app) ou atualiza o andamento (triagem)",
    responses={
        400: {"model": Erro},
        401: {"model": Erro},
        403: {"model": Erro},
        404: {"model": Erro},
        422: {"model": Erro},
    },
)
def atualizar_relato(
    id: UUID,
    corpo: AtualizacaoRelato,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    armazenamento: Annotated[Armazenamento, Depends(get_armazenamento)],
    authorization: Annotated[str | None, Header()] = None,
    x_autor_id: Annotated[UUID | None, Header()] = None,
) -> Relato:
    campos = corpo.model_dump(exclude_unset=True)
    if not campos:
        raise ErroApi(
            400,
            "requisicao_invalida",
            "A requisição está malformada.",
            [{"campo": "corpo", "problema": "envie ao menos um campo para alterar"}],
        )

    # Quem é o chamador? Se o Authorization veio, ele manda: inválido é 401 (não cai no modo app).
    if authorization is not None:
        if not tokens_iguais(settings.service_token, extrair_bearer(authorization)):
            raise nao_autenticado()
        modo_triagem = True
    elif x_autor_id is not None:
        modo_triagem = False
    else:
        raise nao_autenticado("Credencial ausente: envie Authorization (triagem) ou X-Autor-Id (app).")

    # Trava a linha: o app e a triagem podem alterar o mesmo relato ao mesmo tempo.
    linha = servico.buscar(db, id, travar=True)
    if linha is None:
        raise ErroApi(404, "nao_encontrado", "Relato não encontrado.")
    relato = linha.relato

    if not modo_triagem:
        esperado = relato.autor_hash
        recebido = hash_autor(x_autor_id, settings.salt_autor)
        if esperado is None or not hmac.compare_digest(esperado, recebido):
            raise _proibido("Este relato pertence a outro autor.")
        if set(campos) != {"categoria"}:
            raise _proibido("O app só pode alterar a categoria.")
        if relato.status != StatusRelato.NOVO.value:
            raise _proibido("A categoria só pode ser corrigida enquanto o relato está novo.")

    servico.aplicar_alteracoes(db, relato, campos)
    return servico.para_schema(linha, armazenamento)
