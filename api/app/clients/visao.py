"""Cliente do serviço de visão (POST /deteccoes de OUTRO serviço, feito pelo pessoal de visão).

A API não carrega modelo de IA: ela só chama esse serviço por HTTP. Implementações:
- `VisaoHttp`: chamada real (URL, token e timeout vêm de variáveis de ambiente);
- `VisaoFalsa`: detecções determinísticas, para desenvolvimento e demonstração;
- `VisaoForaDoAr`: usada quando não há URL configurada; sempre falha, e o relato é criado
  do mesmo jeito, com categoria e confiança nulas.
"""

import hashlib
import logging
from functools import lru_cache
from typing import Protocol

import httpx
from pydantic import TypeAdapter, ValidationError

from app.config import Settings
from app.dominio import Categoria, ModoDeteccao
from app.schemas.deteccoes import Caixa, Deteccao

log = logging.getLogger("passo_seguro.visao")
_LISTA_DETECCOES = TypeAdapter(list[Deteccao])

_CLASSES = list(Categoria)


class VisaoIndisponivel(Exception):
    """O serviço de visão não respondeu ou respondeu algo inválido."""


class ClienteVisao(Protocol):
    # Quem respondeu, gravado em `relatos.modo_deteccao` quando houver detecção.
    modo: ModoDeteccao

    def detectar(self, imagem: bytes, content_type: str) -> list[Deteccao]:
        """Devolve as detecções, da maior para a menor confiança (lista vazia = nada)."""


class VisaoFalsa:
    """Detector de mentira, determinístico: a mesma imagem dá sempre a mesma resposta.

    Serve para desenvolvimento e para demonstração quando o serviço de visão real não está
    no ar. A classe vem do hash da imagem, ou seja, NÃO olha para a foto de verdade.
    """

    modo = ModoDeteccao.FAKE

    def detectar(self, imagem: bytes, content_type: str) -> list[Deteccao]:
        h = hashlib.sha256(imagem).digest()
        classe = _CLASSES[h[0] % len(_CLASSES)]
        confianca = round(0.70 + (h[1] / 255) * 0.27, 2)  # 0,70 a 0,97
        x = round(0.05 + (h[2] / 255) * 0.40, 2)
        y = round(0.10 + (h[3] / 255) * 0.40, 2)
        largura = round(0.15 + (h[4] / 255) * 0.35, 2)
        altura = round(0.15 + (h[5] / 255) * 0.35, 2)
        return [Deteccao(classe=classe, confianca=confianca, caixa=Caixa(x=x, y=y, largura=largura, altura=altura))]


class VisaoForaDoAr:
    """Sem serviço de visão configurado: toda chamada falha como 'indisponível'."""

    modo = ModoDeteccao.NENHUMA

    def detectar(self, imagem: bytes, content_type: str) -> list[Deteccao]:
        raise VisaoIndisponivel("serviço de visão não configurado")


class VisaoHttp:
    """Chama `POST {url}/deteccoes` (multipart, campo `imagem`) do serviço de visão."""

    modo = ModoDeteccao.REAL

    def __init__(self, base_url: str, token: str = "", timeout_s: float = 5.0, cliente: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.cliente = cliente or httpx.Client(timeout=timeout_s)
        self.timeout_s = timeout_s

    def detectar(self, imagem: bytes, content_type: str) -> list[Deteccao]:
        cabecalhos = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            resposta = self.cliente.post(
                f"{self.base_url}/deteccoes",
                files={"imagem": ("imagem", imagem, content_type)},
                headers=cabecalhos,
                timeout=self.timeout_s,
            )
        except httpx.HTTPError as erro:
            # Só o tipo do erro vai para o log (a mensagem pode trazer a URL e detalhes).
            log.warning("visao_falhou", extra={"tipo_erro": type(erro).__name__})
            raise VisaoIndisponivel(type(erro).__name__) from None
        if resposta.status_code != 200:
            log.warning("visao_status_inesperado", extra={"status": resposta.status_code})
            raise VisaoIndisponivel(f"status {resposta.status_code}")
        try:
            deteccoes = _LISTA_DETECCOES.validate_json(resposta.content)
        except ValidationError:
            log.warning("visao_resposta_invalida")
            raise VisaoIndisponivel("resposta fora do contrato") from None
        return sorted(deteccoes, key=lambda d: d.confianca, reverse=True)


@lru_cache(maxsize=8)
def _http_compartilhado(url: str, token: str, timeout_s: float) -> VisaoHttp:
    """Um cliente por configuração, para reaproveitar conexões entre requisições."""
    return VisaoHttp(url, token, timeout_s)


def criar_visao(settings: Settings) -> ClienteVisao:
    """Escolhe a implementação: fake (USE_FAKE_VISAO), HTTP (VISAO_URL) ou fora do ar."""
    if settings.use_fake_visao:
        return VisaoFalsa()
    if settings.visao_url:
        return _http_compartilhado(settings.visao_url, settings.visao_token, settings.visao_timeout_s)
    return VisaoForaDoAr()
