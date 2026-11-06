"""Dados de EXEMPLO (os do contrato) usados na Etapa 1, antes de ligar o banco real.

Tudo aqui é fictício: telefones e CPFs são claramente falsos (zeros).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.dominio import Categoria, FonteRelato, Prioridade, StatusRelato
from app.schemas.painel import PrioridadeSubprefeitura
from app.schemas.relatos import Relato

_BRT = timezone(timedelta(hours=-3))
_FOTOS = "https://fotos.exemplo.invalid/relatos"


def _relato(
    id_: str,
    criado: str,
    lat: float,
    lon: float,
    descricao: str | None,
    categoria,
    confianca,
    fonte,
    status,
    confirmacoes=0,
    subprefeitura=None,
    prioridade=None,
) -> Relato:
    return Relato(
        id=UUID(id_),
        criado_em=datetime.fromisoformat(criado).astimezone(_BRT),
        lat=lat,
        lon=lon,
        foto_url=f"{_FOTOS}/{id_[:8]}.jpg",
        descricao=descricao,
        categoria=categoria,
        confianca=confianca,
        fonte=fonte,
        status=status,
        confirmacoes=confirmacoes,
        subprefeitura=subprefeitura,
        prioridade=prioridade,
    )


RELATOS_EXEMPLO: list[Relato] = sorted(
    [
        _relato(
            "0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01",
            "2026-11-04T14:32:10-03:00",
            -23.5505,
            -46.6333,
            "Buraco grande na calçada em frente ao número 120.",
            Categoria.BURACO,
            0.94,
            FonteRelato.APP,
            StatusRelato.NOVO,
        ),
        _relato(
            "5d1c7e22-93aa-4b0e-b7c1-2e4f8a6d9c10",
            "2026-11-04T14:51:42-03:00",
            -23.5489,
            -46.6388,
            "Lajes soltas, quase caí. Falar com Maria no (11) 90000-0000.",
            Categoria.PISO_DANIFICADO,
            0.88,
            FonteRelato.APP,
            StatusRelato.NOVO,
        ),
        _relato(
            "a47e90b5-6c3f-4d18-9a2b-7f1e3c5d8e22",
            "2026-11-04T15:08:03-03:00",
            -23.5672,
            -46.6916,
            "Entulho de obra ocupando toda a calçada. CPF do morador 000.000.000-00.",
            Categoria.OBSTACULO,
            0.81,
            FonteRelato.APP,
            StatusRelato.NOVO,
        ),
        _relato(
            "c92d4f61-0b8e-47a3-a5d6-1e9b7f3a2c33",
            "2026-11-04T15:40:27-03:00",
            -23.5649,
            -46.6952,
            None,
            Categoria.VEICULO_NA_CALCADA,
            0.97,
            FonteRelato.ROBO,
            StatusRelato.NOVO,
        ),
        _relato(
            "e3a85c17-2d4b-4f90-8c61-9b0d6e7f1a44",
            "2026-11-04T16:05:51-03:00",
            -23.5661,
            -46.6931,
            "Calçada com algo estranho, não sei explicar.",
            None,
            None,
            FonteRelato.APP,
            StatusRelato.NOVO,
        ),
        _relato(
            "7a2e5b90-4f13-4c68-b0d7-3c8a1e6f9d55",
            "2026-11-02T09:12:30-03:00",
            -23.5503,
            -46.6339,
            "Piso afundado perto do ponto de ônibus.",
            Categoria.PISO_DANIFICADO,
            0.91,
            FonteRelato.APP,
            StatusRelato.ENCAMINHADO,
            4,
            "Sé",
            Prioridade.ALTA,
        ),
        _relato(
            "9c4d1f08-5e27-4a39-8b6e-0d2f7a3c1b66",
            "2026-10-28T17:45:00-03:00",
            -23.5668,
            -46.6925,
            None,
            Categoria.VEICULO_NA_CALCADA,
            0.95,
            FonteRelato.ROBO,
            StatusRelato.RESOLVIDO,
            2,
            "Pinheiros",
            Prioridade.MEDIA,
        ),
        _relato(
            "b1e8a3c4-7f20-4d5b-9c36-8a4e2f1d0b77",
            "2026-11-03T11:20:00-03:00",
            -23.5521,
            -46.6354,
            "Poste no meio da calçada, não passa cadeira de rodas.",
            Categoria.OBSTACULO,
            0.42,
            FonteRelato.APP,
            StatusRelato.REVISAO_HUMANA,
        ),
        _relato(
            "d6f2b9a1-3c58-4e07-a1d4-5b7c9e0f2a88",
            "2026-11-03T18:02:44-03:00",
            -23.5577,
            -46.6881,
            "Raiz de árvore levantou o piso.",
            Categoria.PISO_DANIFICADO,
            0.79,
            FonteRelato.APP,
            StatusRelato.VALIDADO,
        ),
    ],
    key=lambda r: r.criado_em,
)

PAINEL_EXEMPLO: list[PrioridadeSubprefeitura] = [
    PrioridadeSubprefeitura(
        subprefeitura="Sé",
        prioridade=Prioridade.ALTA,
        relatos_abertos=69,
        relatos_por_categoria={
            Categoria.BURACO: 12,
            Categoria.PISO_DANIFICADO: 31,
            Categoria.OBSTACULO: 9,
            Categoria.VEICULO_NA_CALCADA: 17,
        },
        tempo_medio_ate_reparo_dias=41.5,
        atualizado_em=datetime(2026, 11, 4, 6, 0, tzinfo=_BRT),
    ),
    PrioridadeSubprefeitura(
        subprefeitura="Pinheiros",
        prioridade=Prioridade.MEDIA,
        relatos_abertos=38,
        relatos_por_categoria={
            Categoria.BURACO: 5,
            Categoria.PISO_DANIFICADO: 14,
            Categoria.OBSTACULO: 11,
            Categoria.VEICULO_NA_CALCADA: 8,
        },
        tempo_medio_ate_reparo_dias=None,
        atualizado_em=datetime(2026, 11, 4, 6, 0, tzinfo=_BRT),
    ),
]
