"""POST /relatos: validação, gravação no banco e na pasta de fotos, visão fora do ar, autoria."""

import logging
import uuid
from io import BytesIO

import httpx
import pytest
import respx
from PIL import Image
from sqlalchemy import select, text

from app.clients.visao import VisaoIndisponivel
from app.db.models import Relato
from app.dominio import MAX_UPLOAD_BYTES
from app.observabilidade import FormatadorJson
from app.seguranca import hash_autor
from tests.conftest import SAL_AUTOR, TOKEN_DISPOSITIVO


def _foto(conteudo: bytes, nome="foto.jpg", tipo="image/jpeg"):
    return {"foto": (nome, conteudo, tipo)}


def _form(**extra):
    base = {"lat": "-23.5505", "lon": "-46.6333", "fonte": "app"}
    base.update(extra)
    return base


def _linha(fabrica_sessao, id_) -> Relato:
    with fabrica_sessao() as sessao:
        return sessao.scalars(select(Relato).where(Relato.id == uuid.UUID(id_))).one()


# --- sucesso -------------------------------------------------------------------------


def test_cria_relato_e_grava_banco_e_foto(client, fabrica_sessao, settings, jpeg):
    r = client.post("/relatos", data=_form(descricao="Buraco na calçada"), files=_foto(jpeg))

    assert r.status_code == 201
    corpo = r.json()
    assert set(corpo) == {"id", "categoria", "confianca", "status"}
    assert corpo["status"] == "novo"
    assert corpo["categoria"] in {"buraco", "piso_danificado", "obstaculo", "veiculo_na_calcada"}

    linha = _linha(fabrica_sessao, corpo["id"])
    assert linha.status == "novo" and linha.confirmacoes == 0
    assert linha.categoria == corpo["categoria"] and linha.confianca == corpo["confianca"]
    assert linha.descricao == "Buraco na calçada"
    assert linha.fonte == "app" and linha.simulado is False
    assert linha.subprefeitura is None and linha.prioridade is None
    assert linha.foto_chave == f"relatos/{corpo['id']}.jpg"
    assert (settings.media_dir / linha.foto_chave).read_bytes()[:2] == b"\xff\xd8"  # é um JPEG


def test_localizacao_vira_ponto_postgis(client, fabrica_sessao, jpeg):
    r = client.post("/relatos", data=_form(lat="-23.55051234", lon="-46.63331234"), files=_foto(jpeg))
    with fabrica_sessao() as sessao:
        wkt, srid = sessao.execute(
            text("SELECT ST_AsText(localizacao::geometry), ST_SRID(localizacao::geometry) FROM relatos WHERE id = :i"),
            {"i": r.json()["id"]},
        ).one()
    assert wkt == "POINT(-46.63331234 -23.55051234)" and srid == 4326


def test_png_e_aceito_e_vira_png(client, settings, png, fabrica_sessao):
    r = client.post("/relatos", data=_form(fonte="app"), files=_foto(png, "f.png", "image/png"))
    assert r.status_code == 201
    assert _linha(fabrica_sessao, r.json()["id"]).foto_chave.endswith(".png")


def test_foto_gravada_nao_tem_exif(client, settings, fabrica_sessao):
    imagem = Image.new("RGB", (40, 30), (1, 2, 3))
    exif = Image.Exif()
    exif.get_ifd(0x8825)[1] = "S"  # um campo de GPS
    exif[0x010F] = "Fabricante"
    entrada = BytesIO()
    imagem.save(entrada, "JPEG", exif=exif)

    r = client.post("/relatos", data=_form(), files=_foto(entrada.getvalue()))

    gravada = (settings.media_dir / _linha(fabrica_sessao, r.json()["id"]).foto_chave).read_bytes()
    assert dict(Image.open(BytesIO(gravada)).getexif()) == {}


def test_sempre_novo_mesmo_com_confianca_baixa(montar_cliente, settings, jpeg, fabrica_sessao, monkeypatch):
    """A regra 'confiança < 0,5 vai para revisão humana' é da triagem, não da API."""
    from app.clients import visao
    from app.schemas.deteccoes import Caixa, Deteccao

    baixa = Deteccao(classe="piso_danificado", confianca=0.42, caixa=Caixa(x=0, y=0, largura=1, altura=1))
    monkeypatch.setattr(visao.VisaoFalsa, "detectar", lambda self, i, c: [baixa])
    r = montar_cliente(settings).post("/relatos", data=_form(), files=_foto(jpeg))
    assert r.status_code == 201
    assert r.json() == {"id": r.json()["id"], "categoria": "piso_danificado", "confianca": 0.42, "status": "novo"}
    assert _linha(fabrica_sessao, r.json()["id"]).status == "novo"


