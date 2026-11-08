#!/bin/sh
# Roda na partida do contêiner, ANTES do envsubst (20-...) da imagem oficial do nginx.
# Falha cedo e com mensagem clara em vez de deixar o nginx subir com a configuração quebrada.
set -eu

ME=$(basename "$0")

if [ -z "${API_UPSTREAM:-}" ]; then
  echo "$ME: ERRO: defina API_UPSTREAM (ex.: http://ca-passoseguro-api)" >&2
  exit 1
fi

case "$API_UPSTREAM" in
  http://* | https://*) ;;
  *)
    echo "$ME: ERRO: API_UPSTREAM deve começar com http:// ou https://" >&2
    exit 1
    ;;
esac

case "$API_UPSTREAM" in
  */ | *[!A-Za-z0-9:/._-]*)
    echo "$ME: ERRO: API_UPSTREAM não pode terminar em / nem ter caracteres fora de [A-Za-z0-9:/._-]" >&2
    exit 1
    ;;
esac

# METRICS_TOKEN vazio é permitido: significa "raspagem desligada" (sempre 401).
# O valor entra num arquivo de configuração do nginx: espaço, aspas, $, ; e chaves quebrariam.
case "${METRICS_TOKEN:-}" in
  *[!A-Za-z0-9._~+/=-]*)
    echo "$ME: ERRO: METRICS_TOKEN só pode ter letras, números e . _ ~ + / = -" >&2
    exit 1
    ;;
esac

if [ -z "${METRICS_TOKEN:-}" ]; then
  echo "$ME: aviso: METRICS_TOKEN vazio, /metrics/api responderá sempre 401"
fi
