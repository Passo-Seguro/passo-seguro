#!/usr/bin/env bash
# Valida os contratos: lint do openapi.yaml (Redocly) e conferência das classes.
# Falha (código diferente de 0) se houver qualquer erro.
#
# Uso: scripts/validar-contratos.sh
# Requer: Node.js (npx) e Python 3.
set -euo pipefail

cd "$(dirname "$0")/.."

REDOCLY_VERSION="2.64.1"

echo "==> Lint do openapi.yaml (Redocly CLI ${REDOCLY_VERSION})"
npx --yes "@redocly/cli@${REDOCLY_VERSION}" lint openapi.yaml

PY=""
for candidato in python3 python; do
  if command -v "$candidato" >/dev/null 2>&1 \
    && "$candidato" -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
    PY="$candidato"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "ERRO: Python 3 não encontrado (necessário para checar as classes)." >&2
  exit 1
fi

echo "==> Classes: openapi.yaml x contratos/classes.yaml"
"$PY" scripts/checar-classes.py

echo "==> Contratos válidos."
