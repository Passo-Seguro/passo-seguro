"""GET /painel lendo o painel.json do pipeline de dados: blob (com cache), arquivo local e campos opcionais.

O blob é simulado: troca-se `_baixar_blob`, a única função que fala com o Azure, por uma falsa.
Nenhum teste faz chamada de rede nem precisa de credencial.
"""

import json
import logging
from pathlib import Path

import pytest
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ResourceNotFoundError

from app.services import painel as servico

EXEMPLO = Path(__file__).resolve().parents[2] / "docs" / "exemplos" / "vw_prioridades.json"
URL = "https://contapassoseguro.blob.core.windows.net/painel/painel.json"
EXTRAS = (
    "reclamacoes_calcada_sp156",
    "reclamacoes_guia_sarjeta_sp156",
    "atropelamentos_pedestres",
    "pedestres_mortos",
    "indice_prioridade",
)


def _item(nome="Sé", prioridade="alta", abertos=10, **extras):
    return {
        "subprefeitura": nome,
        "prioridade": prioridade,
        "relatos_abertos": abertos,
        "relatos_por_categoria": {"buraco": abertos},
        "tempo_medio_ate_reparo_dias": None,
        "atualizado_em": "2026-11-09T22:30:00-03:00",
        **extras,
    }


def _com_extras(nome, prioridade, indice):
    return _item(
        nome,
        prioridade,
        reclamacoes_calcada_sp156=282,
        reclamacoes_guia_sarjeta_sp156=122,
        atropelamentos_pedestres=89,
        pedestres_mortos=2,
        indice_prioridade=indice,
    )


def _bytes(itens) -> bytes:
    return json.dumps(itens).encode("utf-8")


class BlobFalso:
    """Troca de `_baixar_blob`: devolve o conteúdo (ou lança o erro) e conta as leituras."""

    def __init__(self, resultado):
        self.resultado = resultado
        self.chamadas: list[str] = []

    def __call__(self, url):
        self.chamadas.append(url)
        if isinstance(self.resultado, BaseException):
            raise self.resultado
        return self.resultado


@pytest.fixture(autouse=True)
def _cache_limpo():
    servico.limpar_cache()
    yield
    servico.limpar_cache()


@pytest.fixture
def relogio(monkeypatch):
    """Relógio controlável para o cache (substitui time.monotonic só no serviço do painel)."""
    agora = [1000.0]
    monkeypatch.setattr(servico.time, "monotonic", lambda: agora[0])
    return agora


@pytest.fixture
def com_blob(monkeypatch, settings, montar_cliente):
    """Devolve uma fábrica: dado o conteúdo (ou erro) do blob, monta (cliente, blob_falso)."""

    def _montar(resultado):
        blob = BlobFalso(resultado)
        monkeypatch.setattr(servico, "_baixar_blob", blob)
        config = settings.model_copy(update={"painel_blob_url": URL, "painel_json_path": None})
        return montar_cliente(config), blob

    return _montar


# =============== arquivo válido, com e sem os campos extras ===============


def test_blob_valido_com_os_campos_extras_devolve_todos(com_blob):
    cliente, _ = com_blob(_bytes([_com_extras("Sé", "alta", 0.972)]))
    r = cliente.get("/painel")
    assert r.status_code == 200
    item = r.json()[0]
    assert item["reclamacoes_calcada_sp156"] == 282
    assert item["reclamacoes_guia_sarjeta_sp156"] == 122
    assert item["atropelamentos_pedestres"] == 89
    assert item["pedestres_mortos"] == 2
    assert item["indice_prioridade"] == 0.972


def test_blob_valido_sem_os_campos_extras_continua_igual_e_sem_null(com_blob):
    cliente, _ = com_blob(_bytes([_item("Sé", "alta", 69), _item("Pinheiros", "media", 38)]))
    r = cliente.get("/painel")
    assert r.status_code == 200
    assert [i["subprefeitura"] for i in r.json()] == ["Sé", "Pinheiros"]
    for item in r.json():
        assert not set(EXTRAS) & set(item)  # ausentes, não null: no contrato não são "nullable"
        assert item["tempo_medio_ate_reparo_dias"] is None  # esse sim é nullable e continua saindo


def test_campo_extra_nulo_no_arquivo_e_tratado_como_ausente(com_blob):
    cliente, _ = com_blob(_bytes([_item(indice_prioridade=None, pedestres_mortos=None)]))
    r = cliente.get("/painel")
    assert r.status_code == 200
    assert not set(EXTRAS) & set(r.json()[0])


