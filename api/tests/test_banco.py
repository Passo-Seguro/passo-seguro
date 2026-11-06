"""Migrações do Alembic, regras do banco (constraints) e gerador de dados simulados com Postgres."""

import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Relato
from app.services import simulacao
from app.services.simulacao import AREAS_NOMEADAS, DISTRIBUICAO_CLASSES_PADRAO
from app.storage import ArmazenamentoLocal
from tests.conftest import API_DIR, URL_TESTE, recriar_banco

# --- migrações -----------------------------------------------------------------------


def test_modelos_e_migracoes_estao_em_sincronia(engine_banco):
    """Se alguém muda o modelo e esquece a migração, este teste acusa a diferença."""

    def sem_tabelas_do_postgis(objeto, nome, tipo, reflected, compare_to):
        return not (tipo == "table" and nome == "spatial_ref_sys")

    with engine_banco.connect() as conexao:
        contexto = MigrationContext.configure(
            conexao, opts={"compare_type": True, "include_object": sem_tabelas_do_postgis}
        )
        diferencas = compare_metadata(contexto, Base.metadata)
    assert diferencas == [], f"o modelo difere das migrações: {diferencas}"


def test_migracoes_sobem_descem_e_sobem_de_novo():
    url = make_url(URL_TESTE)
    scratch = url.set(database=f"{url.database}_migracoes").render_as_string(hide_password=False)
    recriar_banco(scratch)  # já sobe até o head
    engine = create_engine(scratch)
    try:
        cfg = Config(str(API_DIR / "alembic.ini"))
        with engine.connect() as conexao:
            cfg.attributes["connection"] = conexao
            command.downgrade(cfg, "base")
            conexao.commit()
            assert "relatos" not in inspect(conexao).get_table_names()
            command.upgrade(cfg, "head")
            conexao.commit()
            colunas = {c["name"] for c in inspect(conexao).get_columns("relatos")}
        assert {"id", "criado_em", "localizacao", "autor_hash", "atualizado_em", "simulado", "foto_chave"} <= colunas
    finally:
        engine.dispose()


def test_indice_espacial_gist_existe(engine_banco):
    with engine_banco.connect() as conexao:
        definicao = conexao.scalar(text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_relatos_localizacao'"))
    assert definicao and "USING gist" in definicao


# --- constraints (o banco também se defende) -------------------------------------------


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("categoria", "cratera"),
        ("status", "perdido"),
        ("fonte", "drone"),
        ("prioridade", "urgente"),
        ("confianca", 1.5),
        ("confianca", -0.1),
        ("confirmacoes", -1),
    ],
)
def test_constraints_recusam_valores_fora_do_contrato(fabrica_sessao, campo, valor):
    with fabrica_sessao() as sessao:
        campos = {"foto_chave": "relatos/x.jpg", "fonte": "app", campo: valor}
        sessao.add(Relato(localizacao=func.ST_GeogFromText("SRID=4326;POINT(-46.6333 -23.5505)"), **campos))
        with pytest.raises(IntegrityError):
            sessao.commit()


def test_valores_padrao_do_banco(fabrica_sessao):
    with fabrica_sessao() as sessao:
        sessao.execute(
            text(
                "INSERT INTO relatos (id, localizacao, foto_chave, fonte) "
                "VALUES (:i, ST_GeogFromText('SRID=4326;POINT(-46.63 -23.55)'), 'x.jpg', 'app')"
            ),
            {"i": uuid.uuid4()},
        )
        sessao.commit()
        r = sessao.scalars(select(Relato)).one()
    assert (r.status, r.confirmacoes, r.simulado, r.categoria, r.autor_hash) == ("novo", 0, False, None, None)
    assert r.criado_em and r.atualizado_em


# --- dados simulados no banco ------------------------------------------------------------

REF = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
AREAS = [AREAS_NOMEADAS["se"], AREAS_NOMEADAS["pinheiros"]]


def test_gerar_inserir_ignorar_repeticao_e_apagar_so_os_simulados(fabrica_sessao, criar_relato_db):
    real = criar_relato_db(simulado=False)
    linhas = simulacao.gerar_relatos(120, AREAS, DISTRIBUICAO_CLASSES_PADRAO, seed=7, referencia=REF)

    with fabrica_sessao() as sessao:
        assert simulacao.inserir_relatos(sessao, linhas) == 120
        assert simulacao.inserir_relatos(sessao, linhas) == 0  # mesma semente: nada duplica
        assert simulacao.contar_simulados(sessao) == 120
        assert sessao.scalar(select(func.count()).select_from(Relato)) == 121
        # o que foi gravado respeita as regras do contrato
        assert (
            sessao.scalar(
                select(func.count())
                .select_from(Relato)
                .where(Relato.simulado, Relato.status.in_(["novo", "revisao_humana"]), Relato.prioridade.isnot(None))
            )
            == 0
        )

        assert simulacao.apagar_simulados(sessao) == 120
        restantes = sessao.scalars(select(Relato)).all()
    assert [r.id for r in restantes] == [real]  # o relato real não foi tocado


def test_relatos_simulados_aparecem_na_api_e_no_mapa(client_rc2, auth, fabrica_sessao):
    with fabrica_sessao() as sessao:
        simulacao.inserir_relatos(
            sessao, simulacao.gerar_relatos(50, [AREAS_NOMEADAS["se"]], DISTRIBUICAO_CLASSES_PADRAO, 1, REF)
        )
    assert client_rc2.get("/relatos", headers=auth).json()["paginacao"]["total_itens"] == 50
    proximos = client_rc2.get("/relatos/proximos", params={"lat": -23.5505, "lon": -46.6333, "raio_m": 5000}).json()
    assert 0 < len(proximos) <= 50
    assert '"simulado"' not in client_rc2.get("/relatos", headers=auth).text  # o campo interno não sai pela API


def test_foto_placeholder_e_gravada_e_servida(client, settings):
    armazenamento = ArmazenamentoLocal(settings.media_dir, settings.public_base_url)
    simulacao.garantir_foto_placeholder(armazenamento)
    r = client.get(f"/fotos/{simulacao.FOTO_PLACEHOLDER}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"


def test_sessionmaker_de_teste_enxerga_o_mesmo_banco(engine_banco):
    assert sessionmaker(bind=engine_banco)().execute(text("SELECT postgis_version()")).scalar()
