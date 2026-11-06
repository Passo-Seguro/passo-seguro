"""Cliente do serviço de visão (POST /deteccoes).

Nesta etapa só existe o `VisaoFalsa`, que devolve detecções de exemplo, sem modelo de IA.
O cliente HTTP real entra na etapa de banco/integração.
"""

import hashlib
from typing import Protocol

from app.dominio import Categoria
from app.schemas.deteccoes import Caixa, Deteccao

_CLASSES = list(Categoria)


class VisaoIndisponivel(Exception):
    """O serviço de visão não respondeu ou respondeu algo inválido."""


class ClienteVisao(Protocol):
    def detectar(self, imagem: bytes, content_type: str) -> list[Deteccao]:
        """Devolve as detecções, da maior para a menor confiança (lista vazia = nada)."""


class VisaoFalsa:
    """Detector de mentira, determinístico: a mesma imagem dá sempre a mesma resposta.

    Serve para desenvolvimento e para demonstração quando o serviço de visão real não está
    no ar. A classe vem do hash da imagem, ou seja, NÃO olha para a foto de verdade.
    """

    def detectar(self, imagem: bytes, content_type: str) -> list[Deteccao]:
        h = hashlib.sha256(imagem).digest()
        classe = _CLASSES[h[0] % len(_CLASSES)]
        confianca = round(0.70 + (h[1] / 255) * 0.27, 2)  # 0,70 a 0,97
        x = round(0.05 + (h[2] / 255) * 0.40, 2)
        y = round(0.10 + (h[3] / 255) * 0.40, 2)
        largura = round(0.15 + (h[4] / 255) * 0.35, 2)
        altura = round(0.15 + (h[5] / 255) * 0.35, 2)
        return [Deteccao(classe=classe, confianca=confianca, caixa=Caixa(x=x, y=y, largura=largura, altura=altura))]
