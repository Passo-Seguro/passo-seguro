"""Leitura do painel de prioridades exportado pelo pipeline de dados (camada Ouro).

Duas origens, nesta ordem:
- `PAINEL_BLOB_URL`: o `painel.json` num container privado do Azure Blob Storage, lido com a
  identidade gerenciada (DefaultAzureCredential; a URL não leva SAS nem chave). O resultado
  validado fica em memória por 10 minutos; falhas ficam por 30 segundos (para um blob fora do
  ar não virar uma ida ao Storage por requisição de um endpoint público).
- `PAINEL_JSON_PATH`: arquivo local, para desenvolvimento. Relido a cada chamada (é barato e
  deixa o desenvolvedor trocar o arquivo sem esperar o cache).

Sem origem configurada ou sem o arquivo: 404 `painel_indisponivel`. Arquivo ou leitura com
problema: 503 `painel_invalido`. Em qualquer falha o log diz o motivo, sem conteúdo do arquivo.
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from azure.core.exceptions import AzureError, HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient
from pydantic import TypeAdapter, ValidationError

from app.dominio import Prioridade
from app.erros import ErroApi
from app.schemas.painel import PrioridadeSubprefeitura

log = logging.getLogger("passo_seguro.painel")
_LISTA = TypeAdapter(list[PrioridadeSubprefeitura])
_MAX_BYTES = 5 * 1024 * 1024
_ORDEM = {Prioridade.ALTA: 0, Prioridade.MEDIA: 1, Prioridade.BAIXA: 2}

TTL_SUCESSO_S = 10 * 60
TTL_FALHA_S = 30
_TIMEOUT_CONEXAO_S = 5
_TIMEOUT_LEITURA_S = 10

_trava = threading.Lock()
# url -> (vale até [monotonic], itens validados ou None, código da falha ou None)
_cache: dict[str, tuple[float, list[PrioridadeSubprefeitura] | None, str | None]] = {}


def limpar_cache() -> None:
    """Esvazia o cache em memória (usado pelos testes)."""
    with _trava:
        _cache.clear()


def _indisponivel() -> ErroApi:
    return ErroApi(
        404,
        "painel_indisponivel",
        "O painel de prioridades ainda não foi exportado pelo pipeline de dados.",
    )


def _invalido() -> ErroApi:
    return ErroApi(
        503,
        "painel_invalido",
        "O arquivo do painel exportado pelo pipeline de dados está inválido.",
    )


_ERROS = {"painel_indisponivel": _indisponivel, "painel_invalido": _invalido}


def _ordenar(itens: list[PrioridadeSubprefeitura]) -> list[PrioridadeSubprefeitura]:
    """Por `indice_prioridade` decrescente; sem índice, da maior para a menor prioridade.

    Quem tem índice vem antes de quem não tem. Desempate: prioridade, mais relatos abertos, nome.
    """
    return sorted(
        itens,
        key=lambda i: (
            i.indice_prioridade is None,
            -(i.indice_prioridade or 0.0),
            _ORDEM[i.prioridade],
            -i.relatos_abertos,
            i.subprefeitura,
        ),
    )


def _interpretar(conteudo: bytes | str, origem: str) -> list[PrioridadeSubprefeitura]:
    """Valida o JSON contra o schema do contrato. 503 (e log do motivo) se estiver fora dele."""
    try:
        itens = _LISTA.validate_python(json.loads(conteudo))
    except ValidationError as erro:
        # Só os caminhos dos campos e o tipo de cada problema; nunca os valores recebidos.
        problemas = sorted({f"{'.'.join(str(p) for p in e['loc'])}:{e['type']}" for e in erro.errors()})
        motivo = f"{len(problemas)} problema(s): " + ", ".join(problemas[:5])
        log.error(
            "painel_fora_do_schema",
            extra={"tipo_erro": "ValidationError", "origem": origem, "motivo": motivo},
        )
        raise _invalido() from None
    except ValueError as erro:  # JSONDecodeError e UnicodeDecodeError são ValueError
        log.error("painel_json_ilegivel", extra={"tipo_erro": type(erro).__name__, "origem": origem})
        raise _invalido() from None
    return _ordenar(itens)


# ---------- arquivo local (desenvolvimento) ----------


def _ler_arquivo(caminho: Path | None) -> list[PrioridadeSubprefeitura]:
    if caminho is None or not caminho.is_file():
        raise _indisponivel()
    try:
        if caminho.stat().st_size > _MAX_BYTES:
            log.error("painel_grande_demais", extra={"origem": "arquivo"})
            raise _invalido()
        conteudo = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:  # sumiu entre o teste e a leitura (troca pelo pipeline)
        raise _indisponivel() from None
    except (OSError, UnicodeDecodeError) as erro:
        log.error("painel_arquivo_ilegivel", extra={"tipo_erro": type(erro).__name__, "origem": "arquivo"})
        raise _invalido() from None
    return _interpretar(conteudo, "arquivo")


# ---------- blob (produção) ----------


@lru_cache
def _credencial() -> DefaultAzureCredential:
    # Uma só por processo: ela guarda o token em memória. Na Azure usa a identidade gerenciada
    # (com identidade user-assigned, o client_id vem de AZURE_CLIENT_ID); na máquina da pessoa
    # desenvolvedora, o `az login`.
    return DefaultAzureCredential()


def _baixar_blob(url: str) -> bytes:
    """Baixa o blob (no máximo _MAX_BYTES + 1 bytes: o excesso só serve para detectar o estouro)."""
    with BlobClient.from_blob_url(
        url,
        credential=_credencial(),
        retry_total=2,
        connection_timeout=_TIMEOUT_CONEXAO_S,
        read_timeout=_TIMEOUT_LEITURA_S,
    ) as blob:
        return blob.download_blob(offset=0, length=_MAX_BYTES + 1, max_concurrency=1).readall()


def _ler_blob(url: str) -> list[PrioridadeSubprefeitura]:
    try:
        conteudo = _baixar_blob(url)
    except ResourceNotFoundError:
        log.warning("painel_blob_nao_encontrado", extra={"status": 404, "origem": "blob"})
        raise _indisponivel() from None
    except HttpResponseError as erro:
        log.error(
            "painel_blob_falha_http",
            extra={"tipo_erro": type(erro).__name__, "status": erro.status_code, "origem": "blob"},
        )
        raise _invalido() from None
    except Exception as erro:  # credencial sem acesso, rede, timeout, URL malformada...
        # `AzureError` cobre a maior parte, mas a identidade e a rede também lançam outros tipos.
        # Só o tipo vai para o log: a mensagem pode trazer a URL ou detalhes da conta.
        evento = "painel_blob_falha_azure" if isinstance(erro, AzureError) else "painel_blob_falha_leitura"
        log.error(evento, extra={"tipo_erro": type(erro).__name__, "origem": "blob"})
        raise _invalido() from None
    if len(conteudo) > _MAX_BYTES:
        log.error("painel_grande_demais", extra={"origem": "blob"})
        raise _invalido()
    return _interpretar(conteudo, "blob")


def _com_cache(url: str, carregar: Callable[[str], list[PrioridadeSubprefeitura]]) -> list[PrioridadeSubprefeitura]:
    with _trava:  # uma leitura por vez: evita várias idas ao Storage quando o cache vence
        agora = time.monotonic()
        entrada = _cache.get(url)
        if entrada and entrada[0] > agora:
            _, itens, falha = entrada
            if itens is None:
                raise _ERROS[falha or "painel_invalido"]()
            return itens
        try:
            itens = carregar(url)
        except ErroApi as erro:
            _cache[url] = (agora + TTL_FALHA_S, None, erro.codigo)
            raise
        _cache[url] = (agora + TTL_SUCESSO_S, itens, None)
        return itens


def ler_painel(caminho: Path | None = None, *, blob_url: str = "") -> list[PrioridadeSubprefeitura]:
    """Devolve o painel ordenado. Blob (com cache) se `blob_url` vier; senão o arquivo local."""
    if blob_url:
        return _com_cache(blob_url, _ler_blob)
    return _ler_arquivo(caminho)
