# Observabilidade (Prometheus + Grafana locais)

Prometheus e Grafana rodam **no notebook**, em contêineres, e raspam a API em produção pelo app
(`https://<app>/metrics/api`). Tudo é provisionado por arquivo: datasource, painel e alertas.

> **Custo:** a API escala a zero e **cada raspagem a acorda**. Deixe a stack ligada só enquanto
> gera evidência e desligue em seguida (`docker compose down`).

```
observabilidade/
├── docker-compose.yml        prometheus (retenção 15d) + grafana, portas só em 127.0.0.1
├── .env.example              copie para .env (o git ignora)
├── preparar.sh               gera prometheus/alvos/api.json a partir de PUBLIC_URL
├── gerar-trafego.sh          carga para o painel e para o teste dos alertas
├── metrics-token             token da raspagem (o git ignora; você cria)
├── prometheus/
│   ├── prometheus.yml        job "api": https, /metrics/api, token, 30 s
│   └── regras.yml            regras de gravação dos quatro sinais
└── grafana/
    ├── dashboards/           "Passo Seguro · Sinais de ouro" (JSON)
    └── provisioning/         datasources, dashboards e alerting (regras, contato, política, modelo)
```

## 1. Subir

Requisitos: Docker, Git Bash (ou outro bash) e, para o roteiro, a Azure CLI logada.

```bash
cd observabilidade
cp .env.example .env     # preencha PUBLIC_URL, a senha do Grafana e o webhook do Discord
```

`PUBLIC_URL` é a saída `app_url` do Terraform (`terraform -chdir=../infra output -raw app_url`).
O webhook vem de *Configurações do canal > Integrações > Webhooks* no Discord; ele só existe no
`.env`, nunca no git.

O token da raspagem é o segredo `metrics-token` do Key Vault (o mesmo que o nginx do app confere).
Grave **só o valor**, sem `Bearer` e sem quebra de linha:

```bash
KV=$(terraform -chdir=../infra output -raw key_vault_name)
az keyvault secret show --vault-name "$KV" --name metrics-token --query value -o tsv | tr -d '\r\n' > metrics-token
```

```bash
./preparar.sh            # grava prometheus/alvos/api.json e confere o metrics-token
docker compose up -d
```

- Grafana: <http://127.0.0.1:3000> (usuário e senha do `.env`), painel em *Passo Seguro > Passo Seguro · Sinais de ouro*.
- Prometheus: <http://127.0.0.1:9090> (confira *Status > Targets*: o job `api` deve estar **UP**).

As regras usam janela de 2 minutos: os gráficos só enchem uns 2 a 3 minutos depois de haver tráfego.
Se `up` ficar 0 logo de início, veja `lastError` em *Targets*: 401 é token errado; erro de DNS ou 502/504
logo após a API escalar a zero costuma passar na raspagem seguinte (a partida a frio pode estourar o
tempo do nginx).

## 2. O que é medido

Os rótulos da API são em português (`metodo`, `rota`, `status`). A raspagem de `/metrics` e a sonda
`/saude` também passam pelo middleware da API; **todas as regras as excluem**.

| Sinal | Série de origem | Regra de gravação (`regras.yml`) | Limiar no painel e no alerta |
|---|---|---|---|
| Latência | `passo_seguro_http_request_duration_seconds_bucket` | `passo_seguro:http_latencia_p50_segundos:rate2m`, `…_p95_…` (e `…_por_rota`) | p95 > 3 s por 5 min |
| Tráfego | `passo_seguro_http_requests_total` | `passo_seguro:http_requisicoes_por_segundo:rate2m` (e `…_por_rota`) | sem alerta |
| Erros | `passo_seguro_http_requests_total{status=~"5.."}` | `passo_seguro:http_taxa_5xx:rate2m` (e `…_por_rota`) | 5xx/total > 5% por 2 min |
| Saturação | `process_cpu_seconds_total`, `process_resident_memory_bytes` | `passo_seguro:processo_cpu_vcpu:rate2m`, `passo_seguro:processo_memoria_residente_bytes` | linhas de referência: 0,5 vCPU e 1 GiB (limites do Container App da API) |
| Disponibilidade | `up{job="api"}` | — | `up == 0` por 1 min |

Sem tráfego, as razões e os quantis ficam **sem dados** (não viram 0/0 nem NaN) e os alertas tratam
isso como OK. A memória e a CPU são do processo Python, não do contêiner inteiro.

**Limite conhecido:** o Terraform deixa a API com até 2 réplicas e a raspagem cai numa delas ao
acaso. Com tráfego baixo costuma haver uma só; com duas, os contadores podem "saltar" entre
raspagens e as taxas oscilam.

## 3. Alertas (Grafana, avaliados a cada 1 min)

| Alerta | Condição | Dispara quando |
|---|---|---|
| **API fora do ar** | `up{job="api"} == 0` por 1 min | a raspagem de `/metrics/api` falha (qualquer resposta que não seja 2xx) |
| **Taxa de 5xx alta** | 5xx ÷ total > 5% por 2 min | a **API** responde 5xx (ex.: 500 por falha no banco) |
| **Latência p95 alta** | p95 > 3 s por 5 min | a API fica lenta |

Aviso para o Discord (URL em `DISCORD_WEBHOOK_URL`), com o valor atual e o link do painel, e
mensagem de **resolvido** quando volta ao normal. Para usar e-mail, descomente o ponto de contato em
`grafana/provisioning/alerting/contatos.yml`, as variáveis `GF_SMTP_*` e `ALERTA_EMAIL` no compose, e
troque o `receiver` em `politicas.yml`.

