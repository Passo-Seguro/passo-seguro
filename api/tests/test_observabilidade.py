"""/metrics (Prometheus) e logs em JSON."""

import json
import logging
import re

import pytest
from prometheus_client.parser import text_string_to_metric_families

from app.observabilidade import FormatadorJson, configurar_logs
from tests.conftest import TOKEN_METRICAS

H_METRICAS = {"Authorization": f"Bearer {TOKEN_METRICAS}"}
ID_FIXO = "0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01"


def _amostras(cliente) -> dict[str, list]:
    texto = cliente.get("/metrics", headers=H_METRICAS).text
    return {f.name: f.samples for f in text_string_to_metric_families(texto)}


def _valor(amostras, nome, **rotulos) -> float:
    for a in amostras:
        if a.name == nome and all(a.labels.get(k) == v for k, v in rotulos.items()):
            return a.value
    return 0.0


# --- proteção do /metrics -------------------------------------------------------------


def test_metrics_exige_token(client):
    r = client.get("/metrics")
    assert r.status_code == 401 and r.json()["codigo"] == "nao_autenticado"
    assert client.get("/metrics", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN_METRICAS}x"}).status_code == 401


def test_metrics_fica_fechado_sem_token_configurado(montar_cliente, settings):
    cliente = montar_cliente(settings.model_copy(update={"metrics_token": ""}))
    assert cliente.get("/metrics").status_code == 401
    assert cliente.get("/metrics", headers={"Authorization": "Bearer "}).status_code == 401


def test_metrics_formato_prometheus(client):
    r = client.get("/metrics", headers=H_METRICAS)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "# TYPE passo_seguro_http_request_duration_seconds histogram" in r.text
    assert "# TYPE passo_seguro_http_requests_total counter" in r.text
    assert "# TYPE passo_seguro_http_requests_in_progress gauge" in r.text


def test_metrics_nao_esta_no_contrato_publico(client):
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]


# --- conteúdo das métricas ------------------------------------------------------------


def test_contador_por_rota_e_status(client, auth):
    client.get("/painel")
    client.get("/painel")
    client.get("/relatos")  # 401
    client.get("/relatos", headers=auth)  # 200
    a = _amostras(client)["passo_seguro_http_requests"]
    assert _valor(a, "passo_seguro_http_requests_total", metodo="GET", rota="/painel", status="200") == 2
    assert _valor(a, "passo_seguro_http_requests_total", metodo="GET", rota="/relatos", status="401") == 1
    assert _valor(a, "passo_seguro_http_requests_total", metodo="GET", rota="/relatos", status="200") == 1


def test_histograma_de_latencia_por_rota(client):
    client.get("/painel")
    a = _amostras(client)["passo_seguro_http_request_duration_seconds"]
    assert _valor(a, "passo_seguro_http_request_duration_seconds_count", metodo="GET", rota="/painel") == 1
    assert _valor(a, "passo_seguro_http_request_duration_seconds_sum", metodo="GET", rota="/painel") > 0
    assert _valor(a, "passo_seguro_http_request_duration_seconds_bucket", rota="/painel", le="+Inf") == 1


def test_rotulo_e_o_modelo_da_rota_nunca_o_caminho_com_id(client_rc2, criar_relato_db):
    id_real = criar_relato_db()
    for i in range(3):
        client_rc2.patch(f"/relatos/{id_real}", json={"status": "validado"}, headers={"Authorization": "Bearer errado"})
        client_rc2.patch(f"/relatos/{ID_FIXO}{i}", json={"status": "validado"})
    texto = client_rc2.get("/metrics", headers=H_METRICAS).text
    assert 'rota="/relatos/{id}"' in texto
    assert str(id_real) not in texto and ID_FIXO not in texto


def test_rotas_inexistentes_viram_desconhecida_sem_explodir_a_cardinalidade(client):
    for i in range(20):
        client.get(f"/rota-que-nao-existe-{i}")
        client.get(f"/fotos-que-nao-existem/{i}.jpg")
    texto = client.get("/metrics", headers=H_METRICAS).text
    rotas = set(re.findall(r'rota="([^"]*)"', texto))
    assert "desconhecida" in rotas
    assert not any("existe" in r for r in rotas)


