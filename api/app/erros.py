"""Erros da API no formato único do contrato (schema `Erro`):

    {"codigo": "dados_invalidos", "mensagem": "...", "detalhes": [{"campo": "lat", "problema": "..."}]}

Regra de status para falhas de validação do FastAPI/Pydantic:
- parâmetros de consulta, de caminho ou de cabeçalho inválidos -> 400 `requisicao_invalida`;
- corpo com problema ESTRUTURAL (campo ausente, tipo errado, JSON malformado) -> 400;
- corpo bem formado mas com valor que não passa na regra (fora da faixa, enum inválido,
  texto vazio ou longo demais) -> 422 `dados_invalidos`.
"""

import logging
import re

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("passo_seguro.erros")


class ErroApi(Exception):
    """Erro de negócio que vira uma resposta `Erro` do contrato."""

    def __init__(
        self,
        status_code: int,
        codigo: str,
        mensagem: str,
        detalhes: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(mensagem)
        self.status_code = status_code
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes
        self.headers = headers


def resposta_erro(
    status_code: int,
    codigo: str,
    mensagem: str,
    detalhes: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    corpo: dict = {"codigo": codigo, "mensagem": mensagem}
    if detalhes:
        corpo["detalhes"] = detalhes
    return JSONResponse(corpo, status_code=status_code, headers=headers)


# --- tradução das mensagens do Pydantic para português -------------------------------

_MSG_SIMPLES = {
    "missing": "campo obrigatório",
    "json_invalid": "JSON malformado",
    "string_too_short": "texto curto demais",
    "string_too_long": "texto longo demais",
    "float_parsing": "deve ser um número",
    "float_type": "deve ser um número",
    "int_parsing": "deve ser um número inteiro",
    "int_type": "deve ser um número inteiro",
    "bool_parsing": "deve ser verdadeiro ou falso",
    "uuid_parsing": "deve ser um UUID",
    "uuid_type": "deve ser um UUID",
    "datetime_parsing": "deve ser uma data e hora ISO 8601",
    "datetime_from_date_parsing": "deve ser uma data e hora ISO 8601",
    "datetime_type": "deve ser uma data e hora ISO 8601",
    "timezone_aware": "deve informar o fuso, por exemplo -03:00",
    "extra_forbidden": "campo não permitido",
    "model_attributes_type": "corpo deve ser um objeto",
    "dict_type": "corpo deve ser um objeto",
    "too_short": "deve ter ao menos um item",
}


def _mensagem(erro: dict) -> str:
    tipo = erro.get("type", "")
    ctx = erro.get("ctx") or {}
    if tipo in ("greater_than_equal", "greater_than"):
        limite = ctx.get("ge", ctx.get("gt"))
        return f"deve ser maior ou igual a {limite}"
    if tipo in ("less_than_equal", "less_than"):
        limite = ctx.get("le", ctx.get("lt"))
        return f"deve ser menor ou igual a {limite}"
    if tipo in ("enum", "literal_error"):
        esperados = ctx.get("expected")
        return f"deve ser um de: {esperados}" if esperados else "valor não permitido"
    if tipo == "value_error":
        return str(erro.get("msg", "valor inválido")).removeprefix("Value error, ")
    if tipo == "string_too_long":
        return f"deve ter no máximo {ctx.get('max_length')} caracteres"
    if tipo == "string_too_short":
        return f"deve ter no mínimo {ctx.get('min_length')} caractere(s)"
    return _MSG_SIMPLES.get(tipo, "valor inválido")


def _eh_estrutural(erro: dict) -> bool:
    tipo = erro.get("type", "")
    return (
        tipo in ("missing", "json_invalid", "model_attributes_type", "dict_type", "extra_forbidden")
        or tipo.endswith("_type")
        or tipo.endswith("_parsing")
    )


def _campo(erro: dict) -> str:
    if erro.get("type") in ("json_invalid", "model_attributes_type", "dict_type"):
        return "corpo"
    loc = [str(p) for p in erro.get("loc", ())]
    if len(loc) == 2 and loc[0] == "header":
        # 'x_autor_id' / 'x-autor-id' -> 'X-Autor-Id', como o cliente escreve o cabeçalho
        return "-".join(parte.capitalize() for parte in re.split(r"[-_]", loc[1]))
    # Tira o primeiro nível (body/query/header/path) e fica com o nome do campo.
    return ".".join(loc[1:]) if len(loc) > 1 else (loc[0] if loc else "corpo")


async def tratar_erro_api(_: Request, exc: ErroApi) -> JSONResponse:
    return resposta_erro(exc.status_code, exc.codigo, exc.mensagem, exc.detalhes, exc.headers)


async def tratar_validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
    erros = exc.errors()
    detalhes = [{"campo": _campo(e), "problema": _mensagem(e)} for e in erros]
    fora_do_corpo = any(e.get("loc", ("body",))[0] != "body" for e in erros)
    estrutural = any(_eh_estrutural(e) for e in erros)
    if fora_do_corpo or estrutural:
        return resposta_erro(400, "requisicao_invalida", "A requisição está malformada.", detalhes)
    return resposta_erro(422, "dados_invalidos", "Os dados enviados não são válidos.", detalhes)


_CODIGOS_HTTP = {
    400: "requisicao_invalida",
    401: "nao_autenticado",
    403: "proibido",
    404: "nao_encontrado",
    405: "metodo_nao_permitido",
    413: "arquivo_grande",
}


async def tratar_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    codigo = _CODIGOS_HTTP.get(exc.status_code, "erro_http")
    mensagem = {
        400: "A requisição está malformada.",
        404: "Recurso não encontrado.",
        405: "Método não permitido.",
    }.get(exc.status_code, str(exc.detail))
    return resposta_erro(exc.status_code, codigo, mensagem, headers=getattr(exc, "headers", None))


async def tratar_excecao(_: Request, exc: Exception) -> JSONResponse:
    # Só o tipo vai para o log: a mensagem da exceção pode conter dados do relato.
    log.error("erro_nao_tratado", extra={"tipo_erro": type(exc).__name__})
    return resposta_erro(500, "erro_interno", "Erro interno. Tente novamente em instantes.")
