"""Leitura do painel de prioridades exportado pelo pipeline de dados (camada Ouro)."""

import json
import logging
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.dominio import Prioridade
from app.erros import ErroApi
from app.schemas.painel import PrioridadeSubprefeitura

log = logging.getLogger("passo_seguro.painel")
_LISTA = TypeAdapter(list[PrioridadeSubprefeitura])
_MAX_BYTES = 5 * 1024 * 1024
_ORDEM = {Prioridade.ALTA: 0, Prioridade.MEDIA: 1, Prioridade.BAIXA: 2}


def _indisponivel() -> ErroApi:
    return ErroApi(
        404,
        "painel_indisponivel",
        "O painel de prioridades ainda não foi exportado pelo pipeline de dados.",
    )


def ler_painel(caminho: Path | None) -> list[PrioridadeSubprefeitura]:
    """Lê e valida o arquivo. 404 se não existir; 503 se existir mas estiver fora do schema.

    O arquivo é relido a cada chamada: o pipeline o troca quando exporta de novo, e ele é pequeno.
    Os itens saem da maior para a menor prioridade (depois mais relatos abertos, depois nome).
    """
    if caminho is None or not caminho.is_file():
        raise _indisponivel()
    try:
        if caminho.stat().st_size > _MAX_BYTES:
            raise ValueError("arquivo grande demais")
        itens = _LISTA.validate_python(json.loads(caminho.read_text(encoding="utf-8")))
    except FileNotFoundError:  # sumiu entre o teste e a leitura (troca pelo pipeline)
        raise _indisponivel() from None
    except (ValueError, ValidationError, OSError) as erro:
        # ValidationError e JSONDecodeError são ValueError. Só o tipo vai para o log.
        log.error("painel_arquivo_invalido", extra={"tipo_erro": type(erro).__name__})
        raise ErroApi(
            503,
            "painel_invalido",
            "O arquivo do painel exportado pelo pipeline de dados está inválido.",
        ) from None
    return sorted(itens, key=lambda i: (_ORDEM[i.prioridade], -i.relatos_abertos, i.subprefeitura))
