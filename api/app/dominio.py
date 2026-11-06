"""Vocabulário do domínio, igual ao contrato (openapi.yaml) e a contratos/classes.yaml.

As classes de problema NÃO devem ser editadas aqui sem antes mudar contratos/classes.yaml
e o openapi.yaml; o teste `test_dominio.py` confere os três contra divergência.
"""

from enum import StrEnum


class Categoria(StrEnum):
    """Classes de problema de calçada. A ordem é a de contratos/classes.yaml (índice no YOLO)."""

    BURACO = "buraco"
    PISO_DANIFICADO = "piso_danificado"
    OBSTACULO = "obstaculo"
    VEICULO_NA_CALCADA = "veiculo_na_calcada"


class StatusRelato(StrEnum):
    """Fluxo: novo -> revisao_humana -> validado -> encaminhado -> resolvido (ou rejeitado)."""

    NOVO = "novo"
    REVISAO_HUMANA = "revisao_humana"
    VALIDADO = "validado"
    ENCAMINHADO = "encaminhado"
    RESOLVIDO = "resolvido"
    REJEITADO = "rejeitado"


class Prioridade(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class FonteRelato(StrEnum):
    APP = "app"
    ROBO = "robo"


# Tamanho máximo de foto/imagem aceito (decisão provisória do contrato): 10 MiB.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class ModoDeteccao(StrEnum):
    """Como a categoria de um relato foi obtida. Dado INTERNO: não entra no contrato nem em resposta.

    - `real`: a visão real (serviço de visão) respondeu;
    - `fake`: o cliente fake respondeu (a categoria vem do hash da imagem, não do modelo);
    - `nenhuma`: a visão falhou ou não detectou nada (e os relatos simulados por script).
    """

    REAL = "real"
    FAKE = "fake"
    NENHUMA = "nenhuma"
