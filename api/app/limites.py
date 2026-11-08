"""Rejeita cedo requisições com corpo grande demais (413), antes de gravar qualquer coisa.

Olha só o cabeçalho Content-Length. O limite exato do ARQUIVO (10 MiB) é conferido de novo na
leitura do upload (services/imagens.py); aqui a folga cobre os demais campos do formulário e
as fronteiras do multipart. Corpo sem Content-Length (chunked) não passa por esta checagem.
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

FOLGA_MULTIPART_BYTES = 1024 * 1024


class LimiteCorpoMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.limite = max_bytes + FOLGA_MULTIPART_BYTES

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for nome, valor in scope["headers"]:
                if nome == b"content-length":
                    try:
                        tamanho = int(valor)
                    except ValueError:
                        break
                    if tamanho > self.limite:
                        resposta = JSONResponse(
                            {
                                "codigo": "arquivo_grande",
                                "mensagem": "O arquivo enviado passa do tamanho máximo de "
                                f"{(self.limite - FOLGA_MULTIPART_BYTES) // (1024 * 1024)} MB.",
                            },
                            status_code=413,
                            headers={"Connection": "close"},
                        )
                        await resposta(scope, receive, send)
                        return
                    break
        await self.app(scope, receive, send)
