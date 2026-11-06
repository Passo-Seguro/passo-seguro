"""Gerador de dados simulados: parte pura (sem banco). A parte com banco fica em test_banco_*.py."""

from collections import Counter
from datetime import UTC, datetime

import pytest

from app.dominio import Categoria
from app.services import simulacao
from app.services.simulacao import AREAS_NOMEADAS, DISTRIBUICAO_CLASSES_PADRAO, Area

REF = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
AREAS = [AREAS_NOMEADAS["se"], AREAS_NOMEADAS["pinheiros"]]


def _gerar(n=400, seed=42, areas=AREAS, dist=DISTRIBUICAO_CLASSES_PADRAO):
    return simulacao.gerar_relatos(n, areas, dist, seed, REF)


def _lat_lon(linha):
    # WKTElement guarda 'POINT(lon lat)'
    lon, lat = linha["localizacao"].data[len("POINT(") : -1].split()
    return float(lat), float(lon)


def test_quantidade_exata():
    assert len(_gerar(0)) == 0
    assert len(_gerar(37)) == 37


def test_mesma_semente_mesmos_dados():
    a, b = _gerar(50, seed=1), _gerar(50, seed=1)
    assert [x["id"] for x in a] == [x["id"] for x in b]
    assert [x["descricao"] for x in a] == [x["descricao"] for x in b]
    assert [x["id"] for x in a] != [x["id"] for x in _gerar(50, seed=2)]


def test_ids_unicos_e_marcados_como_simulados():
    linhas = _gerar()
    assert len({x["id"] for x in linhas}) == len(linhas)
    assert all(x["simulado"] is True for x in linhas)


def test_pontos_ficam_dentro_das_areas():
    for linha in _gerar():
        lat, lon = _lat_lon(linha)
        assert any(a.lat_min <= lat <= a.lat_max and a.lon_min <= lon <= a.lon_max for a in AREAS)


def test_area_personalizada_e_respeitada():
    mooca = Area("Mooca", -23.57, -46.615, -23.54, -46.58)
    for linha in _gerar(200, areas=[mooca]):
        lat, lon = _lat_lon(linha)
        assert mooca.lat_min <= lat <= mooca.lat_max and mooca.lon_min <= lon <= mooca.lon_max
        assert linha["subprefeitura"] in (None, "Mooca")


def test_distribuicao_de_classes_segue_os_pesos():
    linhas = _gerar(4000, dist={Categoria.BURACO: 90, Categoria.OBSTACULO: 10})
    contagem = Counter(x["categoria"] for x in linhas if x["categoria"])
    assert set(contagem) == {"buraco", "obstaculo"}
    assert contagem["buraco"] / sum(contagem.values()) == pytest.approx(0.9, abs=0.03)


def test_regras_de_consistencia_do_contrato():
    for x in _gerar(1000):
        # categoria e confianca andam juntas (nulas quando "a visão não detectou nada")
        assert (x["categoria"] is None) == (x["confianca"] is None)
        if x["confianca"] is not None:
            assert 0 <= x["confianca"] <= 1
        # subprefeitura e prioridade só a partir de "encaminhado"
        encaminhado = x["status"] in ("encaminhado", "resolvido")
        assert (x["subprefeitura"] is not None) == encaminhado
        assert (x["prioridade"] is not None) == encaminhado
        assert x["confirmacoes"] >= 0
        assert x["criado_em"] <= REF
        assert x["fonte"] in ("app", "robo")


def test_dados_pessoais_so_aparecem_como_falsos():
    descricoes = [x["descricao"] for x in _gerar(3000) if x["descricao"]]
    com_telefone = [d for d in descricoes if "(11)" in d]
    com_cpf = [d for d in descricoes if "CPF" in d]
    assert com_telefone and com_cpf  # existem, para a triagem poder demonstrar o mascaramento
    assert all("90000-0000" in d for d in com_telefone)
    assert all("000.000.000-00" in d for d in com_cpf)


@pytest.mark.parametrize(
    "texto",
    ["se", "SE", "pinheiros", "-23.57,-46.66,-23.52,-46.61", "Mooca:-23.57,-46.615,-23.54,-46.58"],
)
def test_ler_area_valida(texto):
    assert isinstance(simulacao.ler_area(texto), Area)


@pytest.mark.parametrize("texto", ["", "lugar-nenhum", "1,2,3", "a,b,c,d", "-23.5,-46.6,-23.6,-46.5", "95,0,96,1"])
def test_ler_area_invalida(texto):
    with pytest.raises(ValueError):
        simulacao.ler_area(texto)


def test_ler_distribuicao():
    d = simulacao.ler_distribuicao("buraco=1,piso_danificado=3")
    assert d == {Categoria.BURACO: 1, Categoria.PISO_DANIFICADO: 3}


@pytest.mark.parametrize("texto", ["buraco", "cratera=1", "buraco=x", "buraco=-1", "buraco=0"])
def test_ler_distribuicao_invalida(texto):
    with pytest.raises(ValueError):
        simulacao.ler_distribuicao(texto)
