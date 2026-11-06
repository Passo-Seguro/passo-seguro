"""`relatos.modo_deteccao`: como a categoria foi obtida (real, fake ou nenhuma).

Coluna INTERNA: serve para achar e apagar relatos criados sob visão fake. Não entra no
contrato nem em nenhuma resposta.
"""

import httpx
import pytest
import respx
from sqlalchemy import select, text

from app.db.models import Relato
from app.dominio import ModoDeteccao
from app.services import simulacao
from app.services.simulacao import AREAS_NOMEADAS, DISTRIBUICAO_CLASSES_PADRAO
from tests.conftest import API_DIR

URL_VISAO = "http://visao.invalid"
FORM = {"lat": "-23.5505", "lon": "-46.6333", "fonte": "app"}
DETECCAO = {"classe": "buraco", "confianca": 0.91, "caixa": {"x": 0.1, "y": 0.2, "largura": 0.3, "altura": 0.3}}


def _config_real(settings):
    return settings.model_copy(update={"use_fake_visao": False, "visao_url": URL_VISAO})


def _gravado(fabrica_sessao) -> Relato:
    with fabrica_sessao() as sessao:
        return sessao.scalars(select(Relato)).one()


def _postar(cliente, jpeg):
    return cliente.post("/relatos", data=FORM, files={"foto": ("f.jpg", jpeg, "image/jpeg")})


# --- os três casos ---------------------------------------------------------------------


def test_visao_real_respondeu_grava_real(montar_cliente, settings, fabrica_sessao, jpeg):
    with respx.mock() as mock:
        mock.post(f"{URL_VISAO}/deteccoes").mock(return_value=httpx.Response(200, json=[DETECCAO]))
        r = _postar(montar_cliente(_config_real(settings)), jpeg)
    assert r.status_code == 201 and r.json()["categoria"] == "buraco"
    assert _gravado(fabrica_sessao).modo_deteccao == "real"


def test_visao_fake_respondeu_grava_fake(client, fabrica_sessao, jpeg):  # a fixture `client` usa a visão fake
    r = _postar(client, jpeg)
    assert r.status_code == 201 and r.json()["categoria"] is not None
    assert _gravado(fabrica_sessao).modo_deteccao == "fake"


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, json=[]),  # a visão respondeu, mas não detectou nada
        httpx.Response(500),  # erro do serviço
        httpx.Response(200, json=[{"classe": "gato", "confianca": 2}]),  # fora do contrato
        httpx.ConnectError("sem rede"),  # fora do ar
    ],
    ids=["nao-detectou-nada", "erro-500", "resposta-invalida", "fora-do-ar"],
)
def test_visao_falhou_ou_nao_detectou_nada_grava_nenhuma(montar_cliente, settings, fabrica_sessao, jpeg, resposta):
    with respx.mock() as mock:
        rota = mock.post(f"{URL_VISAO}/deteccoes")
        rota.mock(side_effect=resposta) if isinstance(resposta, Exception) else rota.mock(return_value=resposta)
        r = _postar(montar_cliente(_config_real(settings)), jpeg)
    assert r.status_code == 201 and r.json()["categoria"] is None and r.json()["confianca"] is None
    assert _gravado(fabrica_sessao).modo_deteccao == "nenhuma"


def test_sem_visao_configurada_grava_nenhuma(montar_cliente, settings, fabrica_sessao, jpeg):
    sem_visao = settings.model_copy(update={"use_fake_visao": False, "visao_url": ""})
    assert _postar(montar_cliente(sem_visao), jpeg).status_code == 201
    assert _gravado(fabrica_sessao).modo_deteccao == "nenhuma"


def test_fake_que_nao_detecta_nada_tambem_grava_nenhuma(client, fabrica_sessao, jpeg, monkeypatch):
    from app.clients import visao

    monkeypatch.setattr(visao.VisaoFalsa, "detectar", lambda self, imagem, content_type: [])
    assert _postar(client, jpeg).status_code == 201
    assert _gravado(fabrica_sessao).modo_deteccao == "nenhuma"


# --- simulados ---------------------------------------------------------------------------


def test_relatos_do_script_de_simulacao_sao_simulados_e_modo_nenhuma(fabrica_sessao):
    from datetime import UTC, datetime

    linhas = simulacao.gerar_relatos(
        40,
        [AREAS_NOMEADAS["se"]],
        DISTRIBUICAO_CLASSES_PADRAO,
        seed=3,
        referencia=datetime(2026, 11, 5, 12, 0, tzinfo=UTC),
    )
    with fabrica_sessao() as sessao:
        assert simulacao.inserir_relatos(sessao, linhas) == 40
        gravados = sessao.scalars(select(Relato)).all()
    assert len(gravados) == 40
    assert {(r.simulado, r.modo_deteccao) for r in gravados} == {(True, "nenhuma")}


# --- o dado é interno ---------------------------------------------------------------------


def test_modo_deteccao_nao_aparece_em_nenhuma_resposta(client_rc2, fabrica_sessao, criar_relato_db, jpeg, auth):
    criar_relato_db(modo_deteccao="fake")
    r = _postar(client_rc2, jpeg)
    textos = [
        r.text,
        client_rc2.get("/relatos", headers=auth).text,
        client_rc2.get("/relatos/proximos", params={"lat": -23.5505, "lon": -46.6333, "raio_m": 5000}).text,
    ]
    for texto in textos:
        assert "modo_deteccao" not in texto


def test_modo_deteccao_nao_esta_no_openapi_gerado_nem_no_contrato(client):
    assert "modo_deteccao" not in client.get("/openapi.json").text
    contrato = (API_DIR.parent / "openapi.yaml").read_text(encoding="utf-8")
    assert "modo_deteccao" not in contrato


# --- banco -------------------------------------------------------------------------------


def test_banco_recusa_valor_fora_de_real_fake_nenhuma(fabrica_sessao):
    from sqlalchemy.exc import IntegrityError

    with fabrica_sessao() as sessao:
        with pytest.raises(IntegrityError):
            sessao.execute(
                text(
                    "INSERT INTO relatos (id, localizacao, foto_chave, fonte, modo_deteccao) "
                    "VALUES (gen_random_uuid(), ST_GeogFromText('SRID=4326;POINT(-46.6 -23.5)'), "
                    "'x.jpg', 'app', 'talvez')"
                )
            )


def test_relato_sem_o_campo_assume_nenhuma(fabrica_sessao):
    with fabrica_sessao() as sessao:
        sessao.execute(
            text(
                "INSERT INTO relatos (id, localizacao, foto_chave, fonte) "
                "VALUES (gen_random_uuid(), ST_GeogFromText('SRID=4326;POINT(-46.6 -23.5)'), 'x.jpg', 'app')"
            )
        )
        sessao.commit()
        assert sessao.scalars(select(Relato)).one().modo_deteccao == ModoDeteccao.NENHUMA.value


# --- a consulta documentada em docs/modo-deteccao.md funciona -------------------------------


def test_sql_da_documentacao_acha_so_os_relatos_criados_sob_fake(fabrica_sessao, criar_relato_db, client, jpeg):
    criar_relato_db(modo_deteccao="real")
    criar_relato_db(modo_deteccao="nenhuma")
    _postar(client, jpeg)  # um criado sob fake pela API
    with fabrica_sessao() as sessao:
        achados = sessao.execute(text("SELECT id FROM relatos WHERE modo_deteccao = 'fake' AND NOT simulado")).all()
    assert len(achados) == 1
