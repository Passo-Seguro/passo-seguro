"""Geração de relatos SIMULADOS (fictícios) para o mapa não começar vazio.

Tudo que sai daqui tem `simulado = true` no banco, o que permite separar e apagar depois
(ver docs/dados-simulados.md). A geração é determinística: a mesma combinação de
parâmetros (incluindo `seed` e a data de referência) produz sempre os mesmos relatos.

Telefones e CPFs que aparecem em algumas descrições são claramente FALSOS (zeros), de
propósito: servem para a triagem (RPA) demonstrar o mascaramento de dados pessoais.
"""

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO

from geoalchemy2 import WKTElement
from PIL import Image, ImageDraw
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Relato
from app.dominio import Categoria, FonteRelato, Prioridade, StatusRelato
from app.storage import Armazenamento

FOTO_PLACEHOLDER = "simulados/placeholder.png"


@dataclass(frozen=True)
class Area:
    """Retângulo (bounding box) onde os relatos são sorteados. Aproximado, não oficial."""

    nome: str
    lat_min: float
    lon_min: float
    lat_max: float
    lon_max: float

    def __post_init__(self) -> None:
        if not (self.lat_min < self.lat_max and self.lon_min < self.lon_max):
            raise ValueError("área inválida: os mínimos devem ser menores que os máximos")
        if not (-90 <= self.lat_min and self.lat_max <= 90 and -180 <= self.lon_min and self.lon_max <= 180):
            raise ValueError("área inválida: coordenadas fora do intervalo")


AREAS_NOMEADAS: dict[str, Area] = {
    "se": Area("Sé", -23.5700, -46.6600, -23.5250, -46.6150),
    "pinheiros": Area("Pinheiros", -23.5800, -46.7200, -23.5400, -46.6700),
}
AREAS_PADRAO = ["se", "pinheiros"]

DISTRIBUICAO_CLASSES_PADRAO: dict[Categoria, float] = {
    Categoria.BURACO: 25,
    Categoria.PISO_DANIFICADO: 40,
    Categoria.OBSTACULO: 20,
    Categoria.VEICULO_NA_CALCADA: 15,
}

_STATUS_PESOS: dict[StatusRelato, float] = {
    StatusRelato.NOVO: 40,
    StatusRelato.REVISAO_HUMANA: 8,
    StatusRelato.VALIDADO: 10,
    StatusRelato.ENCAMINHADO: 25,
    StatusRelato.RESOLVIDO: 12,
    StatusRelato.REJEITADO: 5,
}
_COM_ENCAMINHAMENTO = {StatusRelato.ENCAMINHADO, StatusRelato.RESOLVIDO}
_PESO_DA_CLASSE = {
    Categoria.BURACO: 3,
    Categoria.PISO_DANIFICADO: 2,
    Categoria.OBSTACULO: 2,
    Categoria.VEICULO_NA_CALCADA: 1,
}
_DESCRICOES: dict[Categoria | None, list[str]] = {
    Categoria.BURACO: [
        "Buraco aberto na calçada, perigoso para quem anda com criança.",
        "Falta um pedaço do piso e dá para ver a terra.",
        "Bueiro sem tampa no meio da calçada.",
    ],
    Categoria.PISO_DANIFICADO: [
        "Lajes soltas balançando quando a gente pisa.",
        "Raiz da árvore levantou o piso.",
        "Piso tátil quebrado perto do ponto de ônibus.",
    ],
    Categoria.OBSTACULO: [
        "Entulho de obra ocupando a calçada inteira.",
        "Poste no meio da faixa de passagem.",
        "Mesas do bar tomando a calçada toda.",
    ],
    Categoria.VEICULO_NA_CALCADA: [
        "Carro estacionado em cima da calçada.",
        "Moto parada na calçada, não passa carrinho de bebê.",
        "Caminhão de entrega parado sobre o passeio.",
    ],
    None: ["Tem algo estranho na calçada, não sei explicar."],
}
_SUFIXOS_PESSOAIS = [
    " Falar com Maria no (11) 90000-0000.",
    " CPF do morador 000.000.000-00.",
]


# --- leitura dos parâmetros de linha de comando ---------------------------------------


def ler_area(texto: str) -> Area:
    """Aceita 'se', 'pinheiros' ou '[nome:]lat_min,lon_min,lat_max,lon_max'."""
    chave = texto.strip().lower()
    if chave in AREAS_NOMEADAS:
        return AREAS_NOMEADAS[chave]
    nome, _, numeros = texto.rpartition(":")
    nome = nome.strip() or "Área simulada"
    try:
        lat_min, lon_min, lat_max, lon_max = (float(p) for p in numeros.split(","))
    except ValueError:
        raise ValueError(
            f"área '{texto}' inválida: use 'se', 'pinheiros' ou '[nome:]lat_min,lon_min,lat_max,lon_max'"
        ) from None
    return Area(nome, lat_min, lon_min, lat_max, lon_max)


def ler_distribuicao(texto: str) -> dict[Categoria, float]:
    """Lê 'buraco=25,piso_danificado=40,...'. Pesos relativos (não precisam somar 100)."""
    pesos: dict[Categoria, float] = {}
    for par in texto.split(","):
        nome, igual, valor = par.partition("=")
        if not igual:
            raise ValueError(f"distribuição inválida em '{par}': use classe=peso")
        try:
            categoria = Categoria(nome.strip())
            peso = float(valor)
        except ValueError:
            raise ValueError(f"distribuição inválida em '{par}': classe desconhecida ou peso não numérico") from None
        if peso < 0:
            raise ValueError(f"distribuição inválida em '{par}': peso negativo")
        pesos[categoria] = peso
    if sum(pesos.values()) <= 0:
        raise ValueError("distribuição inválida: a soma dos pesos deve ser maior que zero")
    return pesos


