# PWA do Passo Seguro: build com Node e servidor com nginx SEM privilégios, que também faz
# o proxy de /api para a API (a imagem serve qualquer domínio: o app chama o caminho /api).
#
#   docker build -t passo-seguro-app app/
#   docker run --rm -p 8080:8080 \
#     -e API_UPSTREAM=http://host.docker.internal:8000 -e METRICS_TOKEN=token-ficticio \
#     passo-seguro-app
#
# Variáveis de EXECUÇÃO (o nginx as aplica ao modelo nginx.conf.template na partida):
#   API_UPSTREAM   obrigatória. Endereço interno da API, sem barra no fim.
#   METRICS_TOKEN  segredo da raspagem em /metrics/api. Vazio = sempre 401.
# VITE_API_URL é só um caminho público (não é segredo) e entra no JavaScript no build.
# Não há nenhum segredo nesta imagem.

# ---------- Etapa 1: build ----------
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Caminho relativo: o navegador chama /api no mesmo domínio em que abriu o app.
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------- Etapa 2: servidor ----------
FROM nginxinc/nginx-unprivileged:1.28-alpine AS servidor

# Só estas duas variáveis passam pelo envsubst; as $variáveis do nginx ficam intactas.
ENV NGINX_ENVSUBST_FILTER='^(API_UPSTREAM|METRICS_TOKEN)$'

# O modelo vira /etc/nginx/conf.d/default.conf na partida (a imagem deixa conf.d com dono
# nginx, então o usuário 101 consegue gravar). O default.conf da imagem sai do caminho.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY seguranca.inc /etc/nginx/seguranca.inc
COPY --chmod=755 docker/19-valida-variaveis.sh /docker-entrypoint.d/19-valida-variaveis.sh
COPY --from=build /app/dist /usr/share/nginx/html

# O usuário "nginx" (uid 101) já vem na imagem; a porta é 8080 (portas < 1024 exigem root).
USER 101
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
