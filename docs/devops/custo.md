# Custo

Estimativa de custo da infraestrutura do Passo Seguro na Azure, com a configuração que o Terraform em [`infra/`](../../infra/README.md) cria. Veja a arquitetura em [`arquitetura.md`](./arquitetura.md).

> **Valores em dólar: a preencher.** As colunas de preço abaixo esperam os números da calculadora de preços da Azure (Central US, USD por mês). Elas estão marcadas **a preencher** de propósito, para nenhum número inventado entrar no documento. A coluna de configuração e as contas de uso e de período já estão prontas.
>
> Export da calculadora: **a preencher** (link).

## Premissas

| Item | Valor |
|---|---|
| Região | Central US (`centralus`) |
| Moeda e unidade | USD por mês |
| Entrega do projeto | 19/11/2026 |
| Infraestrutura no ar até | 26/11/2026, para a correção |
| Período contado | **09/11 a 26/11 = 18 dias**, ou 0,6 de um mês de 30 dias |
| Orçamento da assinatura | US$ 10 por mês (`budget_amount`), com aviso por e-mail em 50%, 80% e 100% |
| Réplicas mínimas | 0 (escala a zero). O padrão do Terraform e o valor do `terraform.tfvars` da equipe |

O orçamento **só avisa**. Ele não desliga nada.

## Itens da estimativa

| Item | Configuração (do Terraform) | Mensal (calculadora) | Franquia que se aplica |
|---|---|---|---|
| Container Apps, API | Consumption, 0,5 vCPU e 1 GiB, de 0 a 2 réplicas | **a preencher** | Franquia mensal do Container Apps (abaixo) |
| Container Apps, app (nginx) | Consumption, 0,25 vCPU e 0,5 GiB, de 0 a 2 réplicas | **a preencher** | A mesma franquia, dividida com a API |
| PostgreSQL Flexible Server | `B_Standard_B1ms`, 32 GB, backup de 7 dias, sem alta disponibilidade | **a preencher** | Oferta de 12 meses do Azure for Students (abaixo) |
| Azure Files e Blob | Conta Standard LRS; share `fotos` com cota de 5 GB; containers `painel` e `ouro-export` | **a preencher** | Nenhuma conhecida |
| Key Vault | SKU `standard`; 7 segredos | **a preencher** | Nenhuma conhecida |
| Log Analytics | `PerGB2018`, retenção de 30 dias, teto de 0,15 GB por dia (cerca de 4,5 GB por mês) | **a preencher** | 5 GB por mês de ingestão |
| Rede | VNet, 2 NSGs, zona de DNS privado do PostgreSQL | **a preencher** | Nenhuma conhecida |
| Azure Monitor | 1 alerta de métrica (5xx), 1 grupo de ação por e-mail | **a preencher** | Conferir na calculadora |
| Conta do state do Terraform | Standard LRS, em `rg-passoseguro-tfstate`, criada à mão | **a preencher** | Nenhuma conhecida |
| Banda de saída (egress) | Respostas do app e chamadas da API ao Railway | **a preencher** | Conferir na calculadora |
| GitHub Actions e GHCR | Repositório público | US$ 0 (fora da Azure) | Gratuito em repositório público |
| Prometheus e Grafana | No notebook da equipe | US$ 0 | Cada raspagem acorda a API |
| Railway (assistente, LLM) | Fora da Azure | **a preencher** (fora da calculadora da Azure) | Depende do plano do Railway |
| **Total mensal** | | **a preencher** | |

## O que a franquia cobre

| Franquia | O que cobre | O que cobre neste projeto |
|---|---|---|
| **Container Apps (Consumption)**: por assinatura, a cada mês, os primeiros 180.000 vCPU-segundos, 360.000 GiB-segundos e 2 milhões de requisições | Os recursos que ficam dentro desses limites não são cobrados. Só contam requisições vindas de fora do ambiente; as sondas de saúde não contam | Com escala a zero, cada app só consome quando recebe tráfego. Com a observabilidade local desligada, o uso deve ficar dentro da franquia (confirme no Cost Management). A conta do pior caso está na seção seguinte |
| **PostgreSQL Flexible Server B1ms** (oferta de 12 meses do Azure for Students): 750 horas de B1ms, 32 GB de armazenamento e 32 GB de backup | 750 horas passam de um mês inteiro (720 horas em 30 dias) | O nosso servidor é exatamente `B1ms` com 32 GB, então a oferta o cobre **por inteiro**, desde que ela esteja ativa na assinatura. Confirme no portal (Cost Management) |
| **Crédito do Azure for Students**: US$ 100 por 12 meses | O que passar das franquias sai do crédito | O orçamento de US$ 10 por mês avisa antes de o saldo ir embora |
| **Log Analytics**: 5 GB por mês de ingestão | Ingestão até 5 GB | O teto diário de 0,15 GB limita a ingestão a cerca de 4,5 GB por mês, dentro da franquia |