def test_fotos_servidas_tem_rotulo_fixo(client, settings):
    (settings.media_dir / "relatos").mkdir(parents=True, exist_ok=True)
    (settings.media_dir / "relatos" / "a.jpg").write_bytes(b"x")
    assert client.get("/fotos/relatos/a.jpg").status_code == 200
    texto = client.get("/metrics", headers=H_METRICAS).text
    assert 'rota="/fotos/{caminho}"' in texto and "relatos/a.jpg" not in texto


def test_gauge_de_em_andamento_volta_a_zero(client):
    client.get("/painel")
    a = _amostras(client)["passo_seguro_http_requests_in_progress"]
    # a própria requisição de /metrics está em andamento quando o valor é lido
    assert _valor(a, "passo_seguro_http_requests_in_progress") == 1
    assert (
        _valor(_amostras(client)["passo_seguro_http_requests_in_progress"], "passo_seguro_http_requests_in_progress")
        == 1
    )


def test_gauge_enxerga_requisicoes_simultaneas(settings, montar_cliente):
    """Uma requisição lenta fica 'em andamento' enquanto outra lê o /metrics."""
    import threading
    import time

    cliente = montar_cliente(settings)
    liberar, dentro = threading.Event(), threading.Event()

    from app.clients import visao

    original = visao.VisaoFalsa.detectar

    def lenta(self, imagem, content_type):
        dentro.set()
        liberar.wait(5)
        return original(self, imagem, content_type)

    visao.VisaoFalsa.detectar = lenta
    try:
        from tests.conftest import gerar_imagem

        resultado = {}

        def chamar():
            resultado["r"] = cliente.post(
                "/relatos",
                data={"lat": "-23.55", "lon": "-46.63", "fonte": "app"},
                files={"foto": ("f.jpg", gerar_imagem(), "image/jpeg")},
            )

        t = threading.Thread(target=chamar)
        t.start()
        assert dentro.wait(5)
        time.sleep(0.05)
        a = _amostras(cliente)["passo_seguro_http_requests_in_progress"]
        assert _valor(a, "passo_seguro_http_requests_in_progress") == 2  # a lenta + a do /metrics
        liberar.set()
        t.join(5)
        assert resultado["r"].status_code == 201
    finally:
        visao.VisaoFalsa.detectar = original


def test_cada_app_tem_seu_proprio_registro(montar_cliente, settings):
    a, b = montar_cliente(settings), montar_cliente(settings)
    a.get("/painel")
    assert (
        _valor(
            _amostras(a)["passo_seguro_http_requests"], "passo_seguro_http_requests_total", rota="/painel", status="200"
        )
        == 1
    )
    assert (
        _valor(_amostras(b).get("passo_seguro_http_requests", []), "passo_seguro_http_requests_total", rota="/painel")
        == 0
    )


# --- logs --------------------------------------------------------------------------------


def _linhas_de_requisicao(caplog) -> list[dict]:
    formatador = FormatadorJson()
    return [json.loads(formatador.format(r)) for r in caplog.records if r.name == "passo_seguro.requisicao"]


def test_uma_linha_json_por_requisicao_so_com_campos_permitidos(client, caplog):
    caplog.set_level(logging.INFO)
    client.get("/painel")
    (linha,) = _linhas_de_requisicao(caplog)
    assert set(linha) == {"ts", "nivel", "logger", "mensagem", "metodo", "rota", "status", "duracao_ms", "request_id"}
    assert (linha["metodo"], linha["rota"], linha["status"]) == ("GET", "/painel", 200)