def test_ordena_por_indice_decrescente_antes_da_prioridade(com_blob):
    itens = [_com_extras("A", "alta", 0.2), _com_extras("B", "baixa", 0.9), _com_extras("C", "media", 0.5)]
    cliente, _ = com_blob(_bytes(itens))
    assert [i["subprefeitura"] for i in cliente.get("/painel").json()] == ["B", "C", "A"]


def test_sem_indice_ordena_pela_prioridade_e_quem_tem_indice_vem_primeiro(com_blob):
    itens = [_item("sem-baixa", "baixa", 50), _item("sem-alta", "alta", 1), _com_extras("com", "baixa", 0.1)]
    cliente, _ = com_blob(_bytes(itens))
    assert [i["subprefeitura"] for i in cliente.get("/painel").json()] == ["com", "sem-alta", "sem-baixa"]


def test_exemplo_do_repositorio_tem_os_extras_e_e_valido():
    itens = servico.ler_painel(EXEMPLO)
    assert [i.subprefeitura for i in itens] == ["Sé", "Pinheiros"]
    assert all(i.indice_prioridade is not None for i in itens)


# =============== arquivo local (desenvolvimento) ===============


def test_arquivo_local_com_e_sem_extras(montar_cliente, settings, tmp_path):
    arquivo = tmp_path / "painel.json"
    cliente = montar_cliente(settings.model_copy(update={"painel_json_path": arquivo}))
    arquivo.write_bytes(_bytes([_com_extras("Sé", "alta", 0.9)]))
    assert cliente.get("/painel").json()[0]["indice_prioridade"] == 0.9
    arquivo.write_bytes(_bytes([_item("Sé")]))  # sem cache no arquivo local: a troca aparece na hora
    assert "indice_prioridade" not in cliente.get("/painel").json()[0]


def test_a_url_do_blob_vence_o_caminho_local(monkeypatch, settings, montar_cliente):
    monkeypatch.setattr(servico, "_baixar_blob", BlobFalso(_bytes([_item("Do blob")])))
    config = settings.model_copy(update={"painel_blob_url": URL, "painel_json_path": EXEMPLO})
    assert [i["subprefeitura"] for i in montar_cliente(config).get("/painel").json()] == ["Do blob"]


# =============== cache de 10 minutos ===============


def test_cache_le_o_blob_uma_vez_em_10_minutos_e_depois_relê(com_blob, relogio):
    cliente, blob = com_blob(_bytes([_item("Sé")]))
    assert cliente.get("/painel").status_code == 200
    relogio[0] += 9 * 60 + 59
    assert cliente.get("/painel").status_code == 200
    assert blob.chamadas == [URL]

    blob.resultado = _bytes([_item("Sé"), _item("Mooca", "baixa")])
    relogio[0] += 2  # passou de 10 minutos
    assert len(cliente.get("/painel").json()) == 2
    assert len(blob.chamadas) == 2


def test_falha_fica_em_cache_so_por_30_segundos_e_depois_recupera(com_blob, relogio):
    cliente, blob = com_blob(HttpResponseError("falhou"))
    assert cliente.get("/painel").status_code == 503
    assert cliente.get("/painel").status_code == 503
    assert len(blob.chamadas) == 1  # a segunda não foi ao Storage

    blob.resultado = _bytes([_item("Sé")])
    relogio[0] += servico.TTL_FALHA_S + 1
    assert cliente.get("/painel").status_code == 200
    assert len(blob.chamadas) == 2


# =============== arquivo inválido ===============


@pytest.mark.parametrize(
    "conteudo",
    [
        b"isto nao e json",
        b"",
        b'{"nao": "e uma lista"}',
        b"\xff\xfe\x00",  # não é UTF-8
        _bytes([{"subprefeitura": "Sé"}]),
        _bytes([_item(prioridade="urgente")]),
        _bytes([_item(indice_prioridade=1.5)]),
        _bytes([_item(indice_prioridade=-0.1)]),
        _bytes([_item(atropelamentos_pedestres=-1)]),
        _bytes([_item(reclamacoes_calcada_sp156="muitas")]),
        _bytes([_item(pedestres_mortos=1.5)]),
    ],
)
def test_arquivo_invalido_e_503_e_nao_expoe_o_conteudo(com_blob, conteudo):
    cliente, _ = com_blob(conteudo)
    r = cliente.get("/painel")
    assert r.status_code == 503
    assert r.json() == {
        "codigo": "painel_invalido",
        "mensagem": "O arquivo do painel exportado pelo pipeline de dados está inválido.",
    }
    assert "urgente" not in r.text and "muitas" not in r.text


