#!/usr/bin/env python3
"""Popula (ou limpa) o banco com relatos SIMULADOS, para o mapa não começar vazio.

Os relatos são fictícios e marcados com `simulado = true`. Veja docs/dados-simulados.md.

Exemplos (a partir da raiz do repositório, com o ambiente da API ativo e o banco no ar):

    python scripts/gerar_dados_simulados.py                          # 300 relatos em Sé e Pinheiros
    python scripts/gerar_dados_simulados.py --quantidade 50 --seed 7
    python scripts/gerar_dados_simulados.py --area se --area "Mooca:-23.5700,-46.6150,-23.5400,-46.5800"
    python scripts/gerar_dados_simulados.py --distribuicao-classes buraco=50,piso_danificado=50
    python scripts/gerar_dados_simulados.py --apagar                 # remove só os simulados

A conexão vem de DATABASE_URL (variável de ambiente ou api/.env).
"""

import argparse
import os
import sys
from datetime import datetime, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API = RAIZ / "api"
# O script usa o código da API. Rodar "dentro" de api/ faz o .env e o MEDIA_DIR relativos
# valerem do mesmo jeito que valem para a API.
sys.path.insert(0, str(API))
os.chdir(API)

from app.config import get_settings  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.services import simulacao  # noqa: E402
from app.storage import criar_armazenamento  # noqa: E402
from app.services.simulacao import (  # noqa: E402
    AREAS_PADRAO,
    DISTRIBUICAO_CLASSES_PADRAO,
)

PADRAO_DISTRIBUICAO = ",".join(f"{c.value}={int(p)}" for c, p in DISTRIBUICAO_CLASSES_PADRAO.items())


def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Gera relatos simulados (fictícios) no banco, marcados com simulado=true.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--quantidade", type=int, default=300, help="quantos relatos gerar (padrão: 300)")
    p.add_argument(
        "--area",
        action="append",
        metavar="AREA",
        help=(
            "onde sortear os pontos; pode repetir. Valores: 'se', 'pinheiros' ou uma caixa "
            "'[nome:]lat_min,lon_min,lat_max,lon_max'. Padrão: Sé e Pinheiros."
        ),
    )
    p.add_argument(
        "--distribuicao-classes",
        default=PADRAO_DISTRIBUICAO,
        metavar="CLASSE=PESO,...",
        help=f"pesos relativos de cada classe (padrão: {PADRAO_DISTRIBUICAO})",
    )
    p.add_argument("--seed", type=int, default=42, help="semente do sorteio; mesma semente, mesmos dados (padrão: 42)")
    p.add_argument(
        "--referencia",
        metavar="AAAA-MM-DD",
        help="data de 'hoje' para calcular o criado_em dos relatos (padrão: hoje)",
    )
    p.add_argument("--apagar", action="store_true", help="em vez de gerar, apaga TODOS os relatos simulados")
    return p


def main() -> int:
    args = montar_parser().parse_args()
    sessionmaker = get_sessionmaker()

    if args.apagar:
        with sessionmaker() as sessao:
            apagados = simulacao.apagar_simulados(sessao)
        print(f"{apagados} relato(s) simulado(s) apagado(s). Relatos reais não foram tocados.")
        return 0

    try:
        areas = [simulacao.ler_area(a) for a in (args.area or AREAS_PADRAO)]
        distribuicao = simulacao.ler_distribuicao(args.distribuicao_classes)
        referencia = (
            datetime.combine(datetime.strptime(args.referencia, "%Y-%m-%d").date(), time(12, 0))
            if args.referencia
            else datetime.combine(datetime.now().date(), time(12, 0))
        ).astimezone()
        linhas = simulacao.gerar_relatos(args.quantidade, areas, distribuicao, args.seed, referencia)
    except ValueError as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 2

    simulacao.garantir_foto_placeholder(criar_armazenamento(get_settings()))
    with sessionmaker() as sessao:
        inseridos = simulacao.inserir_relatos(sessao, linhas)
        total = simulacao.contar_simulados(sessao)
    ignorados = len(linhas) - inseridos
    print(
        f"{inseridos} relato(s) simulado(s) inserido(s)"
        + (f" ({ignorados} já existiam e foram ignorados)" if ignorados else "")
        + f". Total de simulados no banco: {total}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