def test_log_nao_traz_query_string_nem_cabecalhos(client_rc2, caplog, criar_relato_db):
    criar_relato_db()
    caplog.set_level(logging.DEBUG)
    client_rc2.get(
        "/relatos/proximos", params={"lat": -23.55051234, "lon": -46.63331234}, headers={"X-Autor-Id": "x-secreto"}
    )
    client_rc2.get("/meus-relatos", headers={"X-Autor-Id": "3f2b8c1e-7d4a-4e90-9b15-6a0c2d8e4f71"})
    formatador = FormatadorJson()
    tudo = "\n".join(formatador.format(r) for r in caplog.records)
    for proibido in ("-23.5505", "-46.6333", "3f2b8c1e", "x-secreto", "lat=", "X-Autor-Id"):
        assert proibido not in tudo, proibido
    assert {linha["rota"] for linha in _linhas_de_requisicao(caplog)} == {"/relatos/proximos", "/meus-relatos"}


def test_log_usa_modelo_da_rota_e_nao_loga_saude_nem_metrics(client_rc2, caplog, criar_relato_db):
    id_ = criar_relato_db()
    caplog.set_level(logging.INFO)
    client_rc2.patch(f"/relatos/{id_}", json={"status": "validado"}, headers={"Authorization": "Bearer errado"})
    client_rc2.get("/saude")
    client_rc2.get("/metrics", headers=H_METRICAS)
    linhas = _linhas_de_requisicao(caplog)
    assert [(linha["rota"], linha["status"]) for linha in linhas] == [("/relatos/{id}", 401)]
    assert str(id_) not in json.dumps(linhas)


def test_resposta_traz_x_request_id_igual_ao_do_log(client, caplog):
    caplog.set_level(logging.INFO)
    r = client.get("/painel")
    (linha,) = _linhas_de_requisicao(caplog)
    assert r.headers["x-request-id"] == linha["request_id"]


def test_erro_interno_loga_so_tipo_e_local_nunca_a_mensagem(montar_cliente, settings, caplog, jpeg, monkeypatch):
    from app.routers import relatos as roteador

    def quebrar(*a, **k):
        raise RuntimeError("DADO-SENSIVEL-DO-CIDADAO")

    monkeypatch.setattr(roteador.servico, "criar", quebrar)
    caplog.set_level(logging.DEBUG)
    r = montar_cliente(settings, raise_server_exceptions=False).post(
        "/relatos",
        data={"lat": "-23.55", "lon": "-46.63", "fonte": "app"},
        files={"foto": ("f.jpg", jpeg, "image/jpeg")},
    )
    assert r.status_code == 500
    formatador = FormatadorJson()
    tudo = "\n".join(formatador.format(rec) for rec in caplog.records)
    assert "DADO-SENSIVEL-DO-CIDADAO" not in tudo and "DADO-SENSIVEL-DO-CIDADAO" not in r.text
    assert "RuntimeError" in tudo
    assert any(linha["status"] == 500 for linha in _linhas_de_requisicao(caplog))


def test_configurar_logs_desliga_access_log_do_uvicorn_e_silencia_httpx():
    raiz = logging.getLogger()
    antigos = (raiz.handlers[:], raiz.level, logging.getLogger("uvicorn.access").disabled)
    try:
        configurar_logs("INFO")
        assert logging.getLogger("uvicorn.access").disabled is True  # o access log traz a query string
        assert logging.getLogger("httpx").level == logging.WARNING  # o INFO do httpx traz a URL completa
        assert len(raiz.handlers) == 1 and isinstance(raiz.handlers[0].formatter, FormatadorJson)
    finally:
        raiz.handlers[:] = antigos[0]
        raiz.setLevel(antigos[1])
        logging.getLogger("uvicorn.access").disabled = antigos[2]
        logging.getLogger("httpx").setLevel(logging.NOTSET)


def test_formatador_json_ignora_campos_fora_da_lista():
    registro = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
    registro.descricao = "texto livre do cidadão"  # campo extra NÃO permitido
    registro.metodo = "GET"
    linha = json.loads(FormatadorJson().format(registro))
    assert "descricao" not in linha and linha["metodo"] == "GET"


@pytest.mark.parametrize("valor", ["texto com acento: calçada", "linha\ncom quebra"])
def test_formatador_json_gera_sempre_uma_linha(valor):
    registro = logging.LogRecord("x", logging.INFO, __file__, 1, valor, None, None)
    saida = FormatadorJson().format(registro)
    assert "\n" not in saida and json.loads(saida)["mensagem"] == valor