def test_arquivo_invalido_loga_o_motivo_sem_valores_nem_url(com_blob, caplog):
    segredo = "valor-sensivel-que-nao-pode-ir-ao-log"
    cliente, _ = com_blob(_bytes([_item(prioridade=segredo, indice_prioridade=1.5)]))
    with caplog.at_level(logging.ERROR, logger="passo_seguro.painel"):
        assert cliente.get("/painel").status_code == 503
    registro = next(r for r in caplog.records if r.name == "passo_seguro.painel")
    assert registro.getMessage() == "painel_fora_do_schema"
    assert registro.origem == "blob"
    assert "0.prioridade" in registro.motivo and "0.indice_prioridade" in registro.motivo
    texto = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert segredo not in texto and "contapassoseguro" not in texto


def test_arquivo_maior_que_5_mb_e_503(com_blob):
    cliente, _ = com_blob(b" " * (servico._MAX_BYTES + 1))
    assert cliente.get("/painel").status_code == 503


# =============== falha de leitura ===============


def test_blob_inexistente_e_404_painel_indisponivel(com_blob):
    cliente, _ = com_blob(ResourceNotFoundError("BlobNotFound"))
    r = cliente.get("/painel")
    assert r.status_code == 404 and r.json()["codigo"] == "painel_indisponivel"


@pytest.mark.parametrize(
    "erro",
    [
        ClientAuthenticationError("sem credencial"),
        HttpResponseError("403 AuthorizationPermissionMismatch"),
        TimeoutError("lento"),
        ConnectionError("rede"),
        ValueError("URL malformada"),
    ],
)
def test_falha_de_leitura_do_blob_e_503_painel_invalido(com_blob, erro):
    cliente, _ = com_blob(erro)
    r = cliente.get("/painel")
    assert r.status_code == 503 and r.json()["codigo"] == "painel_invalido"


def test_falha_de_leitura_loga_so_o_tipo_e_o_status(com_blob, caplog):
    cliente, _ = com_blob(HttpResponseError(f"detalhe secreto de {URL}"))
    with caplog.at_level(logging.ERROR, logger="passo_seguro.painel"):
        assert cliente.get("/painel").status_code == 503
    registro = next(r for r in caplog.records if r.name == "passo_seguro.painel")
    assert registro.getMessage() == "painel_blob_falha_http"
    assert registro.tipo_erro == "HttpResponseError" and registro.origem == "blob"
    assert "secreto" not in str(registro.__dict__) and "contapassoseguro" not in str(registro.__dict__)


def test_sem_nenhuma_origem_e_404(montar_cliente, settings):
    config = settings.model_copy(update={"painel_blob_url": "", "painel_json_path": None})
    assert montar_cliente(config).get("/painel").status_code == 404


# =============== o cliente do Azure (sem rede) ===============


class _BlobClienteFalso:
    criado_com: dict = {}

    def __init__(self, conteudo: bytes):
        self.conteudo = conteudo
        self.baixou: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download_blob(self, **kwargs):
        self.baixou = kwargs
        conteudo = self.conteudo[: kwargs["length"]]
        return type("Baixa", (), {"readall": lambda _self: conteudo})()


def test_baixar_blob_usa_default_azure_credential_sem_sas_e_limita_o_tamanho(monkeypatch):
    falso = _BlobClienteFalso(b"x" * (servico._MAX_BYTES + 100))

    def from_blob_url(url, **kwargs):
        _BlobClienteFalso.criado_com = {"url": url, **kwargs}
        return falso

    monkeypatch.setattr(servico.BlobClient, "from_blob_url", from_blob_url)
    servico._credencial.cache_clear()
    monkeypatch.setattr(servico, "DefaultAzureCredential", lambda: "credencial-falsa")
    try:
        conteudo = servico._baixar_blob(URL)
    finally:
        servico._credencial.cache_clear()

    assert _BlobClienteFalso.criado_com["url"] == URL and "?" not in URL  # sem SAS
    assert _BlobClienteFalso.criado_com["credential"] == "credencial-falsa"
    assert falso.baixou["length"] == servico._MAX_BYTES + 1  # lê no máximo 1 byte além do limite
    assert len(conteudo) == servico._MAX_BYTES + 1