# --- visão fora do ar ou sem detecção: o relato não se perde -----------------------------


def test_visao_nao_detectou_nada_grava_nulos(client, fabrica_sessao, jpeg, monkeypatch):
    from app.clients import visao

    monkeypatch.setattr(visao.VisaoFalsa, "detectar", lambda self, i, c: [])
    r = client.post("/relatos", data=_form(), files=_foto(jpeg))
    assert r.status_code == 201
    assert r.json() == {"id": r.json()["id"], "categoria": None, "confianca": None, "status": "novo"}
    linha = _linha(fabrica_sessao, r.json()["id"])
    assert linha.categoria is None and linha.confianca is None and linha.status == "novo"


def test_visao_indisponivel_grava_nulos(client, fabrica_sessao, jpeg, monkeypatch):
    from app.clients import visao

    def cair(self, imagem, content_type):
        raise VisaoIndisponivel("fora do ar")

    monkeypatch.setattr(visao.VisaoFalsa, "detectar", cair)
    r = client.post("/relatos", data=_form(), files=_foto(jpeg))
    assert r.status_code == 201
    assert r.json()["categoria"] is None and r.json()["confianca"] is None


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(500),
        httpx.Response(200, json={"nao": "e uma lista"}),
        httpx.Response(200, content=b"nao e json"),
        httpx.Response(
            200, json=[{"classe": "cratera", "confianca": 0.9, "caixa": {"x": 0, "y": 0, "largura": 1, "altura": 1}}]
        ),
        httpx.ConnectError("recusou"),
        httpx.ReadTimeout("demorou"),
    ],
    ids=["http-500", "json-errado", "nao-json", "classe-fora-do-contrato", "conexao-recusada", "timeout"],
)
def test_visao_http_com_defeito_nao_derruba_o_relato(montar_cliente, settings, fabrica_sessao, jpeg, resposta):
    config = settings.model_copy(update={"use_fake_visao": False, "visao_url": "http://visao.invalid"})
    with respx.mock(assert_all_called=True) as mock:
        rota = mock.post("http://visao.invalid/deteccoes")
        if isinstance(resposta, Exception):
            rota.mock(side_effect=resposta)
        else:
            rota.mock(return_value=resposta)
        r = montar_cliente(config).post("/relatos", data=_form(), files=_foto(jpeg))
    assert r.status_code == 201
    assert r.json()["categoria"] is None and r.json()["status"] == "novo"
    assert _linha(fabrica_sessao, r.json()["id"]).categoria is None


def test_sem_url_de_visao_e_sem_fake_o_relato_e_criado(montar_cliente, settings, jpeg):
    config = settings.model_copy(update={"use_fake_visao": False, "visao_url": ""})
    r = montar_cliente(config).post("/relatos", data=_form(), files=_foto(jpeg))
    assert r.status_code == 201 and r.json()["categoria"] is None


# --- validação ------------------------------------------------------------------------


def test_mime_e_validado_pelo_conteudo_e_nada_e_gravado(client, fabrica_sessao, settings):
    r = client.post("/relatos", data=_form(), files=_foto(b"nao sou uma imagem", "foto.jpg", "image/jpeg"))
    assert r.status_code == 422
    assert r.json()["codigo"] == "dados_invalidos"
    assert r.json()["detalhes"][0]["campo"] == "foto"
    with fabrica_sessao() as sessao:
        assert sessao.scalar(text("SELECT count(*) FROM relatos")) == 0
    assert not list(settings.media_dir.glob("relatos/*"))


def test_gif_com_content_type_de_jpeg_e_recusado(client):
    gif = BytesIO()
    Image.new("RGB", (8, 8)).save(gif, "GIF")
    assert client.post("/relatos", data=_form(), files=_foto(gif.getvalue())).status_code == 422


def test_tamanho_maximo_e_10_mib_e_acima_disso_413(client, jpeg):
    no_limite = jpeg + b"\0" * (MAX_UPLOAD_BYTES - len(jpeg))  # exatamente 10 MiB (lixo no fim do JPEG)
    assert len(no_limite) == MAX_UPLOAD_BYTES
    r = client.post("/relatos", data=_form(), files=_foto(no_limite))
    assert r.status_code == 201  # exatamente no limite ainda é aceito

    passou_um_byte = no_limite + b"\0"
    r = client.post("/relatos", data=_form(), files=_foto(passou_um_byte))
    assert r.status_code == 413
    assert r.json()["codigo"] == "arquivo_grande"
    assert r.json()["detalhes"][0]["campo"] == "foto"


