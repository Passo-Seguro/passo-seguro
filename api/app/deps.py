"""Dependências injetadas nos routers (fáceis de trocar nos testes)."""

from typing import Annotated

from fastapi import Depends

from app.clients.assistente import AssistenteFalso, ClienteAssistente
from app.clients.visao import ClienteVisao, VisaoFalsa
from app.config import Settings, get_settings
from app.storage import Armazenamento, criar_armazenamento


def get_armazenamento(settings: Annotated[Settings, Depends(get_settings)]) -> Armazenamento:
    return criar_armazenamento(settings)


def get_visao() -> ClienteVisao:
    return VisaoFalsa()


def get_assistente() -> ClienteAssistente:
    return AssistenteFalso()
