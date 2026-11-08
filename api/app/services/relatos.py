"""Acesso ao banco para relatos (consultas e gravações). Sem regra de HTTP aqui."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from geoalchemy2 import Geography, Geometry
from sqlalchemy import Select, cast, func, select
from sqlalchemy.orm import Session

from app.db.models import Relato
from app.dominio import ModoDeteccao, StatusRelato
from app.schemas.relatos import Relato as RelatoSchema
from app.storage import Armazenamento

# Máximo de pontos devolvidos por /relatos/proximos (os mais próximos primeiro).
LIMITE_PROXIMOS = 1000
# Máximo de relatos devolvidos por /meus-relatos (os mais recentes primeiro).
LIMITE_MEUS = 100

_geometria = cast(Relato.localizacao, Geometry("POINT", srid=4326))
_LAT = func.ST_Y(_geometria).label("lat")
_LON = func.ST_X(_geometria).label("lon")


@dataclass(frozen=True)
class LinhaRelato:
    relato: Relato
    lat: float
    lon: float


def _com_coordenadas() -> Select:
    return select(Relato, _LAT, _LON)


def _linhas(resultado) -> list[LinhaRelato]:
    return [LinhaRelato(r, lat, lon) for r, lat, lon in resultado.all()]


def criar(
    db: Session,
    *,
    id: uuid.UUID,
    lat: float,
    lon: float,
    foto_chave: str,
    descricao: str | None,
    fonte: str,
    categoria: str | None,
    confianca: float | None,
    autor_hash: str | None,
    modo_deteccao: ModoDeteccao = ModoDeteccao.NENHUMA,
) -> Relato:
    """Insere o relato SEMPRE com status `novo` (a regra de revisão por confiança é da triagem)."""
    relato = Relato(
        id=id,
        localizacao=func.ST_GeogFromText(f"SRID=4326;POINT({lon!r} {lat!r})"),
        foto_chave=foto_chave,
        descricao=descricao,
        categoria=categoria,
        confianca=confianca,
        fonte=fonte,
        status=StatusRelato.NOVO.value,
        confirmacoes=0,
        autor_hash=autor_hash,
        simulado=False,
        modo_deteccao=modo_deteccao.value,
    )
    db.add(relato)
    db.commit()
    return relato


def listar(
    db: Session, *, status: str | None, criado_desde: datetime | None, pagina: int, tamanho: int
) -> tuple[list[LinhaRelato], int]:
    """Página de relatos do mais antigo para o mais recente, e o total que atende ao filtro."""
    filtros = []
    if status is not None:
        filtros.append(Relato.status == status)
    if criado_desde is not None:
        filtros.append(Relato.criado_em >= criado_desde)
    total = db.scalar(select(func.count()).select_from(Relato).where(*filtros)) or 0
    deslocamento = (pagina - 1) * tamanho
    if deslocamento >= total:
        # Além do fim (inclusive páginas absurdas, que estourariam o OFFSET do banco): vazio.
        return [], total
    consulta = (
        _com_coordenadas()
        .where(*filtros)
        .order_by(Relato.criado_em, Relato.id)  # id desempata: a leitura página a página não pula nem repete
        .offset(deslocamento)
        .limit(tamanho)
    )
    return _linhas(db.execute(consulta)), total


def buscar(db: Session, id: uuid.UUID, *, travar: bool = False) -> LinhaRelato | None:
    consulta = _com_coordenadas().where(Relato.id == id)
    if travar:
        consulta = consulta.with_for_update(of=Relato)
    linhas = _linhas(db.execute(consulta))
    return linhas[0] if linhas else None


def proximos(db: Session, *, lat: float, lon: float, raio_m: int) -> list[LinhaRelato]:
    """Relatos (menos os rejeitados) num raio em METROS, do mais próximo ao mais distante."""
    centro = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    consulta = (
        _com_coordenadas()
        .where(func.ST_DWithin(Relato.localizacao, centro, raio_m))
        .where(Relato.status != StatusRelato.REJEITADO.value)
        .order_by(func.ST_Distance(Relato.localizacao, centro), Relato.id)
        .limit(LIMITE_PROXIMOS)
    )
    return _linhas(db.execute(consulta))


def do_autor(db: Session, autor_hash: str) -> list[Relato]:
    consulta = (
        select(Relato)
        .where(Relato.autor_hash == autor_hash)
        .order_by(Relato.criado_em.desc(), Relato.id)
        .limit(LIMITE_MEUS)
    )
    return list(db.scalars(consulta))


def aplicar_alteracoes(db: Session, relato: Relato, campos: dict) -> None:
    for nome, valor in campos.items():
        setattr(relato, nome, valor.value if hasattr(valor, "value") else valor)
    db.commit()


def para_schema(linha: LinhaRelato, armazenamento: Armazenamento) -> RelatoSchema:
    r = linha.relato
    return RelatoSchema(
        id=r.id,
        criado_em=r.criado_em,
        lat=linha.lat,
        lon=linha.lon,
        foto_url=armazenamento.url(r.foto_chave),
        descricao=r.descricao,
        categoria=r.categoria,
        confianca=r.confianca,
        fonte=r.fonte,
        status=r.status,
        confirmacoes=r.confirmacoes,
        subprefeitura=r.subprefeitura,
        prioridade=r.prioridade,
    )
