"""As classes do código, de contratos/classes.yaml e do openapi.yaml precisam ser iguais."""

from pathlib import Path

import pytest
import yaml

from app.dominio import Categoria, FonteRelato, Prioridade, StatusRelato

RAIZ = Path(__file__).resolve().parents[2]
CLASSES = RAIZ / "contratos" / "classes.yaml"
OPENAPI = RAIZ / "openapi.yaml"

pytestmark = pytest.mark.skipif(not (CLASSES.exists() and OPENAPI.exists()), reason="contratos fora do alcance")


def _openapi() -> dict:
    return yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))


def test_categorias_iguais_as_classes_yaml_e_na_mesma_ordem():
    classes = yaml.safe_load(CLASSES.read_text(encoding="utf-8"))["classes"]
    assert [c["nome"] for c in classes] == [c.value for c in Categoria]
    assert [c["id"] for c in classes] == list(range(len(classes)))


def test_enums_iguais_aos_do_openapi():
    schemas = _openapi()["components"]["schemas"]
    assert schemas["Categoria"]["enum"] == [c.value for c in Categoria]
    assert schemas["StatusRelato"]["enum"] == [s.value for s in StatusRelato]
    assert schemas["Prioridade"]["enum"] == [p.value for p in Prioridade]
    assert schemas["FonteRelato"]["enum"] == [f.value for f in FonteRelato]