As franquias mudam com o tempo. Antes de citar números em outro lugar, confira nas fontes: [cobrança do Container Apps](https://learn.microsoft.com/azure/container-apps/billing), [Azure for Students](https://azure.microsoft.com/free/students) e [serviços gratuitos da Azure](https://azure.microsoft.com/pricing/free-services).

### Se os apps ficarem sempre ligados (`min_replicas = 1`)

Para a demonstração, o `infra/README.md` recomenda `min_replicas = 1`. Isso **estoura a franquia do Container Apps**. Conta para os 18 dias (1.555.200 segundos), com 1 réplica de cada app ativa o tempo todo:

| Recurso | Uso nos 18 dias | Franquia mensal | Relação |
|---|---|---|---|
| vCPU-segundos | (0,5 + 0,25) × 1.555.200 = **1.166.400** | 180.000 | cerca de 6,5 vezes |
| GiB-segundos | (1 + 0,5) × 1.555.200 = **2.332.800** | 360.000 | cerca de 6,5 vezes |

É o teto: o Container Apps cobra menos pelo tempo em que a réplica fica ociosa, então o gasto real é menor que o das contas acima. Mesmo assim, o excedente entra na calculadora. Ligue `min_replicas = 1` só no dia da demonstração e volte a 0 depois.

## Custo esperado

| Período | Fórmula | Valor |
|---|---|---|
| **Mês cheio** | soma dos itens da tabela | **a preencher** |
| **09/11 a 26/11 (18 dias)** | mês cheio × 18/30 | **a preencher** |

Duas observações para ler o resultado:

- O PostgreSQL é cobrado por hora ligado, então a proporção de 18/30 vale para ele (432 horas). Com a oferta do Azure for Students ativa, o item fica em US$ 0.
- A conta de proporção supõe uso constante. O Container Apps com escala a zero depende do tráfego, e o Prometheus acorda a API a cada raspagem de 30 s enquanto estiver ligado. Para economizar, desligue a observabilidade local depois de gerar a evidência (`docker compose down`).

Depois de 26/11, `terraform destroy` em `infra/` desliga tudo e para o gasto. O state e o resource group `rg-passoseguro-tfstate` ficam, porque foram criados à mão, e custam centavos.

## Cenário de escala: 10 vezes mais usuários

O que muda, em poucas linhas. Sem valores: eles dependem da calculadora.

| O que muda | Hoje | Com 10 vezes mais usuários |
|---|---|---|
| **Réplicas mínimas** | 0 (partida a frio) e máximo de 2 | `min_replicas = 1` ou 2 nos dois apps, para acabar com a partida a frio e ter alta disponibilidade; `max_replicas` maior. Sai da franquia do Container Apps |
| **PostgreSQL** | `B1ms` Burstable, 32 GB, sem alta disponibilidade | Camada General Purpose (mais vCPU e memória), mais armazenamento, alta disponibilidade entre zonas e backup geo-redundante. A API conecta como `passo_admin` e as migrações rodam na partida; passar a um papel só de leitura e escrita e a um Job só para migrar |
| **Fotos** | Azure Files montado na API, que serve `/fotos/*` | Blob Storage com **CDN** (Azure Front Door ou Azure CDN) na frente, e URL assinada. Tira o tráfego de imagem da API e do app |
| **Assistente (LLM)** | Serviço no Railway | O maior custo do crescimento. Perguntas 10 vezes maiores pedem **inferência com GPU** dedicada. Antes disso: limite de perguntas por aparelho, cache das respostas frequentes e modelo menor ou quantizado |
| **Logs** | Teto de 0,15 GB por dia | O teto estoura e corta os logs. Subir o teto custa por GB; reduzir o que se grava ou amostrar |
| **Observabilidade** | Prometheus e Grafana no notebook | Prometheus e Grafana gerenciados, para a raspagem não depender de uma máquina ligada |
