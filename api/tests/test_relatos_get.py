"""GET /relatos: autenticação, filtros, paginação e ordem (contra o Postgres de teste)."""

from datetime import UTC, datetime, timedelta

import pytest

BASE = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _popular(criar_relato_db, n=9, **comum):
    ids = []
    for i in range(n):
        ids.append(criar_relato_db(criado_em=BASE + timedelta(minutes=i), **comum))
    return ids


# --- autenticação ----------------------------------------------------------------------


def test_exige_token(client):
    r = client.get("/relatos")
    assert r.status_code == 401
    assert r.json()["codigo"] == "nao_autenticado"
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "cabecalho", ["Bearer outro-token", "Basic dXNlcjpzZW5oYQ==", "Bearer", "token-de-servico-de-teste"]
)
def test_recusa_credenciais_erradas(client, cabecalho):
    assert client.get("/relatos", headers={"Authorization": cabecalho}).status_code == 401


def test_fica_fechado_sem_token_configurado(montar_cliente, settings, auth):
    sem_token = settings.model_copy(update={"service_token": ""})
    cliente = montar_cliente(sem_token)
    assert cliente.get("/relatos", headers=auth).status_code == 401
    assert cliente.get("/relatos", headers={"Authorization": "Bearer "}).status_code == 401


# --- conteúdo ---------------------------------------------------------------------------


def test_devolve_todos_os_campos_do_contrato(client, auth, criar_relato_db):
    criar_relato_db(
        lat=-23.5505,
        lon=-46.6333,
        criado_em=datetime(2026, 11, 4, 17, 32, 10, tzinfo=UTC),
        descricao="Buraco grande",
        categoria="buraco",
        confianca=0.94,
        fonte="robo",
        status="encaminhado",
        confirmacoes=3,
        subprefeitura="Sé",
        prioridade="alta",
    )
    item = client.get("/relatos", headers=auth).json()["itens"][0]
    assert set(item) == {
        "id", "criado_em", "lat", "lon", "foto_url", "descricao", "categoria", "confianca",
        "fonte", "status", "confirmacoes", "subprefeitura", "prioridade",
    }  # fmt: skip
    assert item["criado_em"] == "2026-11-04T14:32:10-03:00"  # fuso de São Paulo, como no contrato
    assert (item["lat"], item["lon"]) == (-23.5505, -46.6333)  # a localização exata (rota protegida)
    assert item["foto_url"] == f"http://testserver/fotos/relatos/{item['id']}.jpg"
    assert item["categoria"] == "buraco" and item["confianca"] == 0.94 and item["fonte"] == "robo"
    assert (item["status"], item["confirmacoes"], item["subprefeitura"], item["prioridade"]) == (
        "encaminhado",
        3,
        "Sé",
        "alta",
    )


def test_campos_nulos_aparecem_como_null(client, auth, criar_relato_db):
    criar_relato_db(categoria=None, confianca=None, descricao=None)
    item = client.get("/relatos", headers=auth).json()["itens"][0]
    assert item["categoria"] is None and item["confianca"] is None and item["descricao"] is None
    assert item["subprefeitura"] is None and item["prioridade"] is None


def test_nao_expoe_campos_internos(client, auth, criar_relato_db):
    criar_relato_db(autor_hash="a" * 64, simulado=True)
    texto = client.get("/relatos", headers=auth).text
    assert "autor" not in texto and "simulado" not in texto and "localizacao" not in texto


# --- paginação, ordem e filtros ----------------------------------------------------------


def test_pagina_ordenada_pelo_mais_antigo(client, auth, criar_relato_db):
    ids = _popular(criar_relato_db)
    p1 = client.get("/relatos", params={"tamanho": 5}, headers=auth).json()
    assert p1["paginacao"] == {"pagina": 1, "tamanho": 5, "total_itens": 9, "total_paginas": 2, "tem_proxima": True}
    p2 = client.get("/relatos", params={"tamanho": 5, "pagina": 2}, headers=auth).json()
    assert p2["paginacao"]["tem_proxima"] is False and len(p2["itens"]) == 4
    vistos = [i["id"] for i in p1["itens"] + p2["itens"]]
    assert vistos == [str(i) for i in ids]  # em ordem, sem repetir nem pular


def test_paginacao_estavel_com_mesmo_criado_em(client, auth, criar_relato_db):
    for _ in range(7):
        criar_relato_db(criado_em=BASE)  # empate total: o desempate por id garante estabilidade
    vistos = []
    for pagina in (1, 2, 3):
        vistos += [
            i["id"]
            for i in client.get("/relatos", params={"tamanho": 3, "pagina": pagina}, headers=auth).json()["itens"]
        ]
    assert len(vistos) == 7 and len(set(vistos)) == 7


