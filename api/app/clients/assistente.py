"""Cliente do assistente (POST /assistente).

Nesta etapa só existe o `AssistenteFalso`, com respostas de exemplo do contrato. O cliente
HTTP real entra na etapa de integração.
"""

from typing import Protocol

from app.schemas.assistente import FonteCitada, RespostaAssistente

_PALAVRAS_DO_ASSUNTO = ("calçada", "calcada", "buraco", "piso", "obstáculo", "obstaculo", "156", "reclam", "conserta")


class ClienteAssistente(Protocol):
    def perguntar(self, pergunta: str) -> RespostaAssistente: ...


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
