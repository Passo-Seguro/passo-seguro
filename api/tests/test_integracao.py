"""Integração com os serviços externos: visão, assistente e arquivo do painel (pipeline de dados).

Os serviços reais podem não existir ainda; aqui eles são simulados com respx (mock de HTTP).
"""

import json
import logging
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select

from app.clients.assistente import AssistenteHttp
from app.db.models import Relato
from app.observabilidade import FormatadorJson

EXEMPLO_PAINEL = Path(__file__).resolve().parents[2] / "docs" / "exemplos" / "vw_prioridades.json"
FOTO_FORM = {"lat": "-23.5505", "lon": "-46.6333", "fonte": "app"}
URL_VISAO = "http://visao.invalid"
URL_ASSISTENTE = "http://assistente.invalid"
SP156 = "https://sp156.prefeitura.sp.gov.br/"


# =============== relato -> visão (mock) -> categoria gravada ===============


def _config_visao(settings, **extra):
    return settings.model_copy(
        update={"use_fake_visao": False, "visao_url": URL_VISAO, "visao_token": "token-da-visao-de-teste", **extra}
    )


def test_relato_criado_chama_a_visao_e_grava_a_categoria(montar_cliente, settings, fabrica_sessao, jpeg):
    detectado = [
        {
            "classe": "piso_danificado",
            "confianca": 0.63,
            "caixa": {"x": 0.6, "y": 0.78, "largura": 0.3, "altura": 0.18},
        },
        {
            "classe": "veiculo_na_calcada",
            "confianca": 0.97,
            "caixa": {"x": 0.05, "y": 0.22, "largura": 0.71, "altura": 0.6},
        },
    ]
    with respx.mock(assert_all_called=True) as mock:
        rota = mock.post(f"{URL_VISAO}/deteccoes").mock(return_value=httpx.Response(200, json=detectado))
        r = montar_cliente(_config_visao(settings)).post(
            "/relatos", data=FOTO_FORM, files={"foto": ("f.jpg", jpeg, "image/jpeg")}
        )
        enviada = rota.calls.last.request

    assert r.status_code == 201
    # fica com a detecção de MAIOR confiança, mesmo que a visão devolva fora de ordem
    assert r.json() == {"id": r.json()["id"], "categoria": "veiculo_na_calcada", "confianca": 0.97, "status": "novo"}
    with fabrica_sessao() as sessao:
        linha = sessao.scalars(select(Relato)).one()
    assert (linha.categoria, linha.confianca, linha.status) == ("veiculo_na_calcada", 0.97, "novo")
    # a visão recebeu a imagem (multipart, campo `imagem`) e o token do serviço
    assert enviada.headers["authorization"] == "Bearer token-da-visao-de-teste"
    assert b'name="imagem"' in enviada.content and enviada.content.count(b"\xff\xd8") >= 1


def test_visao_lenta_estoura_o_timeout_configurado_e_o_relato_e_criado(montar_cliente, settings, jpeg):
    with respx.mock() as mock:
        mock.post(f"{URL_VISAO}/deteccoes").mock(side_effect=httpx.ReadTimeout("lenta"))
        r = montar_cliente(_config_visao(settings, visao_timeout_s=0.5)).post(
            "/relatos", data=FOTO_FORM, files={"foto": ("f.jpg", jpeg, "image/jpeg")}
        )
    assert r.status_code == 201 and r.json()["categoria"] is None