def test_corpo_muito_maior_que_o_limite_e_recusado_antes_de_ler(client):
    r = client.post("/relatos", data=_form(), files=_foto(b"x" * (MAX_UPLOAD_BYTES + 2 * 1024 * 1024)))
    assert r.status_code == 413
    assert r.json()["codigo"] == "arquivo_grande"


def test_coordenadas_fora_de_sao_paulo_422(client, jpeg):
    r = client.post("/relatos", data=_form(lat="-22.9", lon="-43.2"), files=_foto(jpeg))
    assert r.status_code == 422
    # código próprio: o app mostra "Você está fora de São Paulo; toque no mapa dentro da cidade"
    assert r.json() == {
        "codigo": "fora_da_area",
        "mensagem": "Os dados enviados não são válidos.",
        "detalhes": [
            {"campo": "lat", "problema": "a localização está fora da área de atendimento (município de São Paulo)"}
        ],
    }


def test_so_o_fora_da_area_usa_o_codigo_proprio_os_outros_422_continuam_dados_invalidos(client, jpeg):
    for dados in (_form(lat="95"), _form(fonte="drone")):
        r = client.post("/relatos", data=dados, files=_foto(jpeg))
        assert r.status_code in (400, 422)
        assert r.json()["codigo"] != "fora_da_area"
    r = client.post("/relatos", data=_form(), files=_foto(b"isto nao e uma imagem"))
    assert r.status_code == 422 and r.json()["codigo"] == "dados_invalidos"
    r = client.post("/relatos", data=_form(descricao="x" * 1001), files=_foto(jpeg))
    assert r.status_code == 422 and r.json()["codigo"] == "dados_invalidos"


@pytest.mark.parametrize("lat,lon", [("200", "-46.6"), ("-23.5", "-200"), ("nan", "-46.6"), ("inf", "-46.6")])
def test_coordenadas_impossiveis_nunca_viram_201(client, jpeg, lat, lon):
    r = client.post("/relatos", data=_form(lat=lat, lon=lon), files=_foto(jpeg))
    assert r.status_code in (400, 422)


def test_campos_ausentes_ou_mal_tipados_400(client, jpeg):
    assert client.post("/relatos", data=_form()).status_code == 400
    assert client.post("/relatos", data=_form(lat="abc"), files=_foto(jpeg)).status_code == 400
    assert client.post("/relatos", data={"lat": "-23.55", "lon": "-46.63"}, files=_foto(jpeg)).status_code == 400


def test_fonte_invalida_e_descricao_longa_422(client, jpeg):
    r = client.post("/relatos", data=_form(fonte="drone"), files=_foto(jpeg))
    assert r.status_code == 422 and r.json()["detalhes"][0]["campo"] == "fonte"
    assert client.post("/relatos", data=_form(descricao="x" * 1001), files=_foto(jpeg)).status_code == 422


def test_descricao_e_guardada_como_recebida(client, fabrica_sessao, jpeg):
    texto = "Falar com Maria no (11) 90000-0000. CPF 000.000.000-00."  # a triagem mascara depois
    r = client.post("/relatos", data=_form(descricao=texto), files=_foto(jpeg))
    assert _linha(fabrica_sessao, r.json()["id"]).descricao == texto


def test_falha_ao_gravar_no_banco_nao_deixa_foto_orfa(montar_cliente, settings, jpeg, monkeypatch):
    from app.routers import relatos as roteador

    def quebrar(*a, **k):
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(roteador.servico, "criar", quebrar)
    r = montar_cliente(settings, raise_server_exceptions=False).post("/relatos", data=_form(), files=_foto(jpeg))
    assert r.status_code == 500 and r.json()["codigo"] == "erro_interno"
    assert not list(settings.media_dir.glob("relatos/*"))


# --- emenda rc2: autoria e token do robô ----------------------------------------------


