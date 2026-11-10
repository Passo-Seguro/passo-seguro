"""Teste de CONTRATO: a API de verdade (uvicorn + Postgres de teste) contra o openapi.yaml.

O Schemathesis lê o contrato, gera pedidos válidos e inválidos (incluindo os exemplos do próprio
contrato) e FALHA se alguma resposta divergir: status não documentado, corpo fora do schema,
tipo de conteúdo errado, erro 500, endpoint protegido que aceita pedido sem credencial etc.

Qual contrato? Por padrão o `openapi.yaml` da raiz. Para conferir outro (ex.: a emenda rc2
ainda não aprovada), aponte OPENAPI_PATH para o arquivo. A emenda rc2 da API é ligada
automaticamente quando o contrato tem o caminho /meus-relatos.

Rodar só este teste:  pytest tests/test_contrato.py
Mais exemplos por endpoint:  CONTRATO_MAX_EXEMPLOS=200 pytest tests/test_contrato.py
"""

import os
import socket
import threading
import time
from io import BytesIO
from pathlib import Path

import pytest
import schemathesis
import uvicorn
import yaml
from PIL import Image
from schemathesis import checks as sc

from app.config import Settings
from app.db.session import get_db
from app.main import create_app
from tests.conftest import (
    SAL_AUTOR,
    TOKEN_DISPOSITIVO,
    TOKEN_METRICAS,
    TOKEN_SERVICO,
    URL_TESTE,
)

RAIZ = Path(__file__).resolve().parents[2]
OPENAPI = Path(os.environ.get("OPENAPI_PATH", RAIZ / "openapi.yaml"))
MAX_EXEMPLOS = int(os.environ.get("CONTRATO_MAX_EXEMPLOS", "40"))

pytestmark = pytest.mark.skipif(not OPENAPI.exists(), reason="openapi.yaml fora do alcance")


def _jpeg_valido() -> bytes:
    saida = BytesIO()
    Image.new("RGB", (32, 24), (90, 120, 200)).save(saida, "JPEG")
    return saida.getvalue()


JPEG = _jpeg_valido()


@schemathesis.hook
def map_body(context, body):
    """Metade das fotos geradas vira um JPEG de verdade, para exercitar também o caminho de sucesso."""
    if isinstance(body, dict):
        for campo in ("foto", "imagem"):
            valor = body.get(campo)
            if isinstance(valor, bytes) and len(valor) % 2 == 0:
                body[campo] = JPEG
    return body


@pytest.fixture(scope="module")
def servidor(tmp_path_factory, engine_banco):
    """Sobe a API de verdade (uvicorn) numa porta livre, ligada ao banco de teste."""
    contrato = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    rc2 = "/meus-relatos" in contrato["paths"]
    config = Settings(
        _env_file=None,
        database_url=URL_TESTE,
        service_token=TOKEN_SERVICO,
        device_token=TOKEN_DISPOSITIVO,
        metrics_token=TOKEN_METRICAS,
        salt_autor=SAL_AUTOR,
        media_dir=tmp_path_factory.mktemp("fotos"),
        public_base_url="http://127.0.0.1",
        use_fake_visao=True,
        use_fake_assistente=True,
        painel_json_path=RAIZ / "docs" / "exemplos" / "vw_prioridades.json",
        habilitar_rc2=rc2,
    )
    from app.config import get_settings

    aplicacao = create_app(config)
    aplicacao.dependency_overrides[get_settings] = lambda: config
    from sqlalchemy.orm import sessionmaker

    fabrica = sessionmaker(bind=engine_banco, expire_on_commit=False)

    def _db():
        with fabrica() as sessao:
            yield sessao

    aplicacao.dependency_overrides[get_db] = _db

    soquete = socket.socket()
    soquete.bind(("127.0.0.1", 0))
    porta = soquete.getsockname()[1]
    servidor_uvicorn = uvicorn.Server(uvicorn.Config(aplicacao, log_config=None, access_log=False, lifespan="off"))
    thread = threading.Thread(target=servidor_uvicorn.run, kwargs={"sockets": [soquete]}, daemon=True)
    thread.start()
    for _ in range(100):
        if servidor_uvicorn.started:
            break
        time.sleep(0.05)
    assert servidor_uvicorn.started, "a API de teste não subiu"
    yield f"http://127.0.0.1:{porta}", rc2
    servidor_uvicorn.should_exit = True
    thread.join(5)


@pytest.fixture(scope="module")
def api_schema(servidor, engine_banco):
    url, _ = servidor
    schema = schemathesis.openapi.from_path(OPENAPI)
    schema.config.update(
        base_url=url,
        headers={"Authorization": f"Bearer {TOKEN_SERVICO}", "X-Device-Token": TOKEN_DISPOSITIVO},
        request_timeout=20,
    )
    schema.config.generation.update(max_examples=MAX_EXEMPLOS)
    return schema


lazy_schema = schemathesis.pytest.from_fixture("api_schema")

# Conferências aplicadas a cada pedido. Todas as respostas precisam bater com o contrato e a API
# nunca pode devolver 500, nem a pedidos inválidos.
CONFERENCIAS = [
    sc.not_a_server_error,
    sc.status_code_conformance,
    sc.content_type_conformance,
    sc.response_headers_conformance,
    sc.response_schema_conformance,
    sc.negative_data_rejection,
    sc.ignored_auth,
]


@lazy_schema.parametrize()
def test_a_api_cumpre_o_contrato(case):
    case.call_and_validate(checks=CONFERENCIAS)
