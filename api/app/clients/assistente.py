"""Cliente do assistente (POST /assistente de OUTRO serviço: LLM local com RAG).

Implementações:
- `AssistenteHttp`: chamada real (URL, token e timeout por variável de ambiente);
- `AssistenteFalso`: respostas fixas, para desenvolvimento e demonstração;
- `AssistenteForaDoAr`: usada quando não há URL configurada.

Se o assistente falhar, o endpoint NÃO devolve erro: devolve uma recusa padrão com o link do
SP156 (ver `resposta_de_contingencia`), e o app continua funcionando.
"""

import logging
from functools import lru_cache
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas.assistente import FonteCitada, PerguntaAssistente, RespostaAssistente

log = logging.getLogger("passo_seguro.assistente")

_PALAVRAS_DO_ASSUNTO = ("calçada", "calcada", "buraco", "piso", "obstáculo", "obstaculo", "156", "reclam", "conserta")


class AssistenteIndisponivel(Exception):
    """O assistente não respondeu ou respondeu algo fora do contrato."""


class ClienteAssistente(Protocol):
    def perguntar(self, pergunta: str) -> RespostaAssistente: ...


def resposta_de_contingencia(sp156_url: str) -> RespostaAssistente:
    """Resposta padrão quando o assistente está fora do ar: recusa e aponta o canal oficial."""
    return RespostaAssistente(
        resposta=(
            "O assistente não está disponível agora. Você ainda pode registrar o problema aqui "
            "no Passo Seguro e, para falar com a Prefeitura, ligue 156 ou acesse o SP156: "
            f"{sp156_url}"
        ),
        fontes=[],  # com recusou=true as fontes ficam vazias, como manda o contrato
        confianca=0.0,
        recusou=True,
    )


class AssistenteFalso:
    """Respostas fixas do contrato: dentro do assunto responde com fonte; fora, recusa.

    Os textos são ilustrativos, NÃO são orientação oficial.
    """

    def perguntar(self, pergunta: str) -> RespostaAssistente:
        texto = pergunta.lower()
        if any(p in texto for p in _PALAVRAS_DO_ASSUNTO):
            return RespostaAssistente(
                resposta=(
                    "Em geral, o cuidado com o piso da calçada é de quem é dono do imóvel em frente. "
                    "Se o problema for na área pública ou causado por obra de concessionária, a "
                    "subprefeitura da região pode ser acionada pelo canal 156. Registre o problema "
                    "aqui para acompanhar o caso."
                ),
                fontes=[
                    FonteCitada(
                        titulo="Cartilha de calçadas da subprefeitura (exemplo)",
                        url="https://documentos.exemplo.invalid/cartilha-calcadas.pdf",
                    )
                ],
                confianca=0.86,
                recusou=False,
            )
        return RespostaAssistente(
            resposta=(
                "Eu só consigo ajudar com problemas em calçadas de São Paulo, como quem conserta "
                "e como reclamar. Não tenho como responder a essa pergunta."
            ),
            fontes=[],
            confianca=0.1,
            recusou=True,
        )


class AssistenteForaDoAr:
    def perguntar(self, pergunta: str) -> RespostaAssistente:
        raise AssistenteIndisponivel("assistente não configurado")


class AssistenteHttp:
    """Chama `POST {url}/assistente` com `{"pergunta": ...}` e valida a resposta."""

    def __init__(self, base_url: str, token: str = "", timeout_s: float = 15.0, cliente: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_s = timeout_s
        self.cliente = cliente or httpx.Client(timeout=timeout_s)

    def perguntar(self, pergunta: str) -> RespostaAssistente:
        cabecalhos = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            resposta = self.cliente.post(
                f"{self.base_url}/assistente",
                json=PerguntaAssistente(pergunta=pergunta).model_dump(),
                headers=cabecalhos,
                timeout=self.timeout_s,
            )
        except httpx.HTTPError as erro:
            # Só o tipo vai para o log: a mensagem pode trazer a URL e a pergunta do cidadão.
            log.warning("assistente_falhou", extra={"tipo_erro": type(erro).__name__})
            raise AssistenteIndisponivel(type(erro).__name__) from None
        if resposta.status_code != 200:
            log.warning("assistente_status_inesperado", extra={"status": resposta.status_code})
            raise AssistenteIndisponivel(f"status {resposta.status_code}")
        try:
            return RespostaAssistente.model_validate_json(resposta.content)
        except ValidationError:
            log.warning("assistente_resposta_invalida")
            raise AssistenteIndisponivel("resposta fora do contrato") from None


@lru_cache(maxsize=8)
def _http_compartilhado(url: str, token: str, timeout_s: float) -> AssistenteHttp:
    return AssistenteHttp(url, token, timeout_s)


def criar_assistente(settings: Settings) -> ClienteAssistente:
    """Escolhe: fake (USE_FAKE_ASSISTENTE), HTTP (ASSISTENTE_URL) ou fora do ar."""
    if settings.use_fake_assistente:
        return AssistenteFalso()
    if settings.assistente_url:
        return _http_compartilhado(settings.assistente_url, settings.assistente_token, settings.assistente_timeout_s)
    return AssistenteForaDoAr()
