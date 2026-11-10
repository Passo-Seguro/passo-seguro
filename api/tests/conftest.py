"""Fixtures compartilhadas.

Os testes de API usam um Postgres+PostGIS de teste (TEST_DATABASE_URL). Localmente:

    docker compose -f docker-compose.dev.yml up -d db     # na raiz do repositório
    pytest

Sem banco, os testes que precisam dele são PULADOS, a menos que EXIGIR_BANCO=1 (é o que o
CI faz: lá, banco fora do ar é falha, não "pulado").

Nenhum teste usa segredo real: os tokens e o sal abaixo são de mentira.
"""

import os
import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, func, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.db.models import Relato
from app.db.session import get_db
from app.main import create_app

API_DIR = Path(__file__).resolve().parents[1]
URL_TESTE = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://passo:passo-dev@localhost:5432/passo_seguro_test")

TOKEN_SERVICO = "token-de-servico-de-teste"
TOKEN_DISPOSITIVO = "token-do-robo-de-teste"
TOKEN_METRICAS = "token-de-metricas-de-teste"
SAL_AUTOR = "sal-de-teste-nao-usar-em-producao"


def gerar_imagem(formato: str = "JPEG", tamanho=(64, 48), cor=(180, 60, 60)) -> bytes:
    saida = BytesIO()
    Image.new("RGB", tamanho, cor).save(saida, formato)
    return saida.getvalue()


# --- banco ----------------------------------------------------------------------------


def _migrar(engine, destino: str = "head") -> None:
    cfg = Config(str(API_DIR / "alembic.ini"))
    with engine.connect() as conexao:
        cfg.attributes["connection"] = conexao
        command.upgrade(cfg, destino)
        conexao.commit()


def recriar_banco(url: str) -> None:
    """Cria o banco (se faltar) e deixa só o schema das migrações, do zero."""
    alvo = make_url(url)
    admin = create_engine(
        alvo.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5}
    )
    with admin.connect() as c:
        if not c.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": alvo.database}):
            c.execute(text(f'CREATE DATABASE "{alvo.database}"'))
    admin.dispose()
    engine = create_engine(alvo)
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    _migrar(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def engine_banco():
    try:
        recriar_banco(URL_TESTE)
    except OperationalError as erro:
        if os.environ.get("EXIGIR_BANCO"):
            raise
        pytest.skip(f"Postgres de teste indisponível ({type(erro).__name__}); suba o db do docker compose")
    engine = create_engine(URL_TESTE)
    yield engine
    engine.dispose()


@pytest.fixture
def fabrica_sessao(engine_banco):
    """sessionmaker ligado ao banco de teste, com a tabela de relatos limpa a cada teste."""
    with engine_banco.begin() as c:
        c.execute(text("TRUNCATE relatos"))
    return sessionmaker(bind=engine_banco, expire_on_commit=False)


@pytest.fixture
def criar_relato_db(fabrica_sessao):
    """Insere um relato direto no banco (sem passar pela API) e devolve o id."""

    def _criar(
        *,
        lat: float = -23.5505,
        lon: float = -46.6333,
        status: str = "novo",
        categoria: str | None = "buraco",
        confianca: float | None = 0.9,
        fonte: str = "app",
        criado_em: datetime | None = None,
        autor_hash: str | None = None,
        descricao: str | None = None,
        subprefeitura: str | None = None,
        prioridade: str | None = None,
        confirmacoes: int = 0,
        simulado: bool = False,
        modo_deteccao: str = "nenhuma",
        id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        relato_id = id or uuid.uuid4()
        with fabrica_sessao() as sessao:
            sessao.add(
                Relato(
                    id=relato_id,
                    criado_em=criado_em or datetime.now(UTC),
                    localizacao=func.ST_GeogFromText(f"SRID=4326;POINT({lon!r} {lat!r})"),
                    foto_chave=f"relatos/{relato_id}.jpg",
                    descricao=descricao,
                    categoria=categoria,
                    confianca=confianca,
                    fonte=fonte,
                    status=status,
                    confirmacoes=confirmacoes,
                    subprefeitura=subprefeitura,
                    prioridade=prioridade,
                    autor_hash=autor_hash,
                    simulado=simulado,
                    modo_deteccao=modo_deteccao,
                )
            )
            sessao.commit()
        return relato_id

    return _criar


# --- aplicação ------------------------------------------------------------------------


@pytest.fixture
def jpeg() -> bytes:
    return gerar_imagem("JPEG")


@pytest.fixture
def png() -> bytes:
    return gerar_imagem("PNG")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=URL_TESTE,
        service_token=TOKEN_SERVICO,
        device_token=TOKEN_DISPOSITIVO,
        metrics_token=TOKEN_METRICAS,
        salt_autor=SAL_AUTOR,
        media_dir=tmp_path / "fotos",
        public_base_url="http://testserver",
        use_fake_visao=True,
        use_fake_assistente=True,
        painel_json_path=API_DIR.parent / "docs" / "exemplos" / "vw_prioridades.json",
    )


@pytest.fixture
def montar_cliente(fabrica_sessao):
    """Fábrica: monta (app, TestClient) com as configurações dadas, ligados ao banco de teste."""

    def _montar(config: Settings, **opcoes) -> TestClient:
        aplicacao = create_app(config)
        aplicacao.dependency_overrides[get_settings] = lambda: config

        def _db():
            with fabrica_sessao() as sessao:
                yield sessao

        aplicacao.dependency_overrides[get_db] = _db
        return TestClient(aplicacao, **opcoes)

    return _montar


@pytest.fixture
def client(montar_cliente, settings) -> TestClient:
    """Contrato rc1 (HABILITAR_RC2=false), com visão fake."""
    return montar_cliente(settings)


@pytest.fixture
def client_rc2(montar_cliente, settings) -> TestClient:
    """Com a emenda rc2 habilitada."""
    return montar_cliente(settings.model_copy(update={"habilitar_rc2": True}))


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN_SERVICO}"}
