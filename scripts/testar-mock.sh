#!/usr/bin/env bash
# Bateria de curls contra o mock (Prism) do openapi.yaml: confere o status HTTP e,
# quando faz sentido, um trecho do corpo. Falha (código diferente de 0) se algo divergir.
#
# Uso:
#   scripts/mock.sh &            # em outro terminal, sobe o mock em http://localhost:4010
#   scripts/testar-mock.sh       # roda a bateria
#
# Variável opcional: MOCK_URL (padrão http://localhost:4010).
# Os tokens e ids abaixo são FICTÍCIOS; o mock só confere se o cabeçalho existe.
#
# Observação: o mock não sabe regras de negócio (ex.: "robô sem X-Device-Token dá 401").
# Para ver essas respostas de erro, a bateria força o código com `Prefer: code=<codigo>`.
# O mock valida o pedido ANTES de olhar o `Prefer`: um pedido inválido volta como 422
# (o erro de validação do Prism), então os casos forçados usam pedidos válidos.
set -uo pipefail

MOCK_URL="${MOCK_URL:-http://localhost:4010}"
TOKEN_FICTICIO="token-ficticio"
AUTOR_FICTICIO="3f2b8c1e-7d4a-4e90-9b15-6a0c2d8e4f71"
RELATO_ID="0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01"

falhas=0
total=0
FOTO_TMP="$(mktemp)"
trap 'rm -f "$FOTO_TMP"' EXIT
# Cabeçalho mínimo de um JPEG (o mock não decodifica a imagem).
printf '\xff\xd8\xff\xe0fake-jpeg' > "$FOTO_TMP"
# No Windows (Git Bash) o curl precisa do caminho no formato C:/...
FOTO_CURL="$FOTO_TMP"
if command -v cygpath >/dev/null 2>&1; then FOTO_CURL="$(cygpath -m "$FOTO_TMP")"; fi

# checar <descricao> <status-esperado> <trecho-esperado-no-corpo|-> <argumentos do curl...>
checar() {
  local descricao="$1" esperado="$2" trecho="$3"
  shift 3
  total=$((total + 1))
  local saida status corpo
  saida="$(curl -s -o - -w '\n%{http_code}' "$@")"
  status="${saida##*$'\n'}"
  corpo="${saida%$'\n'*}"
  if [ "$status" != "$esperado" ]; then
    echo "FALHA  $descricao: esperado $esperado, veio $status"
    echo "       corpo: $corpo"
    falhas=$((falhas + 1))
  elif [ "$trecho" != "-" ] && ! grep -qF -- "$trecho" <<<"$corpo"; then
    echo "FALHA  $descricao: status $status ok, mas o corpo não contém: $trecho"
    echo "       corpo: $corpo"
    falhas=$((falhas + 1))
  else
    echo "ok     $descricao ($status)"
  fi
}

if ! curl -s -o /dev/null "$MOCK_URL/painel"; then
  echo "ERRO: o mock não responde em $MOCK_URL. Suba com scripts/mock.sh." >&2
  exit 2
fi

echo "==> Endpoints originais"
checar "GET /painel" 200 '"subprefeitura"' "$MOCK_URL/painel"
checar "GET /relatos (com bearer)" 200 '"paginacao"' \
  -H "Authorization: Bearer $TOKEN_FICTICIO" "$MOCK_URL/relatos?status=novo"
checar "GET /relatos (sem bearer)" 401 '"nao_autenticado"' "$MOCK_URL/relatos"
checar "POST /assistente" 200 '"recusou"' \
  -H 'Content-Type: application/json' -d '{"pergunta":"Quem conserta a calçada?"}' "$MOCK_URL/assistente"

echo "==> Emenda rc2: POST /relatos (autor_id e X-Device-Token)"
checar "POST /relatos app com autor_id" 201 '"status":"novo"' \
  -F "foto=@$FOTO_CURL;type=image/jpeg" -F lat=-23.5505 -F lon=-46.6333 -F fonte=app \
  -F "autor_id=$AUTOR_FICTICIO" "$MOCK_URL/relatos"
checar "POST /relatos robô com X-Device-Token" 201 '"status":"novo"' \
  -H "X-Device-Token: $TOKEN_FICTICIO" \
  -F "foto=@$FOTO_CURL;type=image/jpeg" -F lat=-23.5672 -F lon=-46.6916 -F fonte=robo "$MOCK_URL/relatos"