def test_pagina_alem_do_fim_devolve_itens_vazios(client, auth, criar_relato_db):
    _popular(criar_relato_db, n=3)
    corpo = client.get("/relatos", params={"pagina": 5}, headers=auth).json()
    assert corpo["itens"] == []
    assert corpo["paginacao"] == {
        "pagina": 5,
        "tamanho": 50,
        "total_itens": 3,
        "total_paginas": 1,
        "tem_proxima": False,
    }


def test_sem_relatos(client, auth):
    assert client.get("/relatos", headers=auth).json() == {
        "itens": [],
        "paginacao": {"pagina": 1, "tamanho": 50, "total_itens": 0, "total_paginas": 0, "tem_proxima": False},
    }


def test_sem_filtro_traz_todos_os_status(client, auth, criar_relato_db):
    for s in ("novo", "revisao_humana", "validado", "encaminhado", "resolvido", "rejeitado"):
        criar_relato_db(status=s)
    assert client.get("/relatos", headers=auth).json()["paginacao"]["total_itens"] == 6


def test_filtra_por_status(client, auth, criar_relato_db):
    criar_relato_db(status="novo")
    criar_relato_db(status="novo")
    criar_relato_db(status="validado")
    corpo = client.get("/relatos", params={"status": "novo"}, headers=auth).json()
    assert corpo["paginacao"]["total_itens"] == 2 and all(i["status"] == "novo" for i in corpo["itens"])


def test_criado_desde_e_inclusivo(client, auth, criar_relato_db):
    antes = criar_relato_db(criado_em=BASE - timedelta(seconds=1))
    no_limite = criar_relato_db(criado_em=BASE)
    depois = criar_relato_db(criado_em=BASE + timedelta(hours=1))
    corpo = client.get("/relatos", params={"criado_desde": BASE.isoformat()}, headers=auth).json()
    ids = [i["id"] for i in corpo["itens"]]
    assert ids == [str(no_limite), str(depois)] and str(antes) not in ids


def test_criado_desde_entende_fuso(client, auth, criar_relato_db):
    criar_relato_db(criado_em=datetime(2026, 11, 4, 15, 0, tzinfo=UTC))  # 12h em São Paulo
    # 12:00-03:00 == 15:00Z -> inclui; 12:01-03:00 -> exclui
    assert (
        client.get("/relatos", params={"criado_desde": "2026-11-04T12:00:00-03:00"}, headers=auth).json()["paginacao"][
            "total_itens"
        ]
        == 1
    )
    assert (
        client.get("/relatos", params={"criado_desde": "2026-11-04T12:01:00-03:00"}, headers=auth).json()["paginacao"][
            "total_itens"
        ]
        == 0
    )


@pytest.mark.parametrize(
    "params",
    [
        {"tamanho": 101},
        {"tamanho": 0},
        {"pagina": 0},
        {"status": "inventado"},
        {"criado_desde": "ontem"},
        {"criado_desde": "2026-11-04T00:00:00"},
    ],
)
def test_parametros_invalidos_sao_400(client, auth, params):
    r = client.get("/relatos", params=params, headers=auth)
    assert r.status_code == 400
    assert r.json()["codigo"] == "requisicao_invalida" and r.json()["detalhes"]


def test_tamanho_100_e_aceito(client, auth):
    assert client.get("/relatos", params={"tamanho": 100}, headers=auth).status_code == 200


@pytest.mark.parametrize(
    "valor", ["0.5", "1700000000", "2026-11-04", "2026-11-04T10:00", "2026-13-45T10:00:00-03:00", "agora"]
)
def test_criado_desde_so_aceita_iso_8601_com_fuso(client, auth, valor):
    r = client.get("/relatos", params={"criado_desde": valor}, headers=auth)
    assert r.status_code == 400 and r.json()["detalhes"][0]["campo"] == "criado_desde"


def test_criado_desde_aceita_z_e_mais_sem_codificar(client, auth, criar_relato_db):
    criar_relato_db(criado_em=datetime(2026, 11, 4, 15, 0, tzinfo=UTC))
    for valor in ("2026-11-04T15:00:00Z", "2026-11-04T18:00:00+03:00", "2026-11-04T12:00:00.000-03:00"):
        assert (
            client.get("/relatos", params={"criado_desde": valor}, headers=auth).json()["paginacao"]["total_itens"] == 1
        ), valor
    # '+' cru na URL chega ao servidor como espaço; tratamos como '+'
    assert (
        client.get("/relatos?criado_desde=2026-11-04T18:00:00+03:00", headers=auth).json()["paginacao"]["total_itens"]
        == 1
    )


def test_pagina_absurda_devolve_vazio_e_nao_500(client, auth, criar_relato_db):
    criar_relato_db()
    corpo = client.get("/relatos", params={"pagina": 2**70, "tamanho": 100}, headers=auth)
    assert corpo.status_code == 200 and corpo.json()["itens"] == []
    assert corpo.json()["paginacao"]["total_itens"] == 1
