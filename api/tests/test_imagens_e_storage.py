from io import BytesIO

import pytest
from PIL import Image

from app.erros import ErroApi
from app.seguranca import extrair_bearer, tokens_iguais
from app.services.imagens import limpar_imagem
from app.storage import ArmazenamentoLocal


def _jpeg_com_exif_gps() -> bytes:
    imagem = Image.new("RGB", (40, 30), (10, 120, 200))
    exif = Image.Exif()
    exif[0x010F] = "FabricanteFicticio"  # Make
    gps = exif.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (23.0, 33.0, 1.8)
    gps[3] = "W"
    gps[4] = (46.0, 38.0, 0.0)
    saida = BytesIO()
    imagem.save(saida, "JPEG", exif=exif)
    return saida.getvalue()


def test_limpar_imagem_remove_exif_com_gps():
    original = _jpeg_com_exif_gps()
    assert len(Image.open(BytesIO(original)).getexif().get_ifd(0x8825)) > 0  # o teste parte de uma foto com GPS

    limpa = limpar_imagem(original, "foto")

    assert limpa.content_type == "image/jpeg" and limpa.extensao == "jpg"
    resultado = Image.open(BytesIO(limpa.conteudo))
    assert dict(resultado.getexif()) == {}
    assert resultado.size == (40, 30)


def test_limpar_imagem_png():
    entrada = BytesIO()
    Image.new("RGBA", (10, 10), (1, 2, 3, 255)).save(entrada, "PNG")
    limpa = limpar_imagem(entrada.getvalue(), "foto")
    assert limpa.content_type == "image/png" and limpa.extensao == "png"


@pytest.mark.parametrize("dados", [b"", b"texto qualquer", b"\xff\xd8\xff truncado"])
def test_limpar_imagem_recusa_lixo(dados):
    with pytest.raises(ErroApi) as erro:
        limpar_imagem(dados, "foto")
    assert erro.value.status_code == 422


def test_tokens_iguais():
    assert tokens_iguais("segredo", "segredo")
    assert not tokens_iguais("segredo", "outro")
    assert not tokens_iguais("segredo", None)
    assert not tokens_iguais("segredo", "")
    assert not tokens_iguais("", "")  # sem token configurado nada autentica
    assert not tokens_iguais("", "qualquer")


def test_extrair_bearer():
    assert extrair_bearer("Bearer abc") == "abc"
    assert extrair_bearer("bearer abc") == "abc"
    assert extrair_bearer("Bearer") is None
    assert extrair_bearer("Bearer ") is None
    assert extrair_bearer("Basic abc") is None
    assert extrair_bearer(None) is None


def test_armazenamento_local_grava_e_remove(tmp_path):
    armazenamento = ArmazenamentoLocal(tmp_path, "http://x.test/")
    armazenamento.salvar("relatos/a.jpg", b"conteudo", "image/jpeg")
    assert (tmp_path / "relatos" / "a.jpg").read_bytes() == b"conteudo"
    assert armazenamento.url("relatos/a.jpg") == "http://x.test/fotos/relatos/a.jpg"
    armazenamento.remover("relatos/a.jpg")
    armazenamento.remover("relatos/a.jpg")  # não falha se já foi
    assert not (tmp_path / "relatos" / "a.jpg").exists()


@pytest.mark.parametrize("chave", ["../fora.jpg", "a/../../fora.jpg", "/abs.jpg", "a b.jpg", "", "a\\b.jpg"])
def test_armazenamento_local_recusa_chave_perigosa(tmp_path, chave):
    armazenamento = ArmazenamentoLocal(tmp_path, "http://x.test")
    with pytest.raises(ValueError):
        armazenamento.salvar(chave, b"x", "image/jpeg")