checar "POST /relatos robô sem token (401 forçado)" 401 '"nao_autenticado"' \
  -H 'Prefer: code=401' \
  -F "foto=@$FOTO_CURL;type=image/jpeg" -F lat=-23.5672 -F lon=-46.6916 -F fonte=robo "$MOCK_URL/relatos"

echo "==> Emenda rc2: GET /relatos/proximos"
checar "GET /relatos/proximos" 200 '"confirmacoes"' \
  "$MOCK_URL/relatos/proximos?lat=-23.5505&lon=-46.6333"
checar "GET /relatos/proximos com raio_m" 200 '"categoria"' \
  "$MOCK_URL/relatos/proximos?lat=-23.5505&lon=-46.6333&raio_m=5000"
checar "GET /relatos/proximos lista vazia" 200 '[]' \
  -H 'Prefer: example=vazio' "$MOCK_URL/relatos/proximos?lat=-23.5505&lon=-46.6333"
checar "GET /relatos/proximos 400 forçado" 400 '"requisicao_invalida"' \
  -H 'Prefer: code=400' "$MOCK_URL/relatos/proximos?lat=-23.5505&lon=-46.6333"
checar "GET /relatos/proximos fora de SP (422 forçado)" 422 '"dados_invalidos"' \
  -H 'Prefer: code=422' "$MOCK_URL/relatos/proximos?lat=10&lon=10"

echo "==> Emenda rc2: GET /meus-relatos"
checar "GET /meus-relatos" 200 '"foto_url"' -H "X-Autor-Id: $AUTOR_FICTICIO" "$MOCK_URL/meus-relatos"
checar "GET /meus-relatos lista vazia" 200 '[]' \
  -H "X-Autor-Id: $AUTOR_FICTICIO" -H 'Prefer: example=vazio' "$MOCK_URL/meus-relatos"
checar "GET /meus-relatos sem X-Autor-Id" 400 '"requisicao_invalida"' "$MOCK_URL/meus-relatos"

echo "==> Emenda rc2: PATCH /relatos/{id}"
checar "PATCH modo app (X-Autor-Id)" 200 '"piso_danificado"' -X PATCH \
  -H "X-Autor-Id: $AUTOR_FICTICIO" -H 'Content-Type: application/json' \
  -H 'Prefer: example=app_corrigido' -d '{"categoria":"piso_danificado"}' "$MOCK_URL/relatos/$RELATO_ID"
checar "PATCH modo triagem (bearer)" 200 '"encaminhado"' -X PATCH \
  -H "Authorization: Bearer $TOKEN_FICTICIO" -H 'Content-Type: application/json' \
  -H 'Prefer: example=triagem_encaminhado' \
  -d '{"status":"encaminhado","subprefeitura":"Sé","prioridade":"alta","confirmacoes":3}' \
  "$MOCK_URL/relatos/$RELATO_ID"
checar "PATCH sem credencial" 401 '"nao_autenticado"' -X PATCH \
  -H 'Content-Type: application/json' -d '{"categoria":"buraco"}' "$MOCK_URL/relatos/$RELATO_ID"
checar "PATCH 400 forçado" 400 '"requisicao_invalida"' -X PATCH \
  -H "X-Autor-Id: $AUTOR_FICTICIO" -H 'Content-Type: application/json' -H 'Prefer: code=400' \
  -d '{"categoria":"buraco"}' "$MOCK_URL/relatos/$RELATO_ID"
checar "PATCH 403 forçado (outro autor)" 403 '"proibido"' -X PATCH \
  -H "X-Autor-Id: $AUTOR_FICTICIO" -H 'Content-Type: application/json' -H 'Prefer: code=403' \
  -d '{"categoria":"buraco"}' "$MOCK_URL/relatos/$RELATO_ID"
checar "PATCH 404 forçado" 404 '"nao_encontrado"' -X PATCH \
  -H "X-Autor-Id: $AUTOR_FICTICIO" -H 'Content-Type: application/json' -H 'Prefer: code=404' \
  -d '{"categoria":"buraco"}' "$MOCK_URL/relatos/$RELATO_ID"
checar "PATCH 422 forçado" 422 '"dados_invalidos"' -X PATCH \
  -H "Authorization: Bearer $TOKEN_FICTICIO" -H 'Content-Type: application/json' -H 'Prefer: code=422' \
  -d '{"confirmacoes":-1}' "$MOCK_URL/relatos/$RELATO_ID"

echo
echo "$((total - falhas))/$total verificações passaram."
[ "$falhas" -eq 0 ]
