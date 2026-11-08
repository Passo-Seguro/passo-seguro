"""Configuração: .env.example carrega e só traz valores fictícios; área permitida."""

import pytest

from app.config import BoundingBox, Settings
from tests.conftest import API_DIR


def test_env_example_carrega_e_so_tem_valores_ficticios():
    config = Settings(_env_file=API_DIR / ".env.example")
    for segredo in (config.service_token, config.device_token, config.metrics_token, config.salt_autor):
        assert segredo.startswith("troque-por"), "o .env.example não pode trazer segredo de verdade"
    assert config.habilitar_rc2 is False  # a emenda rc2 só liga depois da aprovação do grupo
    assert config.caixa_permitida is not None


def test_sem_nenhuma_variavel_os_segredos_ficam_vazios():
    config = Settings(_env_file=None)
    assert (config.service_token, config.device_token, config.metrics_token, config.salt_autor) == ("", "", "", "")


def test_area_padrao_cobre_a_se_e_pinheiros_e_exclui_o_rio():
    caixa = Settings(_env_file=None).caixa_permitida
    assert caixa.contem(-23.5505, -46.6333)  # Sé
    assert caixa.contem(-23.5670, -46.6916)  # Pinheiros
    assert not caixa.contem(-22.9068, -43.1729)  # Rio de Janeiro
    assert not caixa.contem(-23.5505, -45.0)


def test_area_sem_limite_desliga_a_checagem():
    assert Settings(_env_file=None, area_permitida="sem-limite").caixa_permitida is None


@pytest.mark.parametrize("texto", ["1,2,3", "a,b,c,d", "-23.5,-46.6,-23.6,-46.5"])
def test_area_invalida_e_recusada(texto):
    with pytest.raises(ValueError):
        BoundingBox.de_texto(texto)


def test_origens_cors():
    assert Settings(_env_file=None, cors_origins="https://a.test, https://b.test").origens_cors == [
        "https://a.test",
        "https://b.test",
    ]
