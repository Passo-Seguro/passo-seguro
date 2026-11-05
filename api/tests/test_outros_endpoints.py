"""POST /deteccoes, POST /assistente, GET /painel e comportamentos gerais da API."""

import httpx
import respx

from app.clients import visao


def _imagem(jpeg, nome="a.jpg"):
    return {"imagem": (nome, jpeg, "image/jpeg")}


# --- POST /deteccoes -----------------------------------------------------------------


def test_deteccoes_exige_token(client, jpeg):
    assert client.post("/deteccoes", files=_imagem(jpeg)).status_code == 401


def test_deteccoes_lista_ordenada_com_caixa_normalizada(client, auth, jpeg):
    r = client.post("/deteccoes", files=_imagem(jpeg), headers=auth)
    assert r.status_code == 200
    lista = r.json()
    d = lista[0]
    assert d["classe"] in {"buraco", "piso_danificado", "obstaculo", "veiculo_na_calcada"}
    assert all(0 <= d["caixa"][k] <= 1 for k in ("x", "y", "largura", "altura"))
    assert lista == sorted(lista, key=lambda x: x["confianca"], reverse=True)


def test_deteccoes_reordena_o_que_a_visao_devolve(client, auth, jpeg, monkeypatch):
    from app.schemas.deteccoes import Caixa, Deteccao

    caixa = Caixa(x=0, y=0, largura=0.5, altura=0.5)
    baixa, alta = (
        Deteccao(classe="buraco", confianca=0.3, caixa=caixa),
        Deteccao(classe="obstaculo", confianca=0.9, caixa=caixa),
    )
    monkeypatch.setattr(visao.VisaoFalsa, "detectar", lambda self, i, c: [baixa, alta])
    assert [d["classe"] for d in client.post("/deteccoes", files=_imagem(jpeg), headers=auth).json()] == [
        "obstaculo",
        "buraco",
    ]


def test_deteccoes_nada_detectado_e_lista_vazia(client, auth, jpeg, monkeypatch):
    monkeypatch.setattr(visao.VisaoFalsa, "detectar", lambda self, i, c: [])
    r = client.post("/deteccoes", files=_imagem(jpeg), headers=auth)
    assert r.status_code == 200 and r.json() == []


def test_deteccoes_visao_fora_do_ar_e_503_no_formato_erro(montar_cliente, settings, auth, jpeg):
    config = settings.model_copy(update={"use_fake_visao": False, "visao_url": "http://visao.invalid"})
    with respx.mock() as mock:
        mock.post("http://visao.invalid/deteccoes").mock(side_effect=httpx.ConnectError("recusou"))
        r = montar_cliente(config).post("/deteccoes", files=_imagem(jpeg), headers=auth)
    assert r.status_code == 503
    assert r.json() == {"codigo": "visao_indisponivel", "mensagem": "O serviço de visão está indisponível no momento."}


def test_deteccoes_imagem_ilegivel_422_e_sem_arquivo_400(client, auth):
    r = client.post("/deteccoes", files={"imagem": ("a.jpg", b"lixo", "image/jpeg")}, headers=auth)
    assert r.status_code == 422 and r.json()["detalhes"][0]["campo"] == "imagem"
    assert client.post("/deteccoes", headers=auth).status_code == 400


def test_deteccoes_acima_de_10_mib_413(client, auth, jpeg):
    r = client.post("/deteccoes", files=_imagem(jpeg + b"\0" * (10 * 1024 * 1024)), headers=auth)
    assert r.status_code == 413


def test_visao_http_envia_imagem_e_token_e_le_a_resposta(montar_cliente, settings, auth, jpeg):
    config = settings.model_copy(
        update={"use_fake_visao": False, "visao_url": "http://visao.invalid/", "visao_token": "token-da-visao-de-teste"}
    )
    resposta = [{"classe": "buraco", "confianca": 0.9, "caixa": {"x": 0.1, "y": 0.1, "largura": 0.2, "altura": 0.2}}]
    with respx.mock() as mock:
        rota = mock.post("http://visao.invalid/deteccoes").mock(return_value=httpx.Response(200, json=resposta))
        r = montar_cliente(config).post("/deteccoes", files=_imagem(jpeg), headers=auth)
        enviada = rota.calls.last.request
    assert r.status_code == 200 and r.json() == resposta
    assert enviada.headers["authorization"] == "Bearer token-da-visao-de-teste"
    assert b'name="imagem"' in enviada.content


# --- POST /assistente ----------------------------------------------------------------


def test_assistente_responde_com_fontes(client):
    r = client.post("/assistente", json={"pergunta": "Quem conserta uma calçada quebrada em frente ao meu prédio?"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["recusou"] is False and corpo["fontes"] and corpo["fontes"][0]["titulo"]


def test_assistente_recusa_fora_do_escopo(client):
    corpo = client.post("/assistente", json={"pergunta": "Qual a melhor ação para investir esse mês?"}).json()
    assert corpo["recusou"] is True and corpo["fontes"] == []


def test_assistente_pergunta_vazia_ou_longa_422(client):
    for pergunta in ("", "   ", "a" * 501):
        r = client.post("/assistente", json={"pergunta": pergunta})
        assert r.status_code == 422 and r.json()["codigo"] == "dados_invalidos", repr(pergunta[:5])


def test_assistente_corpo_malformado_400(client):
    assert client.post("/assistente", json={}).status_code == 400
    assert client.post("/assistente", json={"pergunta": 123}).status_code == 400
    r = client.post("/assistente", content=b"{nao e json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["detalhes"] == [{"campo": "corpo", "problema": "JSON malformado"}]


# --- GET /painel ---------------------------------------------------------------------


def test_painel_devolve_prioridades(client):
    r = client.get("/painel")
    assert r.status_code == 200
    corpo = r.json()
    assert [p["subprefeitura"] for p in corpo] == ["Sé", "Pinheiros"]
    assert corpo[0]["relatos_por_categoria"].keys() == {"buraco", "piso_danificado", "obstaculo", "veiculo_na_calcada"}
    assert corpo[0]["atualizado_em"] == "2026-11-04T06:00:00-03:00"
    assert corpo[1]["tempo_medio_ate_reparo_dias"] is None


# --- gerais --------------------------------------------------------------------------


def test_rota_inexistente_e_metodo_errado_usam_o_formato_erro(client):
    r = client.get("/nao-existe")
    assert r.status_code == 404 and r.json() == {"codigo": "nao_encontrado", "mensagem": "Recurso não encontrado."}
    r = client.delete("/painel")
    assert r.status_code == 405 and r.json()["codigo"] == "metodo_nao_permitido"


def test_saude(client):
    assert client.get("/saude").json() == {"status": "ok"}


def test_rc2_desligada_as_rotas_novas_nao_existem(client):
    assert client.get("/relatos/proximos", params={"lat": -23.55, "lon": -46.63}).status_code == 404
    assert client.get("/meus-relatos").status_code == 404
    assert (
        client.patch("/relatos/0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01", json={"categoria": "buraco"}).status_code == 404
    )


def test_cors_libera_o_app(client):
    r = client.options(
        "/relatos",
        headers={
            "Origin": "https://app.exemplo.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-autor-id",
        },
    )
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] in ("*", "https://app.exemplo.test")
