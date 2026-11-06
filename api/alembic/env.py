"""Ambiente do Alembic: usa DATABASE_URL (via app.config) e os metadados dos modelos."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.db import models  # noqa: F401  (registra as tabelas no metadata)
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Tabelas do próprio PostGIS que o Alembic não deve tentar gerenciar.
IGNORAR_TABELAS = {"spatial_ref_sys"}


def incluir_objeto(objeto, nome, tipo, reflected, compare_to):
    if tipo == "table" and nome in IGNORAR_TABELAS:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=incluir_objeto,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Em testes, a conexão pode vir pronta em config.attributes["connection"].
    conexao = config.attributes.get("connection")
    if conexao is not None:
        _migrar(conexao)
        return
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as conexao:
        _migrar(conexao)


def _migrar(conexao) -> None:
    context.configure(connection=conexao, target_metadata=target_metadata, include_object=incluir_objeto)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