def test_rc2_guarda_so_o_hash_do_autor(client_rc2, fabrica_sessao, settings, jpeg):
    autor = uuid.uuid4()
    r = client_rc2.post("/relatos", data=_form(autor_id=str(autor)), files=_foto(jpeg))
    assert r.status_code == 201

    linha = _linha(fabrica_sessao, r.json()["id"])
    assert linha.autor_hash == hash_autor(autor, SAL_AUTOR)
    assert len(linha.autor_hash) == 64 and str(autor) not in linha.autor_hash
    assert str(autor) not in r.text and linha.autor_hash not in r.text  # a API nunca devolve o autor
    with fabrica_sessao() as sessao:  # o id em si não está em lugar nenhum do banco
        dump = sessao.execute(text("SELECT row_to_json(r)::text FROM relatos r")).scalar()
    assert str(autor) not in dump


def test_rc2_hash_depende_do_sal(settings):
    autor = uuid.uuid4()
    assert hash_autor(autor, "sal-a") != hash_autor(autor, "sal-b")
    assert hash_autor(autor, "sal-a") == hash_autor(autor, "sal-a")
    with pytest.raises(RuntimeError):
        hash_autor(autor, "")


def test_rc2_autor_id_invalido_400(client_rc2, jpeg):
    assert client_rc2.post("/relatos", data=_form(autor_id="nao-e-uuid"), files=_foto(jpeg)).status_code == 400


def test_rc2_robo_exige_device_token(client_rc2, jpeg):
    sem = client_rc2.post("/relatos", data=_form(fonte="robo"), files=_foto(jpeg))
    assert sem.status_code == 401 and sem.json()["codigo"] == "nao_autenticado"
    errado = client_rc2.post("/relatos", data=_form(fonte="robo"), files=_foto(jpeg), headers={"X-Device-Token": "x"})
    assert errado.status_code == 401
    certo = client_rc2.post(
        "/relatos", data=_form(fonte="robo"), files=_foto(jpeg), headers={"X-Device-Token": TOKEN_DISPOSITIVO}
    )
    assert certo.status_code == 201


def test_rc2_app_continua_publico(client_rc2, jpeg):
    assert client_rc2.post("/relatos", data=_form(fonte="app"), files=_foto(jpeg)).status_code == 201


def test_rc2_robo_fica_fechado_se_o_token_nao_esta_configurado(montar_cliente, settings, jpeg):
    config = settings.model_copy(update={"habilitar_rc2": True, "device_token": ""})
    r = montar_cliente(config).post(
        "/relatos", data=_form(fonte="robo"), files=_foto(jpeg), headers={"X-Device-Token": ""}
    )
    assert r.status_code == 401


def test_sem_rc2_autor_id_e_device_token_sao_ignorados(client, fabrica_sessao, jpeg):
    r = client.post("/relatos", data=_form(fonte="robo", autor_id=str(uuid.uuid4())), files=_foto(jpeg))
    assert r.status_code == 201
    assert _linha(fabrica_sessao, r.json()["id"]).autor_hash is None


def test_rc2_exige_sal_para_subir(settings):
    from app.main import create_app

    with pytest.raises(RuntimeError, match="SALT_AUTOR"):
        create_app(settings.model_copy(update={"habilitar_rc2": True, "salt_autor": ""}))


# --- logs: nada sensível -------------------------------------------------------------


def test_log_da_requisicao_nao_vaza_dados(client_rc2, caplog, jpeg):
    autor = str(uuid.uuid4())
    descricao = "descricao-secreta-9f3a"
    caplog.set_level(logging.DEBUG)
    r = client_rc2.post(
        "/relatos",
        data=_form(lat="-23.55051234", lon="-46.63331234", descricao=descricao, autor_id=autor),
        files=_foto(jpeg),
        headers={"X-Device-Token": TOKEN_DISPOSITIVO},
    )
    assert r.status_code == 201

    formatador = FormatadorJson()
    linhas = [formatador.format(rec) for rec in caplog.records]
    tudo = "\n".join(linhas)
    for proibido in (
        descricao,
        autor,
        hash_autor(uuid.UUID(autor), SAL_AUTOR),
        "-23.5505",
        "-46.6333",
        TOKEN_DISPOSITIVO,
    ):
        assert proibido not in tudo, proibido
    assert "JFIF" not in tudo and "\\xff" not in tudo  # nenhum pedaço da foto

    requisicoes = [linha for linha in linhas if '"requisicao"' in linha]
    assert len(requisicoes) == 1  # uma linha por requisição
    import json

    registro = json.loads(requisicoes[0])
    assert registro["metodo"] == "POST" and registro["rota"] == "/relatos" and registro["status"] == 201
    assert registro["duracao_ms"] >= 0 and registro["request_id"]
