"""Fixtures compartilhadas. Nenhum teste usa segredo real: os tokens abaixo são de mentira."""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings, get_settings
from app.main import create_app

TOKEN_SERVICO = "token-de-servico-de-teste"


def gerar_imagem(formato: str = "JPEG", tamanho=(64, 48), cor=(180, 60, 60)) -> bytes:
    saida = BytesIO()
    Image.new("RGB", tamanho, cor).save(saida, formato)
    return saida.getvalue()


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
        service_token=TOKEN_SERVICO,
        media_dir=tmp_path / "fotos",
        public_base_url="http://testserver",
    )


@pytest.fixture
def app(settings: Settings):
    aplicacao = create_app(settings)
    aplicacao.dependency_overrides[get_settings] = lambda: settings
    return aplicacao


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN_SERVICO}"}
