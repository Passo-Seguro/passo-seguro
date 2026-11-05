"""Validação e limpeza de imagens enviadas (foto do relato, imagem de detecção).

- Aceita só JPEG e PNG, pelo CONTEÚDO (não pelo cabeçalho Content-Type, que o cliente
  controla).
- Rejeita arquivo ilegível ou com dimensões absurdas (proteção contra "bomba de pixels").
- Regrava a imagem sem metadados: EXIF pode trazer o GPS EXATO de onde a foto foi tirada,
  e a foto fica pública. A orientação do EXIF é aplicada antes de descartá-lo.
"""

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.dominio import MAX_UPLOAD_BYTES
from app.erros import ErroApi

MAX_PIXELS = 50_000_000
_TIPOS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png")}


@dataclass(frozen=True)
class ImagemLimpa:
    conteudo: bytes
    content_type: str
    extensao: str


def ler_upload(upload: UploadFile, campo: str, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Lê o arquivo enviado em blocos e responde 413 se passar do limite."""
    return _ler_limitado(upload.file, campo, max_bytes)


def _ler_limitado(arquivo: BinaryIO, campo: str, max_bytes: int) -> bytes:
    partes: list[bytes] = []
    total = 0
    while bloco := arquivo.read(1024 * 1024):
        total += len(bloco)
        if total > max_bytes:
            raise ErroApi(
                413,
                "arquivo_grande",
                f"O arquivo enviado passa do tamanho máximo de {max_bytes // (1024 * 1024)} MB.",
                [{"campo": campo, "problema": "arquivo grande demais"}],
            )
        partes.append(bloco)
    return b"".join(partes)


def _invalida(campo: str, problema: str) -> ErroApi:
    return ErroApi(
        422,
        "dados_invalidos",
        "Os dados enviados não são válidos.",
        [{"campo": campo, "problema": problema}],
    )


def limpar_imagem(dados: bytes, campo: str) -> ImagemLimpa:
    """Valida e regrava a imagem sem metadados. Levanta 422 se não for JPEG/PNG legível."""
    if not dados:
        raise _invalida(campo, "arquivo vazio")
    try:
        with Image.open(BytesIO(dados)) as imagem:
            formato = imagem.format
            if formato not in _TIPOS:
                raise _invalida(campo, "deve ser uma imagem JPEG ou PNG")
            if imagem.width * imagem.height > MAX_PIXELS:
                raise _invalida(campo, "dimensões grandes demais")
            imagem.load()
            pronta = ImageOps.exif_transpose(imagem)
            saida = BytesIO()
            if formato == "JPEG":
                pronta.convert("RGB").save(saida, "JPEG", quality=90, optimize=True)
            else:
                pronta.save(saida, "PNG", optimize=True)
    except ErroApi:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise _invalida(campo, "imagem ilegível ou corrompida") from None
    content_type, extensao = _TIPOS[formato]
    return ImagemLimpa(saida.getvalue(), content_type, extensao)