def test_usar_fake_tem_prioridade_sobre_a_url(montar_cliente, settings, jpeg):
    config = _config_visao(settings, use_fake_visao=True)
    with respx.mock(assert_all_called=False) as mock:
        rota = mock.post(f"{URL_VISAO}/deteccoes").mock(return_value=httpx.Response(500))
        r = montar_cliente(config).post("/relatos", data=FOTO_FORM, files={"foto": ("f.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 201 and r.json()["categoria"] is not None
    assert rota.call_count == 0  # nem tentou o serviço real


def test_falha_da_visao_nao_vai_para_o_log_com_dados(montar_cliente, settings, jpeg, caplog):
    caplog.set_level(logging.DEBUG)
    with respx.mock() as mock:
        mock.post(f"{URL_VISAO}/deteccoes").mock(
            side_effect=httpx.ConnectError("falhou em http://visao.invalid/deteccoes")
        )
        montar_cliente(_config_visao(settings)).post(
            "/relatos",
            data={**FOTO_FORM, "descricao": "descricao-secreta"},
            files={"foto": ("f.jpg", jpeg, "image/jpeg")},
        )
    formatador = FormatadorJson()
    registros = [json.loads(formatador.format(r)) for r in caplog.records if r.name.startswith("passo_seguro")]
    avisos = [r for r in registros if r["mensagem"] == "visao_falhou"]
    assert avisos and avisos[0]["tipo_erro"] == "ConnectError"
    assert "descricao-secreta" not in json.dumps(registros) and "visao.invalid" not in json.dumps(registros)


# =============== assistente ===============


def _config_assistente(settings, **extra):
    return settings.model_copy(update={"use_fake_assistente": False, "assistente_url": URL_ASSISTENTE, **extra})


RESPOSTA_OK = {
    "resposta": "Procure a subprefeitura da sua região pelo 156.",
    "fontes": [{"titulo": "Cartilha (exemplo)", "url": "https://documentos.exemplo.invalid/c.pdf"}],
    "confianca": 0.8,
    "recusou": False,
}


def test_assistente_http_repassa_a_pergunta_e_a_resposta(montar_cliente, settings):
    with respx.mock() as mock:
        rota = mock.post(f"{URL_ASSISTENTE}/assistente").mock(return_value=httpx.Response(200, json=RESPOSTA_OK))
        r = montar_cliente(_config_assistente(settings, assistente_token="token-do-assistente-de-teste")).post(
            "/assistente", json={"pergunta": "Quem conserta a calçada?"}
        )
        enviada = rota.calls.last.request
    assert r.status_code == 200 and r.json() == RESPOSTA_OK
    assert json.loads(enviada.content) == {"pergunta": "Quem conserta a calçada?"}
    assert enviada.headers["authorization"] == "Bearer token-do-assistente-de-teste"


def test_assistente_recusa_do_proprio_servico_e_repassada(montar_cliente, settings):
    recusa = {"resposta": "Só ajudo com calçadas.", "fontes": [], "confianca": 0.1, "recusou": True}
    with respx.mock() as mock:
        mock.post(f"{URL_ASSISTENTE}/assistente").mock(return_value=httpx.Response(200, json=recusa))
        r = montar_cliente(_config_assistente(settings)).post("/assistente", json={"pergunta": "Qual ação comprar?"})
    assert r.json() == recusa


@pytest.mark.parametrize(
    "falha",
    [
        httpx.ConnectError("recusou"),
        httpx.ReadTimeout("demorou"),
        httpx.Response(500),
        httpx.Response(503, json={"erro": "carregando modelo"}),
        httpx.Response(200, content=b"nao e json"),
        httpx.Response(200, json={"resposta": "sem os outros campos"}),
        httpx.Response(200, json={**RESPOSTA_OK, "confianca": 7}),
    ],
    ids=["conexao", "timeout", "http-500", "http-503", "nao-json", "campos-faltando", "fora-do-contrato"],
)
def test_assistente_fora_do_ar_devolve_recusa_padrao_com_link_do_sp156(montar_cliente, settings, falha):
    with respx.mock() as mock:
        rota = mock.post(f"{URL_ASSISTENTE}/assistente")
        rota.mock(side_effect=falha) if isinstance(falha, Exception) else rota.mock(return_value=falha)
        r = montar_cliente(_config_assistente(settings)).post(
            "/assistente", json={"pergunta": "Quem conserta a calçada?"}
        )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["recusou"] is True and corpo["fontes"] == [] and 0 <= corpo["confianca"] <= 1
    assert SP156 in corpo["resposta"] and "156" in corpo["resposta"]


def test_assistente_sem_url_e_sem_fake_tambem_recusa(montar_cliente, settings):
    r = montar_cliente(settings.model_copy(update={"use_fake_assistente": False, "assistente_url": ""})).post(
        "/assistente", json={"pergunta": "Quem conserta a calçada?"}
    )
    assert r.status_code == 200 and r.json()["recusou"] is True and SP156 in r.json()["resposta"]


def test_link_do_sp156_vem_de_variavel(montar_cliente, settings):
    config = settings.model_copy(update={"use_fake_assistente": False, "sp156_url": "https://sp156.exemplo.test/"})
    assert (
        "https://sp156.exemplo.test/"
        in montar_cliente(config).post("/assistente", json={"pergunta": "oi"}).json()["resposta"]
    )


def test_assistente_nao_loga_a_pergunta(montar_cliente, settings, caplog):
    caplog.set_level(logging.DEBUG)
    with respx.mock() as mock:
        mock.post(f"{URL_ASSISTENTE}/assistente").mock(side_effect=httpx.ConnectError("x"))
        montar_cliente(_config_assistente(settings)).post("/assistente", json={"pergunta": "minha-pergunta-secreta"})
    formatador = FormatadorJson()
    tudo = "\n".join(formatador.format(r) for r in caplog.records if r.name.startswith("passo_seguro"))
    assert "minha-pergunta-secreta" not in tudo and "assistente_falhou" in tudo


def test_assistente_fake_selecionavel_por_variavel(client):
    # `client` usa use_fake_assistente=True: responde sem rede alguma
    assert client.post("/assistente", json={"pergunta": "Quem conserta a calçada?"}).json()["recusou"] is False


def test_cliente_http_do_assistente_respeita_o_timeout_configurado():
    cliente = AssistenteHttp(URL_ASSISTENTE, timeout_s=3.5)
    assert cliente.cliente.timeout.read == 3.5


# =============== painel (arquivo do pipeline de dados) ===============


def _painel(montar_cliente, settings, caminho):
    return montar_cliente(settings.model_copy(update={"painel_export_path": caminho})).get("/painel")


def test_painel_le_o_arquivo_e_ordena_da_maior_para_a_menor_prioridade(montar_cliente, settings):
    r = _painel(montar_cliente, settings, EXEMPLO_PAINEL)  # no arquivo, Pinheiros vem antes de Sé
    assert r.status_code == 200
    assert [(i["subprefeitura"], i["prioridade"]) for i in r.json()] == [("Sé", "alta"), ("Pinheiros", "media")]
    assert r.json()[0]["atualizado_em"] == "2026-11-04T06:00:00-03:00"
    assert r.json()[0]["tempo_medio_ate_reparo_dias"] == 41.5 and r.json()[1]["tempo_medio_ate_reparo_dias"] is None


def test_painel_desempata_por_relatos_abertos_e_nome(montar_cliente, settings, tmp_path):
    def item(nome, prioridade, abertos):
        return {
            "subprefeitura": nome, "prioridade": prioridade, "relatos_abertos": abertos,
            "relatos_por_categoria": {"buraco": abertos}, "tempo_medio_ate_reparo_dias": None,
            "atualizado_em": "2026-11-04T06:00:00-03:00",
        }  # fmt: skip

    arquivo = tmp_path / "painel.json"
    arquivo.write_text(
        json.dumps([item("B", "baixa", 1), item("C", "alta", 5), item("A", "alta", 5), item("D", "alta", 9)])
    )
    assert [i["subprefeitura"] for i in _painel(montar_cliente, settings, arquivo).json()] == ["D", "A", "C", "B"]


def test_painel_sem_arquivo_e_404_no_formato_erro(montar_cliente, settings, tmp_path):
    for caminho in (tmp_path / "nao-existe.json", None, tmp_path):  # inexistente, não configurado, é uma pasta
        r = _painel(montar_cliente, settings, caminho)
        assert r.status_code == 404
        assert r.json() == {
            "codigo": "painel_indisponivel",
            "mensagem": "O painel de prioridades ainda não foi exportado pelo pipeline de dados.",
        }


@pytest.mark.parametrize(
    "conteudo",
    [
        "isto nao e json",
        "",
        '{"nao": "e uma lista"}',
        '[{"subprefeitura": "Sé"}]',
        '[{"subprefeitura":"Sé","prioridade":"urgente","relatos_abertos":1,"relatos_por_categoria":{},"atualizado_em":"2026-11-04T06:00:00-03:00"}]',
        '[{"subprefeitura":"Sé","prioridade":"alta","relatos_abertos":-1,"relatos_por_categoria":{},"atualizado_em":"2026-11-04T06:00:00-03:00"}]',
        '[{"subprefeitura":"Sé","prioridade":"alta","relatos_abertos":1,"relatos_por_categoria":{"cratera":1},"atualizado_em":"2026-11-04T06:00:00-03:00"}]',
    ],
)
def test_painel_arquivo_fora_do_schema_e_503_e_nao_expoe_o_conteudo(montar_cliente, settings, tmp_path, conteudo):
    arquivo = tmp_path / "painel.json"
    arquivo.write_text(conteudo, encoding="utf-8")
    r = _painel(montar_cliente, settings, arquivo)
    assert r.status_code == 503 and r.json()["codigo"] == "painel_invalido"
    assert "cratera" not in r.text and "urgente" not in r.text


def test_painel_lista_vazia_e_valida(montar_cliente, settings, tmp_path):
    arquivo = tmp_path / "painel.json"
    arquivo.write_text("[]")
    r = _painel(montar_cliente, settings, arquivo)
    assert r.status_code == 200 and r.json() == []


def test_painel_acompanha_a_troca_do_arquivo(montar_cliente, settings, tmp_path):
    arquivo = tmp_path / "painel.json"
    cliente = montar_cliente(settings.model_copy(update={"painel_export_path": arquivo}))
    assert cliente.get("/painel").status_code == 404
    arquivo.write_text(EXEMPLO_PAINEL.read_text(encoding="utf-8"), encoding="utf-8")
    assert len(cliente.get("/painel").json()) == 2
    arquivo.write_text("[]")
    assert cliente.get("/painel").json() == []
    arquivo.unlink()
    assert cliente.get("/painel").status_code == 404


def test_arquivo_de_exemplo_do_repositorio_e_valido_e_fictício():
    from app.services.painel import ler_painel

    assert len(ler_painel(EXEMPLO_PAINEL)) == 2