# --- geração (pura, sem banco) --------------------------------------------------------


def _ponto(rng: random.Random, area: Area, centros: list[tuple[float, float]]) -> tuple[float, float]:
    """Sorteia (lat, lon): 70% em torno de pontos quentes (aglomeração), 30% uniforme."""
    if rng.random() < 0.7:
        lat_c, lon_c = rng.choice(centros)
        for _ in range(10):
            lat, lon = rng.gauss(lat_c, 0.0035), rng.gauss(lon_c, 0.0035)
            if area.lat_min <= lat <= area.lat_max and area.lon_min <= lon <= area.lon_max:
                return lat, lon
    return rng.uniform(area.lat_min, area.lat_max), rng.uniform(area.lon_min, area.lon_max)


def gerar_relatos(
    quantidade: int,
    areas: list[Area],
    distribuicao: dict[Categoria, float],
    seed: int,
    referencia: datetime,
) -> list[dict]:
    """Devolve `quantidade` linhas (dicts) prontas para inserir em `relatos`. Sem banco."""
    if quantidade < 0:
        raise ValueError("quantidade não pode ser negativa")
    if not areas:
        raise ValueError("informe ao menos uma área")
    rng = random.Random(seed)
    centros = {
        a: [(rng.uniform(a.lat_min, a.lat_max), rng.uniform(a.lon_min, a.lon_max)) for _ in range(4)] for a in areas
    }
    classes = list(distribuicao)
    pesos_classes = [distribuicao[c] for c in classes]
    status_lista = list(_STATUS_PESOS)
    pesos_status = list(_STATUS_PESOS.values())

    linhas: list[dict] = []
    for _ in range(quantidade):
        area = rng.choice(areas)
        lat, lon = _ponto(rng, area, centros[area])
        sem_deteccao = rng.random() < 0.05
        categoria = None if sem_deteccao else rng.choices(classes, pesos_classes)[0]
        confianca = None if sem_deteccao else round(rng.uniform(0.35, 0.99), 2)
        status = rng.choices(status_lista, pesos_status)[0]
        encaminhado = status in _COM_ENCAMINHAMENTO
        if encaminhado:
            confirmacoes = rng.choices([0, 1, 2, 3, 5, 8], [30, 25, 20, 12, 8, 5])[0]
        else:
            confirmacoes = rng.choices([0, 1, 2], [80, 15, 5])[0]
        prioridade = None
        if encaminhado:
            pontos = (_PESO_DA_CLASSE[categoria] if categoria else 1) + confirmacoes
            prioridade = (
                Prioridade.ALTA if pontos >= 5 else Prioridade.MEDIA if pontos >= 3 else Prioridade.BAIXA
            ).value
        idade = timedelta(
            seconds=rng.uniform(15 * 86400, 60 * 86400)
            if status == StatusRelato.RESOLVIDO
            else rng.uniform(0, 45 * 86400)
        )
        descricao = None
        if rng.random() >= 0.3:
            descricao = rng.choice(_DESCRICOES[categoria])
            if rng.random() < 0.07:
                descricao += rng.choice(_SUFIXOS_PESSOAIS)
        linhas.append(
            {
                "id": uuid.UUID(int=rng.getrandbits(128), version=4),
                "criado_em": referencia - idade,
                "localizacao": WKTElement(f"POINT({lon:.6f} {lat:.6f})", srid=4326),
                "foto_chave": FOTO_PLACEHOLDER,
                "descricao": descricao,
                "categoria": categoria.value if categoria else None,
                "confianca": confianca,
                "fonte": (FonteRelato.ROBO if rng.random() < 0.15 else FonteRelato.APP).value,
                "status": status.value,
                "confirmacoes": confirmacoes,
                "subprefeitura": area.nome if encaminhado else None,
                "prioridade": prioridade,
                "simulado": True,
            }
        )
    return linhas


# --- banco e armazenamento ------------------------------------------------------------


def garantir_foto_placeholder(armazenamento: Armazenamento) -> None:
    """Grava a imagem cinza 'Foto simulada' usada por todos os relatos simulados."""
    imagem = Image.new("RGB", (800, 600), (214, 217, 222))
    ImageDraw.Draw(imagem).text((40, 40), "Foto simulada", fill=(60, 64, 70))
    saida = BytesIO()
    imagem.save(saida, "PNG", optimize=True)
    armazenamento.salvar(FOTO_PLACEHOLDER, saida.getvalue(), "image/png")


def inserir_relatos(sessao: Session, linhas: list[dict]) -> int:
    """Insere as linhas (ignora ids repetidos). Devolve quantas foram realmente inseridas."""
    if not linhas:
        return 0
    comando = pg_insert(Relato).on_conflict_do_nothing(index_elements=["id"]).returning(Relato.id)
    inseridos = sessao.execute(comando, linhas).all()
    sessao.commit()
    return len(inseridos)


def apagar_simulados(sessao: Session) -> int:
    """Apaga TODOS os relatos com `simulado = true`. Relatos reais não são tocados."""
    apagados = sessao.execute(delete(Relato).where(Relato.simulado.is_(True))).rowcount
    sessao.commit()
    return apagados


def contar_simulados(sessao: Session) -> int:
    return sessao.scalar(select(func.count()).select_from(Relato).where(Relato.simulado.is_(True))) or 0
