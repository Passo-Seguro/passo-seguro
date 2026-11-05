#!/usr/bin/env python3
"""Confere que o enum `Categoria` de openapi.yaml é igual, na mesma ordem, à lista de
`nome` em contratos/classes.yaml (a fonte única de verdade). Falha (código 1) se divergir.

Usa só a biblioteca padrão (sem PyYAML). Por isso espera os arquivos no formato atual:
em classes.yaml, linhas `- id: N` e `nome: x`; em openapi.yaml, o schema `Categoria`
com 4 espaços de indentação e `enum:` em lista com hífens ou entre colchetes.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CLASSES = RAIZ / "contratos" / "classes.yaml"
OPENAPI = RAIZ / "openapi.yaml"
NOME_VALIDO = re.compile(r"^[a-z][a-z0-9_]*$")


def limpar(valor: str) -> str:
    return valor.strip().strip("\"'")


def ler_classes(caminho: Path):
    texto = caminho.read_text(encoding="utf-8")
    ids = [int(i) for i in re.findall(r"^\s*-\s+id:\s*(\d+)\s*$", texto, re.M)]
    nomes = [limpar(n) for n in re.findall(r"^\s*nome:\s*(\S+)\s*$", texto, re.M)]
    return ids, nomes


def ler_enum_categoria(caminho: Path):
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    inicio = next((i for i, l in enumerate(linhas) if re.match(r"^    Categoria:\s*$", l)), None)
    if inicio is None:
        raise ValueError("schema 'Categoria' não encontrado em components/schemas")

    bloco = []
    for linha in linhas[inicio + 1 :]:
        if linha.strip() and len(linha) - len(linha.lstrip()) <= 4:
            break
        bloco.append(linha)

    for i, linha in enumerate(bloco):
        m = re.match(r"^\s+enum:\s*(.*)$", linha)
        if not m:
            continue
        if m.group(1).startswith("["):
            return [limpar(x) for x in m.group(1).strip("[] ").split(",") if x.strip()]
        valores = []
        for item in bloco[i + 1 :]:
            m_item = re.match(r"^\s+-\s+(\S+)\s*$", item)
            if not m_item:
                break
            valores.append(limpar(m_item.group(1)))
        return valores
    raise ValueError("'enum' não encontrado no schema 'Categoria'")


def main() -> int:
    erros = []
    ids, nomes = ler_classes(CLASSES)
    try:
        enum = ler_enum_categoria(OPENAPI)
    except ValueError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1

    if not nomes:
        erros.append(f"nenhuma classe encontrada em {CLASSES.name}")
    if ids != list(range(len(nomes))):
        erros.append(f"os 'id' de {CLASSES.name} devem ser 0..{len(nomes) - 1} em ordem, mas são {ids}")
    for nome in nomes:
        if not NOME_VALIDO.match(nome):
            erros.append(f"nome de classe inválido '{nome}' (use snake_case, minúsculo, sem acento)")
    if enum != nomes:
        erros.append(
            "o enum 'Categoria' de openapi.yaml diverge de classes.yaml\n"
            f"    classes.yaml: {nomes}\n"
            f"    openapi.yaml: {enum}"
        )

    if erros:
        for e in erros:
            print(f"ERRO: {e}", file=sys.stderr)
        return 1
    print(f"OK: {len(nomes)} classes iguais e na mesma ordem em classes.yaml e openapi.yaml: {', '.join(nomes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
