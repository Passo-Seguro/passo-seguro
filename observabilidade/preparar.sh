#!/usr/bin/env bash
# Prepara o Prometheus local: gera prometheus/alvos/api.json a partir de PUBLIC_URL (no .env ou
# na variável de ambiente) e confere o arquivo metrics-token. Rode antes do "docker compose up".
set -euo pipefail
cd "$(dirname "$0")"

if [[ -z "${PUBLIC_URL:-}" && -f .env ]]; then
  PUBLIC_URL="$(grep -E '^PUBLIC_URL=' .env | tail -n1 | cut -d= -f2- | tr -d '\r"'"'"'')"
fi
if [[ -z "${PUBLIC_URL:-}" ]]; then
  echo "Defina PUBLIC_URL no .env (cp .env.example .env) ou na variável de ambiente." >&2
  exit 1
fi

# https://app.exemplo.io/  ->  app.exemplo.io   (o esquema https fica no prometheus.yml)
alvo="${PUBLIC_URL#http://}"
alvo="${alvo#https://}"
alvo="${alvo%%/*}"
if [[ -z "$alvo" || "$alvo" == *[[:space:]]* ]]; then
  echo "PUBLIC_URL inválida: '$PUBLIC_URL'" >&2
  exit 1
fi

mkdir -p prometheus/alvos
printf '[{"targets": ["%s"], "labels": {"servico": "passo-seguro"}}]\n' "$alvo" > prometheus/alvos/api.json
echo "Alvo do Prometheus: https://$alvo/metrics/api"

if [[ ! -s metrics-token ]]; then
  cat >&2 <<MSG

Falta o arquivo observabilidade/metrics-token (o git o ignora). Ele guarda só o token, sem o
prefixo "Bearer". Para buscá-lo no Key Vault (nome em: terraform output key_vault_name):

  az keyvault secret show --vault-name <key-vault> --name metrics-token --query value -o tsv | tr -d '\r\n' > metrics-token

MSG
  exit 1
fi
# O contêiner do Prometheus roda como outro usuário e precisa conseguir ler o arquivo.
chmod 644 metrics-token 2>/dev/null || true
echo "metrics-token encontrado."
