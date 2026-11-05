"""Emenda rc2: GET /relatos/proximos, GET /meus-relatos e PATCH /relatos/{id}."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models import Relato
from app.seguranca import hash_autor
from tests.conftest import SAL_AUTOR, TOKEN_SERVICO

AUTOR = uuid.UUID("3f2b8c1e-7d4a-4e90-9b15-6a0c2d8e4f71")
OUTRO = uuid.UUID("9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d")
H_AUTOR = {"X-Autor-Id": str(AUTOR)}
H_TRIAGEM = {"Authorization": f"Bearer {TOKEN_SERVICO}"}
BASE = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
CENTRO = {"lat": -23.5505, "lon": -46.6333}


def _hash(autor=AUTOR):
    return hash_autor(autor, SAL_AUTOR)


def _ids_proximos(cliente, **extra):
    return [i["id"] for i in cliente.get("/relatos/proximos", params={**CENTRO, **extra}).json()]


# =========================== GET /relatos/proximos ===========================


def test_proximos_arredonda_a_3_casas_e_nao_expoe_foto_nem_descricao(client_rc2, criar_relato_db):
    criar_relato_db(lat=-23.55051234, lon=-46.63331234, descricao="segredo", categoria="buraco", confirmacoes=2)
    r = client_rc2.get("/relatos/proximos", params=CENTRO)
    assert r.status_code == 200
    (item,) = r.json()
    assert set(item) == {"id", "lat", "lon", "categoria", "status", "prioridade", "confirmacoes"}
    assert (item["lat"], item["lon"]) == (-23.551, -46.633)
    assert item["categoria"] == "buraco" and item["status"] == "novo" and item["prioridade"] is None
    assert item["confirmacoes"] == 2
    assert "segredo" not in r.text and "foto" not in r.text and "descricao" not in r.text


def test_proximos_nunca_devolve_mais_de_3_casas(client_rc2, criar_relato_db):
    for i in range(30):
        criar_relato_db(lat=-23.5505 + i * 0.000137, lon=-46.6333 - i * 0.000211)
    itens = client_rc2.get("/relatos/proximos", params={**CENTRO, "raio_m": 5000}).json()
    assert len(itens) == 30
    for item in itens:
        for campo in ("lat", "lon"):
            assert round(item[campo], 3) == item[campo]


def test_proximos_respeita_o_raio_em_metros(client_rc2, criar_relato_db):
    perto = str(criar_relato_db(lat=-23.5505, lon=-46.6333))
    a_500m = str(criar_relato_db(lat=-23.5505 + 0.0045, lon=-46.6333))  # ~500 m ao norte
    a_2km = str(criar_relato_db(lat=-23.5505 + 0.018, lon=-46.6333))  # ~2 km
    assert set(_ids_proximos(client_rc2, raio_m=100)) == {perto}
    assert set(_ids_proximos(client_rc2, raio_m=600)) == {perto, a_500m}
    assert set(_ids_proximos(client_rc2, raio_m=5000)) == {perto, a_500m, a_2km}
    # sem raio_m, o padrão é 1000 m
    assert set(client_rc2.get("/relatos/proximos", params=CENTRO).json()[i]["id"] for i in range(2)) == {perto, a_500m}


def test_proximos_ordena_do_mais_proximo_ao_mais_distante(client_rc2, criar_relato_db):
    longe = str(criar_relato_db(lat=-23.5505 + 0.008, lon=-46.6333))
    perto = str(criar_relato_db(lat=-23.5505 + 0.001, lon=-46.6333))
    meio = str(criar_relato_db(lat=-23.5505 + 0.004, lon=-46.6333))
    assert _ids_proximos(client_rc2) == [perto, meio, longe]


def test_proximos_exclui_rejeitados_e_inclui_os_outros_status(client_rc2, criar_relato_db):
    for s in ("novo", "revisao_humana", "validado", "encaminhado", "resolvido"):
        criar_relato_db(status=s)
    rejeitado = str(criar_relato_db(status="rejeitado"))
    ids = _ids_proximos(client_rc2)
    assert len(ids) == 5 and rejeitado not in ids


def test_proximos_aceita_categoria_e_prioridade_nulas(client_rc2, criar_relato_db):
    criar_relato_db(categoria=None, confianca=None)
    criar_relato_db(status="encaminhado", prioridade="alta", subprefeitura="Sé")
    itens = client_rc2.get("/relatos/proximos", params=CENTRO).json()
    assert {i["prioridade"] for i in itens} == {None, "alta"}
    assert {i["categoria"] for i in itens} == {None, "buraco"}


def test_proximos_lista_vazia(client_rc2):
    assert client_rc2.get("/relatos/proximos", params=CENTRO).json() == []


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"lat": -23.55},
        {"lon": -46.63},
        {"lat": "x", "lon": -46.63},
        {"lat": -23.55, "lon": -46.63, "raio_m": 5001},
        {"lat": -23.55, "lon": -46.63, "raio_m": 0},
        {"lat": 95, "lon": -46.63},
    ],
)
def test_proximos_parametros_invalidos_400(client_rc2, params):
    r = client_rc2.get("/relatos/proximos", params=params)
    assert r.status_code == 400 and r.json()["codigo"] == "requisicao_invalida"


def test_proximos_fora_de_sao_paulo_422(client_rc2):
    r = client_rc2.get("/relatos/proximos", params={"lat": -22.9, "lon": -43.2})
    assert r.status_code == 422 and r.json()["codigo"] == "fora_da_area"


# =========================== GET /meus-relatos ===========================


def test_meus_relatos_so_do_autor_do_mais_recente_ao_mais_antigo(client_rc2, criar_relato_db):
    antigo = criar_relato_db(autor_hash=_hash(), criado_em=BASE)
    novo = criar_relato_db(autor_hash=_hash(), criado_em=BASE + timedelta(hours=1), categoria=None, confianca=None)
    criar_relato_db(autor_hash=_hash(OUTRO))  # de outro autor
    criar_relato_db(autor_hash=None)  # anônimo

    r = client_rc2.get("/meus-relatos", headers=H_AUTOR)

    assert r.status_code == 200
    assert [i["id"] for i in r.json()] == [str(novo), str(antigo)]
    item = r.json()[1]
    assert set(item) == {"id", "criado_em", "categoria", "status", "foto_url"}
    assert item["criado_em"] == "2026-11-04T09:00:00-03:00"
    assert item["foto_url"] == f"http://testserver/fotos/relatos/{antigo}.jpg"
    assert r.json()[0]["categoria"] is None


def test_meus_relatos_nunca_devolve_o_autor(client_rc2, criar_relato_db):
    criar_relato_db(autor_hash=_hash())
    texto = client_rc2.get("/meus-relatos", headers=H_AUTOR).text
    assert str(AUTOR) not in texto and _hash() not in texto and "autor" not in texto


def test_meus_relatos_autor_sem_relatos_e_lista_vazia(client_rc2):
    assert client_rc2.get("/meus-relatos", headers=H_AUTOR).json() == []


def test_meus_relatos_limita_a_100(client_rc2, criar_relato_db):
    for i in range(105):
        criar_relato_db(autor_hash=_hash(), criado_em=BASE + timedelta(minutes=i))
    assert len(client_rc2.get("/meus-relatos", headers=H_AUTOR).json()) == 100


def test_meus_relatos_cabecalho_ausente_ou_invalido_400(client_rc2):
    r = client_rc2.get("/meus-relatos")
    assert r.status_code == 400 and r.json()["codigo"] == "requisicao_invalida"
    assert r.json()["detalhes"][0]["campo"] == "X-Autor-Id"
    assert client_rc2.get("/meus-relatos", headers={"X-Autor-Id": "nao-e-uuid"}).status_code == 400


def test_ciclo_completo_cria_lista_e_corrige(client_rc2, jpeg):
    """O fluxo do app: reporta com o id do aparelho, vê em 'meus relatos' e corrige a categoria."""
    r = client_rc2.post(
        "/relatos",
        data={"lat": "-23.5505", "lon": "-46.6333", "fonte": "app", "autor_id": str(AUTOR)},
        files={"foto": ("f.jpg", jpeg, "image/jpeg")},
    )
    id_ = r.json()["id"]
    assert [i["id"] for i in client_rc2.get("/meus-relatos", headers=H_AUTOR).json()] == [id_]
    assert client_rc2.get("/meus-relatos", headers={"X-Autor-Id": str(OUTRO)}).json() == []
    assert (
        client_rc2.patch(f"/relatos/{id_}", json={"categoria": "obstaculo"}, headers=H_AUTOR).json()["categoria"]
        == "obstaculo"
    )
    assert client_rc2.get("/meus-relatos", headers=H_AUTOR).json()[0]["categoria"] == "obstaculo"
    assert id_ in _ids_proximos(client_rc2)


# =========================== PATCH /relatos/{id} ===========================


def _patch(cliente, id_, corpo, headers):
    return cliente.patch(f"/relatos/{id_}", json=corpo, headers=headers)


def _linha(fabrica_sessao, id_):
    with fabrica_sessao() as sessao:
        return sessao.scalars(select(Relato).where(Relato.id == id_)).one()


def test_patch_app_autor_corrige_a_categoria(client_rc2, criar_relato_db, fabrica_sessao):
    id_ = criar_relato_db(autor_hash=_hash(), categoria="buraco", confianca=0.94, descricao="d")
    r = _patch(client_rc2, id_, {"categoria": "piso_danificado"}, H_AUTOR)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["categoria"] == "piso_danificado" and corpo["confianca"] == 0.94 and corpo["status"] == "novo"
    assert corpo["id"] == str(id_) and corpo["descricao"] == "d" and "autor" not in r.text
    assert _linha(fabrica_sessao, id_).categoria == "piso_danificado"


def test_patch_app_pode_categorizar_um_relato_sem_deteccao(client_rc2, criar_relato_db):
    id_ = criar_relato_db(autor_hash=_hash(), categoria=None, confianca=None)
    assert _patch(client_rc2, id_, {"categoria": "obstaculo"}, H_AUTOR).json()["categoria"] == "obstaculo"


def test_patch_app_outro_autor_403(client_rc2, criar_relato_db, fabrica_sessao):
    id_ = criar_relato_db(autor_hash=_hash(OUTRO), categoria="buraco")
    r = _patch(client_rc2, id_, {"categoria": "obstaculo"}, H_AUTOR)
    assert r.status_code == 403 and r.json()["codigo"] == "proibido"
    assert _linha(fabrica_sessao, id_).categoria == "buraco"


def test_patch_app_relato_sem_autor_403(client_rc2, criar_relato_db):
    id_ = criar_relato_db(autor_hash=None)
    assert _patch(client_rc2, id_, {"categoria": "obstaculo"}, H_AUTOR).status_code == 403


@pytest.mark.parametrize("status", ["revisao_humana", "validado", "encaminhado", "resolvido", "rejeitado"])
def test_patch_app_so_enquanto_status_novo(client_rc2, criar_relato_db, status):
    id_ = criar_relato_db(autor_hash=_hash(), status=status)
    r = _patch(client_rc2, id_, {"categoria": "obstaculo"}, H_AUTOR)
    assert r.status_code == 403 and "novo" in r.json()["mensagem"]


@pytest.mark.parametrize(
    "corpo",
    [
        {"status": "validado"},
        {"subprefeitura": "Sé"},
        {"prioridade": "alta"},
        {"confirmacoes": 9},
        {"categoria": "buraco", "status": "validado"},
    ],
)
def test_patch_app_so_pode_mudar_categoria(client_rc2, criar_relato_db, fabrica_sessao, corpo):
    id_ = criar_relato_db(autor_hash=_hash())
    r = _patch(client_rc2, id_, corpo, H_AUTOR)
    assert r.status_code == 403
    linha = _linha(fabrica_sessao, id_)
    assert (linha.status, linha.confirmacoes, linha.prioridade, linha.subprefeitura) == ("novo", 0, None, None)


def test_patch_triagem_altera_todos_os_campos_permitidos(client_rc2, criar_relato_db, fabrica_sessao):
    id_ = criar_relato_db(categoria="buraco", autor_hash=_hash(), status="resolvido")  # triagem mexe em qualquer status
    corpo = {
        "categoria": "obstaculo",
        "status": "encaminhado",
        "subprefeitura": "Pinheiros",
        "prioridade": "media",
        "confirmacoes": 7,
    }
    r = _patch(client_rc2, id_, corpo, H_TRIAGEM)
    assert r.status_code == 200
    assert {k: r.json()[k] for k in corpo} == corpo
    linha = _linha(fabrica_sessao, id_)
    assert (linha.categoria, linha.status, linha.subprefeitura, linha.prioridade, linha.confirmacoes) == (
        "obstaculo",
        "encaminhado",
        "Pinheiros",
        "media",
        7,
    )


def test_patch_e_parcial_so_muda_o_que_foi_enviado(client_rc2, criar_relato_db):
    id_ = criar_relato_db(
        categoria="buraco", confirmacoes=4, subprefeitura="Sé", prioridade="alta", status="encaminhado"
    )
    r = _patch(client_rc2, id_, {"status": "resolvido"}, H_TRIAGEM).json()
    assert (r["status"], r["categoria"], r["confirmacoes"], r["subprefeitura"], r["prioridade"]) == (
        "resolvido",
        "buraco",
        4,
        "Sé",
        "alta",
    )


def test_patch_relato_inexistente_404(client_rc2):
    for headers in (H_AUTOR, H_TRIAGEM):
        r = _patch(client_rc2, uuid.uuid4(), {"categoria": "buraco"}, headers)
        assert r.status_code == 404 and r.json()["codigo"] == "nao_encontrado"


def test_patch_sem_credencial_401(client_rc2, criar_relato_db):
    id_ = criar_relato_db(autor_hash=_hash())
    r = _patch(client_rc2, id_, {"categoria": "buraco"}, {})
    assert r.status_code == 401 and r.json()["codigo"] == "nao_autenticado"


def test_patch_bearer_invalido_e_401_e_nao_cai_no_modo_app(client_rc2, criar_relato_db, fabrica_sessao):
    id_ = criar_relato_db(autor_hash=_hash(), categoria="buraco")
    r = _patch(client_rc2, id_, {"categoria": "obstaculo"}, {**H_AUTOR, "Authorization": "Bearer errado"})
    assert r.status_code == 401
    assert _linha(fabrica_sessao, id_).categoria == "buraco"


def test_patch_bearer_valido_vence_o_x_autor_id(client_rc2, criar_relato_db):
    id_ = criar_relato_db(autor_hash=_hash(OUTRO))
    r = _patch(client_rc2, id_, {"status": "validado"}, {**H_AUTOR, **H_TRIAGEM})
    assert r.status_code == 200  # modo triagem: o autor não importa


def test_patch_triagem_fica_fechado_sem_token_configurado(montar_cliente, settings, criar_relato_db):
    cliente = montar_cliente(settings.model_copy(update={"habilitar_rc2": True, "service_token": ""}))
    id_ = criar_relato_db()
    assert _patch(cliente, id_, {"status": "validado"}, {"Authorization": "Bearer "}).status_code == 401


@pytest.mark.parametrize(
    "corpo",
    [{}, {"campo_inventado": 1}, {"categoria": "buraco", "autor_id": "x"}, {"confirmacoes": "muitas"}],
)
def test_patch_corpo_malformado_400(client_rc2, criar_relato_db, corpo):
    id_ = criar_relato_db(autor_hash=_hash())
    r = _patch(client_rc2, id_, corpo, H_TRIAGEM)
    assert r.status_code == 400 and r.json()["codigo"] == "requisicao_invalida"


@pytest.mark.parametrize(
    "corpo",
    [
        {"categoria": "cratera"},
        {"categoria": 123},
        {"status": "perdido"},
        {"prioridade": "urgente"},
        {"confirmacoes": -1},
        {"subprefeitura": ""},
        {"subprefeitura": "x" * 101},
        {"categoria": None},
    ],
)
def test_patch_valores_invalidos_422(client_rc2, criar_relato_db, corpo):
    id_ = criar_relato_db()
    r = _patch(client_rc2, id_, corpo, H_TRIAGEM)
    assert r.status_code == 422 and r.json()["codigo"] == "dados_invalidos"


def test_patch_id_ou_cabecalho_que_nao_sao_uuid_400(client_rc2, criar_relato_db):
    assert client_rc2.patch("/relatos/nao-e-uuid", json={"categoria": "buraco"}, headers=H_TRIAGEM).status_code == 400
    id_ = criar_relato_db(autor_hash=_hash())
    assert _patch(client_rc2, id_, {"categoria": "buraco"}, {"X-Autor-Id": "x"}).status_code == 400


def test_patch_atualiza_atualizado_em(client_rc2, criar_relato_db, fabrica_sessao):
    id_ = criar_relato_db()
    antes = _linha(fabrica_sessao, id_).atualizado_em
    _patch(client_rc2, id_, {"status": "validado"}, H_TRIAGEM)
    assert _linha(fabrica_sessao, id_).atualizado_em > antes
