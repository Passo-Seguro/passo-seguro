# Passo Seguro

[![CI](https://github.com/Passo-Seguro/passo-seguro/actions/workflows/ci.yml/badge.svg)](https://github.com/Passo-Seguro/passo-seguro/actions/workflows/ci.yml)

> Plataforma de zeladoria colaborativa para calçadas de São Paulo: o pedestre fotografa um problema, a IA identifica o que é, o assistente explica quem resolve e uma automação encaminha o caso para a subprefeitura certa.

**MVP no ar:** A definir
**Entrega:** 19/11/2026 às 23h55

---

## Integrantes

| Nome completo | RM |
|---|---|
| Guilherme Morais | 551981 |
| Júlia Marques | 98680 |
| Matheus Gusmão | 550826 |

---

## Ficha Técnica

| Campo | Descrição |
|---|---|
| Nome do produto | Passo Seguro |
| Cidadão e território | Pedestres da cidade de São Paulo; piloto em uma subprefeitura central (ex.: Sé ou Pinheiros) |
| Problema, em uma frase | Calçadas danificadas ou obstruídas causam quedas e empurram o pedestre para a rua, e reclamar hoje é confuso e lento. |
| Proposta de valor | Reportar um problema na calçada em 30 segundos, saber quem resolve e acompanhar até o reparo. |
| Arquitetura: componentes | App web (PWA), API, serviço de visão, assistente com LLM local, automação de triagem, pipeline Airflow + Databricks, robô inspetor, nuvem via Terraform |
| Fontes de dados | SP156 (dados abertos da Prefeitura), Infosiga (Detran-SP, CC BY 4.0), Open-Meteo, relatos do próprio app |
| Modelos de IA | YOLO ajustado com fotos de calçadas; LLM pequeno aberto com RAG e LoRA; classificador TinyML de vibração no robô |
| URL do MVP e repositório | A definir |
| Indicadores de impacto | Tempo médio até o reparo; % de relatos encaminhados em menos de 24 h; problemas resolvidos por mês; relatos feitos por idosos e PcD |
| ODS conectados | 11 (metas 11.2 e 11.7), 3 (meta 3.6), 10 (meta 10.2), 9 (meta 9.1) |

---

## O problema

As solicitações sobre calçadas no SP156 cresceram mais de 200% entre 2020 e 2025, chegando a 49.215, segundo levantamento apresentado na Câmara Municipal de São Paulo em agosto de 2026. Os canais de denúncia de calçada no 156 são confusos, e a Prefeitura já mapeia buracos no asfalto de forma automatizada, enquanto a calçada fica para trás.

Hoje o SP156 não identifica automaticamente o problema, não agrupa relatos repetidos e não orienta o cidadão sobre quem é o responsável.

## Como funciona

```
foto → detecção (visão) → orientação com fonte (LLM local) → triagem e encaminhamento (automação) → mapa e painel de prioridades (dados)
```

- **Cidadão:** grátis. Reporta, recebe orientação e acompanha o caso até o reparo.
- **Subprefeituras:** painel de prioridades, relatos agrupados e georreferenciados e pacote diário pronto para o 156.
- **Robô inspetor:** percorre uma maquete de calçada, detecta desníveis por vibração e envia as ocorrências para a mesma API.

---

## Arquitetura

A API é o único ponto de integração: todas as partes conversam por ela.

```mermaid
flowchart LR
    Pedestre["Pedestre (PWA)"] -->|"POST /relatos<br/>POST /assistente<br/>GET /painel"| API
    Robo["Robô inspetor"] -->|"POST /relatos"| API
    API -->|"POST /deteccoes"| Visao["Serviço de visão (YOLO/ONNX)"]
    API --> LLM["Assistente (LLM local + RAG)"]
    Triagem["Automação de triagem (RPA)"] -->|"GET /relatos?status=novo"| API
    Triagem --> Pacote["Pacote diário por subprefeitura (SP156)"]
    Airflow["Airflow + Databricks"] -->|"GET /relatos?status=novo"| API
    Airflow --> Ouro[("Camada Ouro")]
    Ouro -->|"vw_prioridades exportada"| API
```

### Contratos de API

O contrato completo está em [`openapi.yaml`](./openapi.yaml).

| Contrato | Quem chama | O que faz |
|---|---|---|
| `POST /relatos` | App e robô | Foto, localização e descrição; devolve id e classe detectada |
| `POST /deteccoes` | API e triagem | Imagem → lista de `{classe, confiança, caixa}` |
| `POST /assistente` | App | Pergunta → JSON com resposta, fontes e recusa |
| `GET /painel` | App | Prioridades por subprefeitura, lidas da Ouro exportada |
| `GET /relatos?status=novo` | Triagem e Airflow | Relatos para triagem e para a coleta diária |
| `GET /relatos/proximos` | App | Relatos num raio, para o mapa público (localização arredondada a ~100 m) *(rc2)* |
| `GET /meus-relatos` | App | Relatos do próprio cidadão, pelo id anônimo do aparelho *(rc2)* |
| `PATCH /relatos/{id}` | App e triagem | App corrige a categoria; triagem atualiza status, subprefeitura, prioridade e confirmações *(rc2)* |

Os contratos marcados com *(rc2)* são a emenda **1.0.0-rc2**, em revisão: só valem depois da aprovação do grupo.

### Classes de problema

`buraco` · `piso_danificado` · `obstaculo` · `veiculo_na_calcada`

O mesmo nome vale no modelo de visão, no banco, na triagem, no robô e nos gráficos.

### Status de um relato

`novo` → `revisao_humana` → `validado` → `encaminhado` → `resolvido` (ou `rejeitado`)

---

## Repositórios

| Repositório | Disciplina | O que contém |
|---|---|---|
| [passo-seguro](https://github.com/Passo-Seguro/passo-seguro) | Secure DevOps & Cloud | App (PWA), API, infraestrutura e Ficha Técnica |
| [passo-seguro-genai](https://github.com/Passo-Seguro/passo-seguro-genai) | Generative AI for Engineering | Assistente do pedestre: RAG, LoRA e avaliação |
| [passo-seguro-dados](https://github.com/Passo-Seguro/passo-seguro-dados) | Big Data Architecture & Data Integration | Pipeline Airflow, Databricks e painel de prioridades |
| [passo-seguro-visao](https://github.com/Passo-Seguro/passo-seguro-visao) | Applied Computer Vision | Detector de problemas na calçada |
| [passo-seguro-rpa](https://github.com/Passo-Seguro/passo-seguro-rpa) | Robotic Process Automation | Robô de triagem e encaminhamento |
| [passo-seguro-robo](https://github.com/Passo-Seguro/passo-seguro-robo) | Project-Based Maker Lab | Robô 2WD inspetor de calçada |

## Estrutura deste repositório

```
passo-seguro/
├── app/          # PWA (front-end)
├── api/          # API (FastAPI)
├── infra/        # Terraform da nuvem (ver infra/README.md), docker compose, pipeline de CI/CD
├── openapi.yaml  # contratos de API
└── README.md
```

## Fontes de dados

| Fonte | O que traz | Formato |
|---|---|---|
| [SP156](http://dados.prefeitura.sp.gov.br/dataset/dados-do-sp156) | Solicitações de calçada: data, status, subprefeitura | CSV |
| [Infosiga](https://infosiga.detran.sp.gov.br/) | Sinistros e vítimas pedestres na capital, com latitude e longitude | CSV em ZIP |
| Open-Meteo | Chuva horária em SP | JSON |
| Relatos do Passo Seguro | Ocorrências do app e do robô | JSON da API |

## Privacidade e segurança

- Nenhuma chave, senha ou dado pessoal real é versionado; `.env`, `*.tfvars`, `*.tfstate` e `secrets.h` ficam no `.gitignore`.
- Fotos publicadas têm rostos e placas desfocados.
- O identificador do cidadão usa hash SHA-256 com sal, e coordenadas públicas são arredondadas para cerca de 100 m.

## Contratos e mock

O contrato da API está em [`openapi.yaml`](./openapi.yaml) (OpenAPI 3.1) e as classes de problema, em [`contratos/classes.yaml`](./contratos/classes.yaml), a fonte única de verdade.

**Validar** (precisa de Node.js e Python 3):

```bash
scripts/validar-contratos.sh
```

Faz o lint do `openapi.yaml` e confere se o enum `categoria` é igual, na mesma ordem, às classes de `classes.yaml`.

**Rodar o mock** em `http://localhost:4010` (precisa de Node.js):

```bash
scripts/mock.sh
curl http://localhost:4010/painel
curl -H "Authorization: Bearer token-ficticio" "http://localhost:4010/relatos?status=novo"
```

Para escolher um exemplo, use `-H "Prefer: example=obstaculo"`; para um código de resposta, `-H "Prefer: code=422"`.

**Bateria de curls** contra o mock (com o mock rodando em outro terminal):

```bash
scripts/testar-mock.sh
```

## Como rodar

Dois ambientes com Docker, para fins diferentes:

| Arquivo | Para quê | O que sobe |
|---|---|---|
| [`docker-compose.yml`](./docker-compose.yml) | **Produção rodando localmente**: o que vai para a nuvem, com o endurecimento de contêiner ligado | app (nginx + PWA), API e banco; só o app publica porta |
| [`docker-compose.dev.yml`](./docker-compose.dev.yml) | **Desenvolvimento** da API | API e banco, com porta aberta para depurar |

### Stack completa (app + API + banco), como em produção

Precisa de Docker. Sobe tudo, aplica as migrações e serve o app em `http://localhost:8080`:

```bash
docker compose up --build
docker compose ps                                  # os três devem ficar "healthy"
curl http://localhost:8080/api/painel               # a API, atrás do nginx do app
```

O navegador fala só com o app. O nginx repassa `/api/*` para a API (`/api/painel` chega na API como `/painel`), nunca expõe `/api/metrics` (404) e serve a raspagem de métricas em `/metrics/api`, só com token:

```bash
curl -H "Authorization: Bearer token-metricas-local" http://localhost:8080/metrics/api
```

Os valores do compose (senha do banco, `METRICS_TOKEN`, `SERVICE_TOKEN`, `SALT_AUTOR`…) são **fictícios** e só valem para este teste local; para mudar, exporte a variável ou crie um `.env` ao lado do compose (ex.: `METRICS_TOKEN=outro-token docker compose up`). Para parar e apagar os dados: `docker compose down -v`.

| Serviço | Porta | Rede | Endurecimento |
|---|---|---|---|
| `app` | 8080 publicada | `borda` | usuário 101, `read_only` (com `tmpfs` em `/tmp` e `/etc/nginx/conf.d`), 128 MB |
| `api` | nenhuma | `borda` e `interna` | usuário 10001, `read_only` (com `tmpfs` em `/tmp`; só o volume `fotos` é gravável), 512 MB |
| `db` | nenhuma | `interna` | usuário 999, `read_only` (com `tmpfs` em `/tmp` e `/run/postgresql`), 512 MB |

Em todos: `no-new-privileges`, `cap_drop: [ALL]`, `restart: unless-stopped`, healthcheck, `depends_on` com `service_healthy` (`db` → `api` → `app`) e log `json-file` com rodízio (10 MB × 3 arquivos). A rede `interna` é `internal: true` (sem saída para a internet): o banco só é alcançado pela API.

A API **confere** o `METRICS_TOKEN` em `/metrics` e só é alcançável pela rede interna, atrás do nginx. Nunca publique a porta 8000 da API em produção. Detalhes do nginx (variáveis, rotas, logs sem query string): [`app/README.md`](./app/README.md#docker).

### API (FastAPI + Postgres/PostGIS)

Precisa de Docker. Sobe a API e o banco, aplica as migrações e serve em `http://localhost:8000` (documentação interativa em `/docs`):

```bash
docker compose -f docker-compose.dev.yml up --build
curl http://localhost:8000/painel
curl -H "Authorization: Bearer token-servico-dev" "http://localhost:8000/relatos?status=novo"
```

Os tokens do compose são **fictícios** e só valem para desenvolvimento. Variáveis de ambiente: veja [`api/.env.example`](./api/.env.example).

**Desenvolvimento local da API** (Python 3.12):

```bash
cd api
python -m venv .venv && source .venv/bin/activate      # no Windows: .venv/Scripts/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest                                                  # testes (precisa do banco: veja abaixo)
ruff check . && ruff format --check .                   # estilo
```

Os testes usam um Postgres+PostGIS de teste (`TEST_DATABASE_URL`, padrão `passo_seguro_test` no banco do compose). Suba só o banco com `docker compose -f docker-compose.dev.yml up -d db`; sem banco, os testes que dependem dele são pulados (no CI, com `EXIGIR_BANCO=1`, viram falha). O teste de **contrato** (`tests/test_contrato.py`) sobe a API de verdade e usa o Schemathesis para conferir cada resposta contra o [`openapi.yaml`](./openapi.yaml); `OPENAPI_PATH=<arquivo>` aponta outro contrato (por exemplo, a emenda rc2).

**Observabilidade:** `GET /metrics` (formato Prometheus, exige `Authorization: Bearer <METRICS_TOKEN>`) traz a latência por rota, o total de requisições por rota e status, as requisições em andamento e as métricas do processo (CPU, memória, descritores de arquivo e coleta de lixo; estas só aparecem em Linux, ou seja, no contêiner). Os logs saem em JSON, uma linha por requisição, **sem** foto, descrição, parâmetros de consulta (coordenadas) nem cabeçalhos.

**Integração com os outros serviços** (todos por variável de ambiente; veja `api/.env.example`):

| Serviço | Variáveis | Se não estiver no ar |
|---|---|---|
| Visão (`POST /deteccoes` do colega) | `VISAO_URL`, `VISAO_TOKEN`, `VISAO_TIMEOUT_S`, `USE_FAKE_VISAO` | O relato é criado do mesmo jeito, com `categoria` e `confianca` nulas. |
| Assistente (`POST /assistente` do colega) | `ASSISTENTE_URL`, `ASSISTENTE_TOKEN`, `ASSISTENTE_TIMEOUT_S`, `USE_FAKE_ASSISTENTE`, `SP156_URL` | `POST /assistente` responde `recusou: true` com mensagem padrão e o link do [SP156](https://sp156.prefeitura.sp.gov.br/). |
| Pipeline de dados (view `vw_prioridades`) | `PAINEL_EXPORT_PATH` | `GET /painel` responde 404 (`painel_indisponivel`). |

`USE_FAKE_VISAO` e `USE_FAKE_ASSISTENTE` trocam o serviço por um falso e ficam **desligados por padrão** (código, `.env.example` e `docker-compose.dev.yml`). A "classe" da visão falsa sai do hash da imagem, **não** da foto: se um avaliador testar com ela, vai parecer erro do modelo. **Não use em demonstração nem em produção.** Para desenvolver sem os serviços reais, ligue de propósito: `docker compose -f docker-compose.dev.yml -f docker-compose.fakes.yml up`. Com qualquer fake ligado a API avisa no log (`modo_fake_ativo`, nível WARNING), em `GET /health` (`modo_fake` e `alertas`; continua 200) e na métrica `passo_seguro_modo_fake{servico=...}` (1 = fake), para o DevOps montar um alerta. O painel é um **arquivo JSON**: uma lista de objetos no formato `PrioridadeSubprefeitura` do contrato (exemplo fictício em [`docs/exemplos/vw_prioridades.json`](./docs/exemplos/vw_prioridades.json); formato a confirmar com quem faz Big Data). Arquivo existente mas fora do schema: 503 `painel_invalido`.

**Emenda rc2 do contrato:** `GET /relatos/proximos`, `GET /meus-relatos`, `PATCH /relatos/{id}`, `autor_id` e `X-Device-Token` ficam isolados em `api/app/routers/rc2.py` e só existem com `HABILITAR_RC2=true` (ligado no `docker-compose.dev.yml`, desligado por padrão até o grupo aprovar o PR `feat/contratos-rc2`).

As dependências têm versões fixas em `api/requirements.txt` e `api/requirements-dev.txt`, geradas com `pip-compile` a partir dos arquivos `.in` (para atualizar: `pip-compile --strip-extras requirements.in`).

**Relatos simulados** para o mapa não começar vazio: [`docs/dados-simulados.md`](./docs/dados-simulados.md).

**Relatos criados sob visão fake:** a coluna interna `relatos.modo_deteccao` (`real`, `fake` ou `nenhuma`) separa o que veio do modelo do que veio do detector de mentira; consulta e limpeza em [`docs/modo-deteccao.md`](./docs/modo-deteccao.md).

## Pipeline

O workflow [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) roda a cada push em qualquer branch, em PR para `main` e sob demanda (`workflow_dispatch`). Um push novo na mesma branch cancela a execução anterior; na `main` nunca cancela, para não interromper um deploy.

```
segredos ─┐
sast      │
iac       ├─► build [api, app] ─► deploy   (só push na main)
testes-api│
testes-app┘
```

| Job | O que faz | Reprova quando |
|---|---|---|
| `segredos` | Gitleaks (CLI em container) no **histórico inteiro**, com [`.gitleaks.toml`](./.gitleaks.toml) | acha segredo que não está na lista de tokens fictícios |
| `sast` | Semgrep (`p/default`, `p/python`, `p/typescript`, `p/dockerfile`, `p/terraform`), sem conta no Semgrep Cloud | qualquer achado |
| `iac` | `trivy config` em `infra/`, `api/` e `app/`; `terraform fmt -check`; `terraform validate` | achado HIGH/CRITICAL ou Terraform fora do padrão/inválido |
| `testes-api` | `ruff check`, `ruff format --check` e `pytest` com Postgres+PostGIS | lint, formatação ou teste falha (banco fora do ar também é falha) |
| `testes-app` | `npm ci`, lint, `check:api` (tipos do contrato em dia), testes e build | qualquer etapa falha |
| `build` | Constrói `api` e `app`, varre a imagem com o Trivy e, **só se passar**, publica no GHCR; gera o SBOM (SPDX) como artifact | vulnerabilidade HIGH/CRITICAL **com correção disponível** |
| `deploy` | Atualiza a API e depois o app no Azure Container Apps, espera a revisão nova ficar saudável e faz o teste de fumaça | a revisão mais recente não usa a imagem do commit, não fica saudável em 5 min, ou `/` e `/api/saude` não respondem |

Os resultados do Gitleaks, do Semgrep e do Trivy vão para a aba **Security → Code scanning**.

**Imagens.** `ghcr.io/passo-seguro/passo-seguro-api` e `...-app`, com as tags `:<sha do commit>` e, na `main`, `:latest`. O que sobe é exatamente a imagem que o Trivy aprovou. As labels OCI `source` e `revision` apontam para este repositório e o commit. O SBOM de cada imagem fica nos artifacts da execução (`sbom-api`, `sbom-app`).

**Deploy.** Só em push na `main`, no environment `production`. O login na Azure é por OIDC (identidade gerenciada, sem senha). Secrets do environment: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`. Variables: `AZURE_RG`, `ACA_API`, `ACA_APP`, `PUBLIC_URL`. A espera pela revisão está em [`.github/scripts/implantar.sh`](./.github/scripts/implantar.sh). PR de fork e Dependabot rodam as varreduras e os testes, mas não enviam relatório nem imagem (o token deles é somente leitura).

### Reproduzir as varreduras localmente

Só precisa de Docker. Rode na raiz do repositório (no Windows, use Git Bash ou WSL; no Git Bash prefixe com `MSYS_NO_PATHCONV=1`). Usam as mesmas versões do CI (variáveis `env` no topo do `ci.yml`).

```bash
# Segredos no histórico (precisa do clone completo: git fetch --unshallow, se for raso)
docker run --rm -v "$PWD:/repo" -w /repo zricethezav/gitleaks:v8.30.1 \
  git --config .gitleaks.toml --redact .

# SAST
docker run --rm -v "$PWD:/src" -w /src semgrep/semgrep:1.184.0 \
  semgrep scan --config p/default --config p/python --config p/typescript \
  --config p/dockerfile --config p/terraform --metrics=off --error

# Terraform e Dockerfiles (rode uma vez para cada alvo: infra, api e app)
docker run --rm -v "$PWD:/repo" -w /repo aquasec/trivy:0.76.2 config \
  --severity HIGH,CRITICAL --exit-code 1 --skip-dirs '**/node_modules' infra

# Formatação e validação do Terraform
docker run --rm -v "$PWD/infra:/infra" -w /infra hashicorp/terraform:1.17.1 fmt -check -recursive -diff
docker run --rm -v "$PWD/infra:/infra" -w /infra --entrypoint sh hashicorp/terraform:1.17.1 \
  -c "terraform init -backend=false -input=false && terraform validate"

# Imagem: construir e varrer como o job "build" (troque api por app para o outro serviço)
docker build -t passo-seguro-api:local api/
# app: docker build --build-arg VITE_API_URL=/api -t passo-seguro-app:local app/
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.2 image \
  --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 passo-seguro-api:local
```

Os testes e o estilo estão em [Desenvolvimento local da API](#api-fastapi--postgrespostgis) e em [`app/README.md`](./app/README.md).

## Licença

A definir.