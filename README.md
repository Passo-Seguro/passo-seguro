# Passo Seguro

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
├── infra/        # Terraform, docker compose, pipeline de CI/CD
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

## Como rodar

Integração de ponta a ponta em construção (meta: 15/11). Por enquanto, a **API** já sobe em desenvolvimento.

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

**Observabilidade:** `GET /metrics` (formato Prometheus, exige `Authorization: Bearer <METRICS_TOKEN>`) traz a latência por rota, o total de requisições por rota e status e as requisições em andamento. Os logs saem em JSON, uma linha por requisição, **sem** foto, descrição, parâmetros de consulta (coordenadas) nem cabeçalhos.

**Integração com os outros serviços** (todos por variável de ambiente; veja `api/.env.example`):

| Serviço | Variáveis | Se não estiver no ar |
|---|---|---|
| Visão (`POST /deteccoes` do colega) | `VISAO_URL`, `VISAO_TOKEN`, `VISAO_TIMEOUT_S`, `USE_FAKE_VISAO` | O relato é criado do mesmo jeito, com `categoria` e `confianca` nulas. |
| Assistente (`POST /assistente` do colega) | `ASSISTENTE_URL`, `ASSISTENTE_TOKEN`, `ASSISTENTE_TIMEOUT_S`, `USE_FAKE_ASSISTENTE`, `SP156_URL` | `POST /assistente` responde `recusou: true` com mensagem padrão e o link do [SP156](https://sp156.prefeitura.sp.gov.br/). |
| Pipeline de dados (view `vw_prioridades`) | `PAINEL_EXPORT_PATH` | `GET /painel` responde 404 (`painel_indisponivel`). |

`USE_FAKE_VISAO` e `USE_FAKE_ASSISTENTE` trocam o serviço por um falso (a "classe" da visão falsa sai do hash da imagem, **não** da foto), para o app funcionar e ser demonstrado sem eles. O painel é um **arquivo JSON**: uma lista de objetos no formato `PrioridadeSubprefeitura` do contrato (exemplo fictício em [`docs/exemplos/vw_prioridades.json`](./docs/exemplos/vw_prioridades.json); formato a confirmar com quem faz Big Data). Arquivo existente mas fora do schema: 503 `painel_invalido`.

**Emenda rc2 do contrato:** `GET /relatos/proximos`, `GET /meus-relatos`, `PATCH /relatos/{id}`, `autor_id` e `X-Device-Token` ficam isolados em `api/app/routers/rc2.py` e só existem com `HABILITAR_RC2=true` (ligado no `docker-compose.dev.yml`, desligado por padrão até o grupo aprovar o PR `feat/contratos-rc2`).

As dependências têm versões fixas em `api/requirements.txt` e `api/requirements-dev.txt`, geradas com `pip-compile` a partir dos arquivos `.in` (para atualizar: `pip-compile --strip-extras requirements.in`).

**Relatos simulados** para o mapa não começar vazio: [`docs/dados-simulados.md`](./docs/dados-simulados.md).

## Licença

A definir.