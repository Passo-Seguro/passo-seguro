"""Os 5 endpoints originais respondendo conforme o contrato (Etapa 1: dados de exemplo)."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def _foto(jpeg: bytes, nome="foto.jpg", tipo="image/jpeg"):
    return {"foto": (nome, jpeg, tipo)}


def _form(**extra):
    base = {"lat": "-23.5505", "lon": "-46.6333", "fonte": "app"}
    base.update(extra)
    return base


# --- GET /painel -----------------------------------------------------------------------


def test_painel_devolve_prioridades(client):
    r = client.get("/painel")
    assert r.status_code == 200
    corpo = r.json()
    assert [p["subprefeitura"] for p in corpo] == ["Sé", "Pinheiros"]
    assert corpo[0]["relatos_por_categoria"].keys() == {"buraco", "piso_danificado", "obstaculo", "veiculo_na_calcada"}
    assert corpo[0]["atualizado_em"] == "2026-11-04T06:00:00-03:00"
    assert corpo[1]["tempo_medio_ate_reparo_dias"] is None


# --- GET /relatos ----------------------------------------------------------------------


def test_listar_relatos_exige_token(client):
    r = client.get("/relatos")
    assert r.status_code == 401
    assert r.json()["codigo"] == "nao_autenticado"
    assert r.headers["www-authenticate"] == "Bearer"


def test_listar_relatos_recusa_token_errado(client):
    r = client.get("/relatos", headers={"Authorization": "Bearer outro-token"})
    assert r.status_code == 401


def test_listar_relatos_recusa_esquema_diferente_de_bearer(client):
    r = client.get("/relatos", headers={"Authorization": "Basic dXNlcjpzZW5oYQ=="})
    assert r.status_code == 401


def test_listar_relatos_fica_fechado_sem_token_configurado(settings, auth):
    sem_token = settings.model_copy(update={"service_token": ""})
    app = create_app(sem_token)
    app.dependency_overrides[get_settings] = lambda: sem_token
    assert TestClient(app).get("/relatos", headers=auth).status_code == 401
    assert TestClient(app).get("/relatos", headers={"Authorization": "Bearer "}).status_code == 401


def test_listar_relatos_paginado_e_ordenado(client, auth):
    r = client.get("/relatos", params={"tamanho": 5}, headers=auth)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["paginacao"] == {"pagina": 1, "tamanho": 5, "total_itens": 9, "total_paginas": 2, "tem_proxima": True}
    datas = [i["criado_em"] for i in corpo["itens"]]
    assert datas == sorted(datas)

    r2 = client.get("/relatos", params={"tamanho": 5, "pagina": 2}, headers=auth).json()
    assert len(r2["itens"]) == 4
    assert r2["paginacao"]["tem_proxima"] is False
    ids = {i["id"] for i in corpo["itens"]} | {i["id"] for i in r2["itens"]}
    assert len(ids) == 9  # nenhuma página repete ou pula item


def test_listar_relatos_filtra_por_status_e_aceita_nulos(client, auth):
    corpo = client.get("/relatos", params={"status": "novo"}, headers=auth).json()
    assert corpo["paginacao"]["total_itens"] == 5
    assert all(i["status"] == "novo" for i in corpo["itens"])
    sem_deteccao = [i for i in corpo["itens"] if i["categoria"] is None]
    assert len(sem_deteccao) == 1 and sem_deteccao[0]["confianca"] is None
    assert all(i["subprefeitura"] is None and i["prioridade"] is None for i in corpo["itens"])


def test_listar_relatos_criado_desde(client, auth):
    corpo = client.get("/relatos", params={"criado_desde": "2026-11-04T00:00:00-03:00"}, headers=auth).json()
    assert corpo["paginacao"]["total_itens"] == 5


def test_listar_relatos_pagina_vazia(client, auth):
    corpo = client.get("/relatos", params={"status": "rejeitado"}, headers=auth).json()
    assert corpo == {
        "itens": [],
        "paginacao": {"pagina": 1, "tamanho": 50, "total_itens": 0, "total_paginas": 0, "tem_proxima": False},
    }


def test_listar_relatos_parametro_invalido_e_400(client, auth):
    for params in ({"tamanho": 101}, {"tamanho": 0}, {"pagina": 0}, {"status": "inventado"}, {"criado_desde": "ontem"}):
        r = client.get("/relatos", params=params, headers=auth)
        assert r.status_code == 400, params
        assert r.json()["codigo"] == "requisicao_invalida"
        assert r.json()["detalhes"]


def test_listar_relatos_criado_desde_sem_fuso_e_400(client, auth):
    r = client.get("/relatos", params={"criado_desde": "2026-11-04T00:00:00"}, headers=auth)
    assert r.status_code == 400
    assert r.json()["detalhes"][0]["campo"] == "criado_desde"


# --- POST /relatos ---------------------------------------------------------------------


def test_criar_relato_201(client, jpeg):
    r = client.post("/relatos", data=_form(descricao="Buraco na calçada"), files=_foto(jpeg))
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["status"] == "novo"
    assert set(corpo) == {"id", "categoria", "confianca", "status"}
    assert corpo["categoria"] in {"buraco", "piso_danificado", "obstaculo", "veiculo_na_calcada"}
    assert 0 <= corpo["confianca"] <= 1


def test_criar_relato_aceita_png(client, png):
    r = client.post("/relatos", data=_form(fonte="robo"), files=_foto(png, "foto.png", "image/png"))
    assert r.status_code == 201


def test_criar_relato_valida_tipo_pelo_conteudo(client):
    r = client.post("/relatos", data=_form(), files=_foto(b"nao sou uma imagem", "foto.jpg", "image/jpeg"))
    assert r.status_code == 422
    assert r.json() == {
        "codigo": "dados_invalidos",
        "mensagem": "Os dados enviados não são válidos.",
        "detalhes": [{"campo": "foto", "problema": "imagem ilegível ou corrompida"}],
    }


def test_criar_relato_recusa_formato_que_nao_e_jpeg_nem_png(client):
    from io import BytesIO

    from PIL import Image

    gif = BytesIO()
    Image.new("RGB", (8, 8)).save(gif, "GIF")
    r = client.post("/relatos", data=_form(), files=_foto(gif.getvalue(), "foto.jpg", "image/jpeg"))
    assert r.status_code == 422


def test_criar_relato_arquivo_vazio_e_422(client):
    r = client.post("/relatos", data=_form(), files=_foto(b""))
    assert r.status_code == 422


def test_criar_relato_arquivo_grande_e_413(settings, jpeg):
    pequeno = settings.model_copy(update={"max_upload_bytes": 100})
    app = create_app(pequeno)
    app.dependency_overrides[get_settings] = lambda: pequeno
    r = TestClient(app).post("/relatos", data=_form(), files=_foto(jpeg))
    assert r.status_code == 413
    assert r.json()["codigo"] == "arquivo_grande"


def test_criar_relato_fora_de_sao_paulo_e_422(client, jpeg):
    r = client.post("/relatos", data=_form(lat="-22.9", lon="-43.2"), files=_foto(jpeg))  # Rio de Janeiro
    assert r.status_code == 422
    assert r.json()["detalhes"][0]["campo"] == "lat"


def test_criar_relato_area_pode_ser_desligada(settings, jpeg):
    livre = settings.model_copy(update={"area_permitida": "sem-limite"})
    app = create_app(livre)
    app.dependency_overrides[get_settings] = lambda: livre
    r = TestClient(app).post("/relatos", data=_form(lat="-22.9", lon="-43.2"), files=_foto(jpeg))
    assert r.status_code == 201


def test_criar_relato_coordenada_impossivel_e_422(client, jpeg):
    r = client.post("/relatos", data=_form(lat="200"), files=_foto(jpeg))
    assert r.status_code == 422
    assert r.json()["detalhes"][0]["campo"] == "lat"


def test_criar_relato_campos_ausentes_ou_malformados_sao_400(client, jpeg):
    sem_foto = client.post("/relatos", data=_form())
    assert sem_foto.status_code == 400
    assert any(d["campo"] == "foto" for d in sem_foto.json()["detalhes"])

    lat_texto = client.post("/relatos", data=_form(lat="abc"), files=_foto(jpeg))
    assert lat_texto.status_code == 400

    sem_fonte = client.post("/relatos", data={"lat": "-23.55", "lon": "-46.63"}, files=_foto(jpeg))
    assert sem_fonte.status_code == 400


def test_criar_relato_fonte_invalida_e_422(client, jpeg):
    r = client.post("/relatos", data=_form(fonte="drone"), files=_foto(jpeg))
    assert r.status_code == 422
    assert r.json()["detalhes"][0]["campo"] == "fonte"


def test_criar_relato_descricao_longa_demais_e_422(client, jpeg):
    r = client.post("/relatos", data=_form(descricao="x" * 1001), files=_foto(jpeg))
    assert r.status_code == 422


# --- POST /deteccoes -------------------------------------------------------------------


def test_deteccoes_exige_token(client, jpeg):
    r = client.post("/deteccoes", files={"imagem": ("a.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 401


def test_deteccoes_devolve_lista_com_caixa_normalizada(client, auth, jpeg):
    r = client.post("/deteccoes", files={"imagem": ("a.jpg", jpeg, "image/jpeg")}, headers=auth)
    assert r.status_code == 200
    lista = r.json()
    assert isinstance(lista, list) and lista
    d = lista[0]
    assert d["classe"] in {"buraco", "piso_danificado", "obstaculo", "veiculo_na_calcada"}
    assert all(0 <= d["caixa"][k] <= 1 for k in ("x", "y", "largura", "altura"))
    assert lista == sorted(lista, key=lambda x: x["confianca"], reverse=True)


def test_deteccoes_e_deterministica_para_a_mesma_imagem(client, auth, jpeg):
    um = client.post("/deteccoes", files={"imagem": ("a.jpg", jpeg, "image/jpeg")}, headers=auth).json()
    dois = client.post("/deteccoes", files={"imagem": ("a.jpg", jpeg, "image/jpeg")}, headers=auth).json()
    assert um == dois


def test_deteccoes_imagem_ilegivel_e_422(client, auth):
    r = client.post("/deteccoes", files={"imagem": ("a.jpg", b"lixo", "image/jpeg")}, headers=auth)
    assert r.status_code == 422
    assert r.json()["detalhes"][0]["campo"] == "imagem"


def test_deteccoes_sem_arquivo_e_400(client, auth):
    r = client.post("/deteccoes", headers=auth)
    assert r.status_code == 400


# --- POST /assistente ------------------------------------------------------------------


def test_assistente_responde_com_fontes(client):
    r = client.post("/assistente", json={"pergunta": "Quem conserta uma calçada quebrada em frente ao meu prédio?"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["recusou"] is False
    assert corpo["fontes"] and corpo["fontes"][0]["titulo"]


def test_assistente_recusa_fora_do_escopo(client):
    r = client.post("/assistente", json={"pergunta": "Qual a melhor ação para investir esse mês?"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["recusou"] is True and corpo["fontes"] == []


def test_assistente_pergunta_vazia_e_422(client):
    for pergunta in ("", "   "):
        r = client.post("/assistente", json={"pergunta": pergunta})
        assert r.status_code == 422, repr(pergunta)
        assert r.json()["codigo"] == "dados_invalidos"


def test_assistente_pergunta_longa_demais_e_422(client):
    assert client.post("/assistente", json={"pergunta": "a" * 501}).status_code == 422


def test_assistente_corpo_malformado_e_400(client):
    assert client.post("/assistente", json={}).status_code == 400
    assert client.post("/assistente", json={"pergunta": 123}).status_code == 400
    assert (
        client.post("/assistente", content=b"{nao e json", headers={"Content-Type": "application/json"}).status_code
        == 400
    )


# --- gerais ----------------------------------------------------------------------------


def test_rota_inexistente_usa_o_formato_erro(client):
    r = client.get("/nao-existe")
    assert r.status_code == 404
    assert r.json() == {"codigo": "nao_encontrado", "mensagem": "Recurso não encontrado."}


def test_metodo_nao_permitido_usa_o_formato_erro(client):
    r = client.delete("/painel")
    assert r.status_code == 405
    assert r.json()["codigo"] == "metodo_nao_permitido"


def test_saude(client):
    assert client.get("/saude").json() == {"status": "ok"}


def test_json_ilegivel_usa_o_formato_erro(client):
    r = client.post("/assistente", content=b"\xff\xfe nao e utf-8", headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    assert r.json()["codigo"] == "requisicao_invalida"
    assert r.json()["detalhes"] == [{"campo": "corpo", "problema": "JSON malformado"}]
