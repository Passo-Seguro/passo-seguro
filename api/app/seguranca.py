"""Autenticação por token (bearerAuth) nas chamadas entre serviços.

Regras:
- a comparação é em tempo constante (`hmac.compare_digest`), para não vazar o token por
  diferença de tempo;
- se o token esperado NÃO está configurado (variável vazia), tudo é negado: a API fecha
  por padrão em vez de abrir por esquecimento;
- o valor recebido nunca é logado nem devolvido.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header

from app.config import Settings, get_settings
from app.erros import ErroApi


def tokens_iguais(esperado: str, recebido: str | None) -> bool:
    """Compara em tempo constante. Esperado vazio ou recebido ausente nunca autenticam."""
    if not esperado or not recebido:
        return False
    return hmac.compare_digest(esperado.encode("utf-8"), recebido.encode("utf-8"))


def extrair_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    esquema, _, valor = authorization.partition(" ")
    if esquema.lower() != "bearer" or not valor.strip():
        return None
    return valor.strip()


def nao_autenticado(mensagem: str = "Token ausente ou inválido.") -> ErroApi:
    return ErroApi(401, "nao_autenticado", mensagem, headers={"WWW-Authenticate": "Bearer"})


def exigir_token_servico(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Dependência dos endpoints entre serviços (`GET /relatos`, `POST /deteccoes`)."""
    if not tokens_iguais(settings.service_token, extrair_bearer(authorization)):
        raise nao_autenticado()
