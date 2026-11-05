"""Visão e assistente falsos: desligados por padrão e sempre visíveis quando ligados."""

import json
import logging

import pytest
from prometheus_client.parser import text_string_to_metric_families

from app.config import Settings
from app.main import create_app
from app.observabilidade import FormatadorJson
from tests.conftest import API_DIR, TOKEN_METRICAS

REPO = API_DIR.parent


def test_padrao_do_codigo_e_do_env_example_e_sem_fake():
    assert Settings(_env_file=None).use_fake_visao is False
    assert Settings(_env_file=None).use_fake_assistente is False
    exemplo = Settings(_env_file=API_DIR / ".env.example")
    assert exemplo.use_fake_visao is False and exemplo.use_fake_assistente is False


def test_compose_dev_nao_liga_fake_por_padrao_e_so_o_override_liga():
    base = (REPO / "docker-compose.dev.yml").read_text(encoding="utf-8")
    assert "USE_FAKE_VISAO: ${USE_FAKE_VISAO:-false}" in base
    assert "USE_FAKE_ASSISTENTE: ${USE_FAKE_ASSISTENTE:-false}" in base
    fakes = (REPO / "docker-compose.fakes.yml").read_text(encoding="utf-8")
    assert 'USE_FAKE_VISAO: "true"' in fakes and 'USE_FAKE_ASSISTENTE: "true"' in fakes


def _sem_fake(settings):
    return settings.model_copy(update={"use_fake_visao": False, "use_fake_assistente": False})


@pytest.mark.parametrize("caminho", ["/health", "/saude"])
def test_health_sem_fake(montar_cliente, settings, caminho):
    corpo = montar_cliente(_sem_fake(settings)).get(caminho).json()
    assert corpo == {"status": "ok", "modo_fake": {"visao": False, "assistente": False}, "alertas": []}


@pytest.mark.parametrize("caminho", ["/health", "/saude"])
def test_health_mostra_o_que_esta_em_fake_sem_deixar_de_responder_200(montar_cliente, settings, caminho):
    cliente = montar_cliente(_sem_fake(settings).model_copy(update={"use_fake_visao": True}))
    r = cliente.get(caminho)
    assert r.status_code == 200  # o healthcheck do Docker não pode falhar por causa disso
    assert r.json()["modo_fake"] == {"visao": True, "assistente": False}
    assert r.json()["alertas"] == ["visao: modo fake ativo"]


def test_health_com_os_dois_fakes(client):  # a fixture `client` liga os dois
    assert client.get("/health").json()["alertas"] == ["visao: modo fake ativo", "assistente: modo fake ativo"]


def test_log_de_aviso_na_subida(settings, caplog):
    caplog.set_level(logging.WARNING)
    create_app(_sem_fake(settings).model_copy(update={"use_fake_visao": True}))
    formatador = FormatadorJson()
    avisos = [json.loads(formatador.format(r)) for r in caplog.records if r.name == "passo_seguro.config"]
    assert len(avisos) == 1
    assert (
        avisos[0]["nivel"] == "WARNING" and avisos[0]["servico"] == "visao" and avisos[0]["evento"] == "modo_fake_ativo"
    )
    assert "MODO FAKE" in avisos[0]["mensagem"] and "NÃO do modelo" in avisos[0]["mensagem"]


def test_sem_fake_nao_ha_aviso(settings, caplog):
    caplog.set_level(logging.WARNING)
    create_app(_sem_fake(settings))
    assert not [r for r in caplog.records if r.name == "passo_seguro.config"]


def test_assistente_fake_tambem_avisa(settings, caplog):
    caplog.set_level(logging.WARNING)
    create_app(_sem_fake(settings).model_copy(update={"use_fake_assistente": True}))
    assert [r.servico for r in caplog.records if r.name == "passo_seguro.config"] == ["assistente"]


def test_metrica_de_modo_fake_para_alertar_no_prometheus(montar_cliente, settings):
    cliente = montar_cliente(_sem_fake(settings).model_copy(update={"use_fake_visao": True}))
    texto = cliente.get("/metrics", headers={"Authorization": f"Bearer {TOKEN_METRICAS}"}).text
    valores = {
        a.labels["servico"]: a.value
        for f in text_string_to_metric_families(texto)
        if f.name == "passo_seguro_modo_fake"
        for a in f.samples
    }
    assert valores == {"visao": 1.0, "assistente": 0.0}


def test_health_nao_gera_linha_de_log_por_requisicao(client, caplog):
    caplog.set_level(logging.INFO)
    client.get("/health")
    client.get("/saude")
    assert not [r for r in caplog.records if r.name == "passo_seguro.requisicao"]
