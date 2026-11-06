"""Ponto de entrada da API Passo Seguro (FastAPI)."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings
from app.erros import (
    ErroApi,
    tratar_erro_api,
    tratar_excecao,
    tratar_http,
    tratar_validacao,
)
from app.limites import LimiteCorpoMiddleware
from app.observabilidade import Metricas, ObservabilidadeMiddleware, configurar_logs
from app.routers import assistente, deteccoes, metricas, painel, rc2, relatos

VERSAO_CONTRATO = "1.0.0-rc1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.habilitar_rc2 and not settings.salt_autor:
        raise RuntimeError("SALT_AUTOR é obrigatório quando HABILITAR_RC2=true (hash do autor_id)")
    app = FastAPI(
        title="API Passo Seguro",
        version=VERSAO_CONTRATO,
        summary="Zeladoria colaborativa de calçadas de São Paulo.",
        description="Implementação do contrato `openapi.yaml` da raiz do repositório.",
    )

    app.add_exception_handler(ErroApi, tratar_erro_api)
    app.add_exception_handler(RequestValidationError, tratar_validacao)
    app.add_exception_handler(StarletteHTTPException, tratar_http)
    app.add_exception_handler(Exception, tratar_excecao)

    app.state.metricas = Metricas()
    # O último middleware adicionado fica por fora. Ordem, de dentro para fora: limite de corpo
    # -> CORS (o 413 também leva os cabeçalhos CORS) -> observabilidade (enxerga TUDO).
    app.add_middleware(LimiteCorpoMiddleware, max_bytes=settings.max_upload_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origens_cors,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    app.add_middleware(ObservabilidadeMiddleware, metricas=app.state.metricas)

    if settings.habilitar_rc2:
        # Antes de relatos.router só por clareza: as rotas não se sobrepõem (GET /relatos/proximos
        # e PATCH /relatos/{id} não existem na rc1).
        app.include_router(rc2.router)
    app.include_router(relatos.router)
    app.include_router(deteccoes.router)
    app.include_router(assistente.router)
    app.include_router(painel.router)
    app.include_router(metricas.router)

    @app.get("/saude", include_in_schema=False)
    def saude() -> dict[str, str]:
        """Verificação de vida para o Docker/orquestrador (não faz parte do contrato)."""
        return {"status": "ok"}

    # Fotos em disco (desenvolvimento). Em produção a foto sai do bucket, não daqui.
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/fotos", StaticFiles(directory=settings.media_dir), name="fotos")

    return app


# O ponto de entrada (uvicorn app.main:app) liga os logs em JSON. create_app() não mexe nos
# logs, para os testes poderem capturá-los.
configurar_logs(get_settings().log_level)
app = create_app()
