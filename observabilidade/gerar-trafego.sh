#!/usr/bin/env bash
# Gera tráfego contra o app (e, por ele, contra a API) para o painel ter dados e para o teste dos
# alertas. Em rodízio, chama: /, /api/painel e /api/relatos/proximos.
#
# Uso:
#   ./gerar-trafego.sh                      # 2 req/s até Ctrl+C, em PUBLIC_URL do .env
#   RPS=5 DURACAO=300 ./gerar-trafego.sh    # 5 req/s por 5 minutos
#   ./gerar-trafego.sh https://meu-app.azurecontainerapps.io
#
# Variáveis:
#   PUBLIC_URL  endereço do app, sem barra no fim (ou 1º argumento; senão lê do .env)
#   RPS         requisições por segundo (padrão 2; aceita decimal, ex.: 0.5)
#   DURACAO     segundos de duração (padrão 0 = até Ctrl+C)
#
# Cada requisição acorda a API se ela estiver escalada a zero (a primeira pode demorar).
set -uo pipefail
cd "$(dirname "$0")"

URL="${1:-${PUBLIC_URL:-}}"
if [[ -z "$URL" && -f .env ]]; then
  URL="$(grep -E '^PUBLIC_URL=' .env | tail -n1 | cut -d= -f2- | tr -d '\r"'"'"'')"
fi
URL="${URL%/}"
if [[ -z "$URL" ]]; then
  echo "Informe o endereço do app: PUBLIC_URL no .env, variável de ambiente ou 1º argumento." >&2
  exit 1
fi

RPS="${RPS:-2}"
DURACAO="${DURACAO:-0}"
if ! awk -v r="$RPS" 'BEGIN { exit !(r ~ /^[0-9]+([.][0-9]+)?$/ && r > 0) }'; then
  echo "RPS inválido: '$RPS' (use um número maior que zero)." >&2
  exit 1
fi
if ! [[ "$DURACAO" =~ ^[0-9]+$ ]]; then
  echo "DURACAO inválida: '$DURACAO' (use segundos inteiros; 0 = sem fim)." >&2
  exit 1
fi

# /relatos/proximos exige lat e lon; raio_m é opcional (1 a 5000 m, padrão 1000). Pontos na
# região central de São Paulo, com raios diferentes.
CAMINHOS=(
  "/"
  "/api/painel"
  "/api/relatos/proximos?lat=-23.5505&lon=-46.6333&raio_m=1000"
  "/"
  "/api/painel"
  "/api/relatos/proximos?lat=-23.5614&lon=-46.6559&raio_m=2500"
)

ARQ_STATUS="$(mktemp)"
cleanup() {
  jobs -p | xargs -r kill 2>/dev/null || true
  wait 2>/dev/null || true
  resumo
  rm -f "$ARQ_STATUS"
}
resumo() {
  echo
  echo "Resumo por código HTTP (de ${total:-0} requisições):"
  if [[ -s "$ARQ_STATUS" ]]; then
    sort "$ARQ_STATUS" | uniq -c | sort -rn | awk '{ printf "  %s  x%s\n", $2, $1 }'
  else
    echo "  (nenhuma resposta registrada)"
  fi
}
trap 'cleanup; exit 0' INT TERM

INTERVALO="$(awk -v r="$RPS" 'BEGIN { printf "%.4f", 1 / r }')"
if (( DURACAO > 0 )); then limite="por ${DURACAO}s"; else limite="até Ctrl+C"; fi
echo "Gerando ${RPS} req/s em ${URL} (${limite})."

chamar() {
  # Timeout generoso: a primeira chamada após escala a zero espera a API subir.
  local codigo
  codigo="$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 "${URL}$1" || true)"
  echo "${codigo:-000}" >> "$ARQ_STATUS"
}

total=0
inicio=$SECONDS
ultimo_resumo=$SECONDS
while :; do
  if (( DURACAO > 0 && SECONDS - inicio >= DURACAO )); then
    break
  fi
  chamar "${CAMINHOS[total % ${#CAMINHOS[@]}]}" &
  total=$((total + 1))
  sleep "$INTERVALO"
  if (( SECONDS - ultimo_resumo >= 10 )); then
    ultimo_resumo=$SECONDS
    recentes="$(tail -n 200 "$ARQ_STATUS" | sort | uniq -c | sort -rn | awk '{ printf "%sx%s ", $2, $1 }')"
    echo "[$(date +%H:%M:%S)] ${total} enviadas | últimos códigos: ${recentes:-aguardando respostas}"
  fi
done
wait
trap - INT TERM
resumo
rm -f "$ARQ_STATUS"