> **O alerta "Taxa de 5xx alta" do Grafana não dispara na queda da API.** Os 502/504 gerados pelo
> nginx nunca chegam à API e, portanto, não entram nas métricas dela. Na queda, o Grafana mostra
> "API fora do ar"; o 5xx da queda é visto pelo **alerta do Azure Monitor** (`alerta-5xx-ca-passoseguro-app`,
> mais de 5 respostas 5xx em 5 minutos na métrica `Requests` do app, com aviso por e-mail).

## 4. Roteiro do disparo (evidência)

Variáveis usadas abaixo:

```bash
RG=rg-passoseguro-prod
API=ca-passoseguro-api
APP=ca-passoseguro-app
APP_URL=$(terraform -chdir=../infra output -raw app_url)
```

**1. Subir o local** (seção 1) e abrir o painel e *Alerting > Alert rules* (as três regras em *Normal*).

**2. Gerar tráfego** e deixar rodando em outro terminal:

```bash
RPS=3 ./gerar-trafego.sh          # Ctrl+C para parar; mostra o resumo por código HTTP
```

Espere uns 3 minutos até o painel encher. **Print 1:** painel com os quatro sinais saudáveis.
`/api/painel` responde 404 até o primeiro export da camada Ouro; isso é 4xx e não
atrapalha o teste.

**3. Derrubar a API.** Use o método 1; só use o 2 se o 1 não produzir 5xx.

*Método 1 (principal): desligar o ingress da API.*

```bash
az containerapp ingress disable -n $API -g $RG
```

**Antes de esperar os alertas**, anote o código que o app devolve em `/api`:

```bash
curl -i "$APP_URL/api/painel"
```

- Se for **5xx** (502/503/504): siga o roteiro. Os dois alertas devem disparar.
- Se for **404** ou qualquer outro código que não seja 5xx: o Azure Monitor **não** vai disparar (ele
  só conta 5xx). "API fora do ar" no Grafana dispara do mesmo jeito, porque qualquer resposta que não
  seja 2xx derruba o `up`. Para o e-mail do Azure, restaure o ingress (passo 6, método 1) e use o método 2.

*Método 2 (alternativo): apontar o nginx do app para um destino que não responde.*

```bash
az containerapp update -n $APP -g $RG --set-env-vars API_UPSTREAM=http://ca-passoseguro-api:81
```

A API continua de pé, mas o nginx passa a falhar ao falar com ela (porta 81 não existe): `/api` e
`/metrics/api` devolvem 502 ou 504 (504 se estourar o tempo de conexão). Os dois alertas disparam.
Este método cria uma **nova revisão** do app (o nginx reinicia para aplicar a variável).

**4. Esperar os alertas**, com o gerador de tráfego ainda rodando (ele mostra os códigos 5xx):

| O quê | Quando | Onde |
|---|---|---|
| **API fora do ar** | uns 2 a 3 min (avaliação de 1 min + `for` de 1 min + agrupamento) | Grafana (*Alerting > Alert rules* em *Firing*) e mensagem no Discord |
| Alerta de 5xx do Azure Monitor | alguns minutos (janela de 5 min, avaliado a cada 1 min) | e-mail do `alert_email` |

**5. Prints.** Painel com `API no ar` em vermelho e a linha do tempo mostrando a queda; as regras em
*Firing*; a mensagem do Discord; o e-mail do Azure; o resultado do `curl -i` do passo 3.

**6. Religar** e mostrar os alertas **resolvidos** (Grafana volta a *Normal*, o Discord mostra "RESOLVIDO"
e o Azure manda o aviso de resolvido):

*Método 1:*

```bash
az containerapp ingress enable -n $API -g $RG --type internal --target-port 8000 --transport auto --allow-insecure
```

> `--allow-insecure` é **obrigatório** aqui: o Terraform da API usa `allow_insecure_connections = true`
> (o nginx chama a API por `http://ca-passoseguro-api` e não segue redirecionamento). Sem a opção, o
> ingress volta com HTTP→HTTPS ligado, o nginx recebe 301, e a API continua "fora do ar".

*Método 2:* volte ao valor original.

```bash
az containerapp update -n $APP -g $RG --set-env-vars API_UPSTREAM=http://ca-passoseguro-api
```

Isso cria **mais uma revisão** do app. Depois de restaurar (qualquer um dos métodos), rode
`terraform plan` em `infra/`: **não deve haver diferença** em `API_UPSTREAM` (nem no ingress da
API). Se aparecer, rode `terraform apply` para reconciliar.

**7. Encerrar** (para a API poder escalar a zero de novo): Ctrl+C no gerador e

```bash
docker compose down        # acrescente -v para apagar os dados do Prometheus e do Grafana
```

## 5. Qual método cobre qual alerta

| Alerta | Método 1 (`ingress disable`) | Método 2 (`API_UPSTREAM` errado) |
|---|---|---|
| **API fora do ar** (Grafana) | sim, sempre | sim, sempre |
| **5xx do Azure Monitor** (e-mail) | só se o `curl -i` do passo 3 mostrar 5xx | sim (o nginx devolve 502/504) |
| Taxa de 5xx alta (Grafana) | não | não |
| Latência p95 alta (Grafana) | não | não |

Os dois alertas do Grafana que dependem de a API estar viva (5xx e latência) não são acionados por
nenhuma queda: as respostas de erro vêm do nginx.

## Segurança

- Portas só em `127.0.0.1`. O `.env` e o `metrics-token` ficam fora do git (`.gitignore`).
- A URL do webhook do Discord é um segredo: quem a tem posta no canal. Se vazar, apague o webhook no Discord.
- Nunca cole o token nem o webhook em prints.
