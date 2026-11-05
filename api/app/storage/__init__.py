"""Armazenamento de fotos atrás de uma interface.

Hoje existe só `ArmazenamentoLocal` (disco, para desenvolvimento). A implementação de
nuvem (bucket) entra depois, feita pelo DevOps, implementando o mesmo `Armazenamento`.
"""

import re
from pathlib import Path
from typing import Protocol

from app.config import Settings

_CHAVE_VALIDA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")


class Armazenamento(Protocol):
    """Contrato de qualquer implementação de armazenamento de fotos."""

    def salvar(self, chave: str, conteudo: bytes, content_type: str) -> None:
        """Grava o arquivo sob `chave` (sobrescreve se existir)."""

    def remover(self, chave: str) -> None:
        """Apaga o arquivo; não falha se ele não existir."""

    def url(self, chave: str) -> str:
        """Endereço público (URI) para exibir a foto."""


class ArmazenamentoLocal:
    """Grava em disco, sob `raiz`. As fotos são servidas por `/fotos/<chave>` (ver main.py)."""

    def __init__(self, raiz: Path, base_url: str):
        self.raiz = Path(raiz).resolve()
        self.base_url = base_url.rstrip("/")

    def _caminho(self, chave: str) -> Path:
        if not _CHAVE_VALIDA.match(chave) or ".." in chave.split("/"):
            raise ValueError("chave de armazenamento inválida")
        caminho = (self.raiz / chave).resolve()
        if self.raiz not in caminho.parents:
            raise ValueError("chave de armazenamento fora da raiz")
        return caminho

    def salvar(self, chave: str, conteudo: bytes, content_type: str) -> None:
        caminho = self._caminho(chave)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)

    def remover(self, chave: str) -> None:
        self._caminho(chave).unlink(missing_ok=True)

    def url(self, chave: str) -> str:
        self._caminho(chave)  # valida a chave
        return f"{self.base_url}/fotos/{chave}"


def criar_armazenamento(settings: Settings) -> Armazenamento:
    return ArmazenamentoLocal(settings.media_dir, settings.public_base_url)
