#!/bin/sh
# Roda DEPOIS do envsubst (20-...) da imagem oficial do nginx. Aquele script só avisa quando
# não consegue gravar (ex.: diretório sem permissão) e o nginx subiria sem nenhum "server".
# Aqui a partida falha em vez disso.
set -eu

ME=$(basename "$0")
CONF=/etc/nginx/conf.d/default.conf

if [ ! -s "$CONF" ]; then
  echo "$ME: ERRO: $CONF não foi gerado a partir do modelo (o diretório é gravável pelo usuário do nginx?)" >&2
  exit 1
fi

if ! nginx -t >/dev/null 2>&1; then
  echo "$ME: ERRO: a configuração gerada é inválida:" >&2
  nginx -t >&2 || true
  exit 1
fi
