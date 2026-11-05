#!/usr/bin/env bash
# Sobe o mock da API a partir do openapi.yaml, em http://localhost:4010 (Prism).
#
# Uso: scripts/mock.sh
# Requer: Node.js (npx).
#
# Dicas:
#   - Escolher um exemplo:           curl -H 'Prefer: example=obstaculo' ...
#   - Escolher um código de resposta: curl -H 'Prefer: code=422' ...
#   - Endpoints protegidos (GET /relatos, POST /deteccoes, PATCH /relatos/{id} da triagem) exigem
#     'Authorization: Bearer <qualquer-valor>' (use um valor fictício; não coloque tokens reais).
#   - PATCH /relatos/{id} no modo app aceita 'X-Autor-Id: <uuid>' no lugar do bearer.
#   - GET /meus-relatos exige o cabeçalho 'X-Autor-Id: <uuid>'.
#   - Bateria de curls contra o mock: scripts/testar-mock.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PRISM_VERSION="5.16.0"

exec npx --yes "@stoplight/prism-cli@${PRISM_VERSION}" mock -p 4010 openapi.yaml
