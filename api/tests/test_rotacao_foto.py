"""Foto tirada em pé: o celular grava a imagem deitada + a rotação no EXIF (Orientation).

Ao remover o EXIF, a API precisa GIRAR os pixels antes; senão a foto fica deitada para quem
vê o mapa e para o modelo de visão.

A imagem de teste é 40x30 (deitada), com um quadrado VERMELHO no canto superior esquerdo e o
resto azul. Depois de girar, o vermelho tem de estar no canto certo.
"""

from io import BytesIO

import pytest
from PIL import Image

from app.clients import visao
from app.services.imagens import limpar_imagem

ORIENTATION = 0x0112


def _foto_com_orientacao(orientacao: int, formato: str = "JPEG") -> bytes:
    imagem = Image.new("RGB", (40, 30), (0, 0, 255))
    imagem.paste((255, 0, 0), (0, 0, 14, 14))  # canto superior esquerdo do arquivo
    exif = Image.Exif()
    exif[ORIENTATION] = orientacao
    saida = BytesIO()
    if formato == "JPEG":
        imagem.save(saida, "JPEG", quality=95, exif=exif)
    else:
        imagem.save(saida, "PNG", exif=exif)
    return saida.getvalue()


def _eh_vermelho(pixel) -> bool:
    r, g, b = pixel[:3]
    return r > 180 and g < 90 and b < 90


def _canto_vermelho(imagem: Image.Image) -> str:
    """Em qual canto está o quadrado vermelho: 'sup-esq', 'sup-dir', 'inf-esq' ou 'inf-dir'."""
    largura, altura = imagem.size
    cantos = {
        "sup-esq": (4, 4),
        "sup-dir": (largura - 5, 4),
        "inf-esq": (4, altura - 5),
        "inf-dir": (largura - 5, altura - 5),
    }
    achados = [nome for nome, xy in cantos.items() if _eh_vermelho(imagem.getpixel(xy))]
    assert len(achados) == 1, f"esperava um único canto vermelho, achei {achados}"
    return achados[0]


@pytest.mark.parametrize(
    "orientacao,tamanho,canto",
    [
        (1, (40, 30), "sup-esq"),  # normal: não mexe
        (3, (40, 30), "inf-dir"),  # de cabeça para baixo: gira 180
        (6, (30, 40), "sup-dir"),  # celular em pé (o caso mais comum): gira 90 horário
        (8, (30, 40), "inf-esq"),  # celular em pé para o outro lado: gira 90 anti-horário
    ],
)
@pytest.mark.parametrize("formato", ["JPEG", "PNG"])
def test_foto_em_pe_e_girada_antes_de_tirar_o_exif(orientacao, tamanho, canto, formato):
    limpa = limpar_imagem(_foto_com_orientacao(orientacao, formato), "foto")

    resultado = Image.open(BytesIO(limpa.conteudo))
    assert resultado.size == tamanho
    assert _canto_vermelho(resultado) == canto
    assert ORIENTATION not in resultado.getexif()  # e a marca de rotação não vai mais junto


def test_post_relatos_grava_e_envia_para_a_visao_a_foto_ja_girada(client, settings, fabrica_sessao, monkeypatch):
    from sqlalchemy import select

    from app.db.models import Relato

    enviadas = []
    original = visao.VisaoFalsa.detectar

    def espiao(self, imagem, content_type):
        enviadas.append(imagem)
        return original(self, imagem, content_type)

    monkeypatch.setattr(visao.VisaoFalsa, "detectar", espiao)

    r = client.post(
        "/relatos",
        data={"lat": "-23.5505", "lon": "-46.6333", "fonte": "app"},
        files={"foto": ("pe.jpg", _foto_com_orientacao(6), "image/jpeg")},
    )
    assert r.status_code == 201

    with fabrica_sessao() as sessao:
        chave = sessao.scalars(select(Relato)).one().foto_chave
    gravada = Image.open(BytesIO((settings.media_dir / chave).read_bytes()))
    assert gravada.size == (30, 40) and _canto_vermelho(gravada) == "sup-dir"  # em pé, como foi tirada

    assert len(enviadas) == 1
    para_a_visao = Image.open(BytesIO(enviadas[0]))
    assert para_a_visao.size == (30, 40) and _canto_vermelho(para_a_visao) == "sup-dir"  # a visão também vê em pé


def test_post_deteccoes_tambem_gira_a_imagem(client, auth, monkeypatch):
    enviadas = []
    original = visao.VisaoFalsa.detectar
    monkeypatch.setattr(visao.VisaoFalsa, "detectar", lambda self, i, c: (enviadas.append(i), original(self, i, c))[1])
    r = client.post("/deteccoes", files={"imagem": ("pe.jpg", _foto_com_orientacao(8), "image/jpeg")}, headers=auth)
    assert r.status_code == 200
    assert Image.open(BytesIO(enviadas[0])).size == (30, 40)
