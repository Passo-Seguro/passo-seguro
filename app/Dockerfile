# PWA do Passo Seguro: build com Node e servidor estático com nginx SEM privilégios.
#
#   docker build -t passo-seguro-app --build-arg VITE_API_URL=https://api.exemplo.invalid app/
#   docker run --rm -p 8080:8080 passo-seguro-app
#
# VITE_API_URL é só um endereço público (não é segredo) e entra no JavaScript no build.
# Não há nenhum segredo nesta imagem.

# ---------- Etapa 1: build ----------
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_URL=http://localhost:4010
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------- Etapa 2: servidor estático ----------
FROM nginxinc/nginx-unprivileged:1.28-alpine AS servidor

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY seguranca.inc /etc/nginx/seguranca.inc
COPY --from=build /app/dist /usr/share/nginx/html

# O usuário "nginx" (uid 101) já vem na imagem; a porta é 8080 (portas < 1024 exigem root).
USER 101
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
