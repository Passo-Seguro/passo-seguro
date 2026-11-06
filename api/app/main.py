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
from app.routers import assistente, deteccoes, painel, relatos

VERSAO_CONTRATO = "1.0.0-rc1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origens_cors,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(relatos.router)
    app.include_router(deteccoes.router)
    app.include_router(assistente.router)
    app.include_router(painel.router)

    @app.get("/saude", include_in_schema=False)
    def saude() -> dict[str, str]:
        """Verificação de vida para o Docker/orquestrador (não faz parte do contrato)."""
        return {"status": "ok"}

    # Fotos em disco (desenvolvimento). Em produção a foto sai do bucket, não daqui.
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/fotos", StaticFiles(directory=settings.media_dir), name="fotos")

    return app


app = create_app()
