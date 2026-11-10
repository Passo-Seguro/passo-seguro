# Infraestrutura (Terraform)

Descreve toda a nuvem do MVP na Azure. Produção 100% gerenciada: **Container Apps + PostgreSQL Flexible Server**, tudo em `centralus`. Nenhum segredo real é versionado; os valores de exemplo são **fictícios**.

```
internet ──► ca-passoseguro-app (nginx, ingress externo, 8080)
                    │  http://ca-passoseguro-api (nome interno)
                    ▼
             ca-passoseguro-api (FastAPI, ingress interno, 8000) ──► Azure Files "fotos" (/data/fotos)
                    │                                           └──► Blob "painel" (painel.json, leitura com identidade gerenciada)
                    │ 5432, só pela rede privada
                    ▼
             PostgreSQL Flexible Server 16 + PostGIS (snet-db, sem endereço público)

Key Vault ── segredos (lidos pelos apps com a identidade id-passoseguro-apps)
Storage   ── share "fotos" + containers de blob "painel" e "ouro-export" (Big Data); share "painel" é legado
Log Analytics, alerta de 5xx e orçamento mensal por e-mail
```

| Arquivo | O que descreve |
|---|---|
| `base.tf` | resource group `rg-passoseguro-prod`, sufixo dos nomes globais, tags |
| `rede.tf` | VNet `10.20.0.0/16`, `snet-aca`, `snet-db` e os NSGs |
| `banco.tf` | PostgreSQL Flexible Server, DNS privado, PostGIS, banco `passo_seguro` |
| `storage.tf` | conta de armazenamento, share `fotos`, containers `painel` e `ouro-export` (e o share `painel`, legado) |
| `segredos.tf` | Key Vault e os segredos (gerados pelo Terraform) |
| `identidade.tf` | `id-passoseguro-apps` (lê segredos e o container `painel`) e `id-passoseguro-github` (pipeline, OIDC) |
| `apps.tf` | ambiente de Container Apps, `ca-passoseguro-api` e `ca-passoseguro-app` |
| `monitoramento.tf` | Log Analytics, grupo de ação por e-mail e alerta de 5xx |
| `orcamento.tf` | orçamento mensal com avisos em 50%, 80% e 100% |

## Pré-requisitos

- [Terraform](https://developer.hashicorp.com/terraform/install) 1.9 ou mais novo e [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli).
- Acesso à assinatura **Azure for Students** com papel **Owner** (o Terraform cria atribuições de papel).
- Docker, para publicar as imagens iniciais.
- Os provedores de recursos registrados na assinatura (uma vez só):

  ```bash
  for p in Microsoft.App Microsoft.OperationalInsights Microsoft.DBforPostgreSQL \
           Microsoft.KeyVault Microsoft.Storage Microsoft.Consumption Microsoft.Insights \
           Microsoft.ManagedIdentity Microsoft.Network; do az provider register --namespace $p; done
  ```

Restrições da assinatura, já verificadas: só `chilecentral`, `eastus`, `southcentralus`, `centralus` e `canadacentral` são permitidas, e o PostgreSQL Flexible Server está restrito em `eastus` e `southcentralus`. Usamos **`centralus` para tudo** (VNet, Container Apps e Postgres precisam estar na mesma região). Não há VM barata disponível, por isso nada roda em VM. Provavelmente também não dá para criar App Registration no Entra ID, e por isso o pipeline usa identidade gerenciada com credencial federada.

## 1. Bootstrap do state

> **Já executado por nós.** Fica aqui só para reproduzir em outra assinatura. Os nomes abaixo são os mesmos de `backend.hcl.example` (fictícios; os reais estão no seu `backend.hcl`).

O state fica numa conta de armazenamento criada à mão, fora do Terraform (ele não pode guardar o próprio state antes de existir):

```bash
az login
az account set --subscription "<ID_DA_ASSINATURA>"

az group create --name rg-passoseguro-tfstate --location centralus

az storage account create \
  --name stpassosegurotfstate --resource-group rg-passoseguro-tfstate \
  --location centralus --sku Standard_LRS --min-tls-version TLS1_2 \
  --allow-blob-public-access false --allow-shared-key-access false

az storage container create \
  --name tfstate --account-name stpassosegurotfstate --auth-mode login

# Quem roda o Terraform precisa ler e gravar o state (o backend usa o Entra ID, sem chave).
az role assignment create \
  --assignee "$(az ad signed-in-user show --query id -o tsv)" \
  --role "Storage Blob Data Contributor" \
  --scope "$(az storage account show -n stpassosegurotfstate -g rg-passoseguro-tfstate --query id -o tsv)"
```

Depois copie `backend.hcl.example` para `backend.hcl` (o git ignora) e ajuste os nomes.

## 2. Publicar as imagens iniciais

Os Container Apps precisam de uma imagem para existir. Antes do primeiro `apply`, publique uma imagem `:bootstrap` de cada serviço no GHCR (o pipeline troca a tag a cada deploy):

```bash
export MSYS_NO_PATHCONV=1   # Git Bash (Windows): sem isto "/api" vira "C:/Program Files/Git/api" no build
echo "$GHCR_TOKEN" | docker login ghcr.io -u <SEU_USUARIO_GITHUB> --password-stdin   # PAT com write:packages

docker build -t ghcr.io/passo-seguro/passo-seguro-api:bootstrap api/
docker build -t ghcr.io/passo-seguro/passo-seguro-app:bootstrap --build-arg VITE_API_URL=/api app/
docker push ghcr.io/passo-seguro/passo-seguro-api:bootstrap
docker push ghcr.io/passo-seguro/passo-seguro-app:bootstrap
```

Depois do primeiro push, em **Packages → Package settings**, deixe os dois pacotes **públicos**: o Terraform não configura credenciais de registro, então o Container Apps puxa as imagens sem login. Se preferir manter privados, será preciso um bloco `registry` com um token em segredo.

## 3. Rodar o Terraform

```bash
cd infra
export ARM_SUBSCRIPTION_ID=$(az account show --query id -o tsv)   # o azurerm 4.x exige a assinatura
cp terraform.tfvars.example terraform.tfvars                       # ajuste; o git ignora *.tfvars
export TF_VAR_assistente_token='<token do serviço do assistente no Railway>'   # ou ponha no tfvars

terraform init -backend-config=backend.hcl
terraform plan -out=passoseguro.tfplan
terraform apply passoseguro.tfplan
```

> **O `terraform apply` é sempre manual.** O pipeline ([`ci.yml`](../.github/workflows/ci.yml)) só publica as imagens no GHCR e roda `az containerapp update` para trocar a imagem de cada app; ele não executa Terraform. Mudanças em `infra/` só chegam à Azure quando alguém roda `plan`/`apply` na própria máquina, com os valores reais (incluindo `painel_publicadores_object_ids`) no `terraform.tfvars` local.

O `apply` leva uns 15 a 20 minutos (Postgres e ambiente de Container Apps). Há duas esperas de 60 s de propósito, para o papel do Azure RBAC propagar antes de gravar segredos e subir os apps.

Para **desligar tudo** (e parar de gastar crédito):

```bash
terraform destroy
```

O Key Vault tem *purge protection* desligada de propósito, então o `destroy` apaga o cofre de verdade e o nome pode ser reutilizado. O state e o resource group `rg-passoseguro-tfstate` ficam, porque foram criados à mão.

### Verificação local (sem Azure)

Nada disto toca a nuvem:

```bash
terraform fmt -recursive -check
terraform init -backend=false && terraform validate
tflint --init && tflint
trivy config --severity HIGH,CRITICAL infra/
```

### Riscos aceitos

O pipeline ([`ci.yml`](../.github/workflows/ci.yml)) reprova achados do Trivy (HIGH/CRITICAL) e do Semgrep. O que está abaixo foi **aceito de propósito** e fica marcado no código com o motivo: `#trivy:ignore:<ID>` logo acima do recurso (o Trivy exige o comentário colado nele) e `# nosemgrep: <ID exato da regra>` no fim da linha do `resource`. Nenhum `nosemgrep` é genérico.

| Ferramenta | Regra | Recurso | Motivo | Evolução para produção |
|---|---|---|---|---|
| Trivy | `AVD-AZU-0012` | `azurerm_storage_account.main` (`storage.tf`) | Firewall aberto: o Databricks lê o container `ouro-export` de fora da VNet. | Private endpoint ou regras de IP. |
| Trivy | `AVD-AZU-0013` | `azurerm_key_vault.main` (`segredos.tf`) | Acesso público aberto no MVP; o acesso exige Entra ID + RBAC. | Private endpoint e acesso público desligado. |
| Trivy | `AVD-AZU-0016` | `azurerm_key_vault.main` (`segredos.tf`) | Purge protection desligada para o `destroy` funcionar na assinatura de estudante. | Purge protection ligada. |
| Trivy | `AVD-AZU-0047` | `azurerm_network_security_group` `nsg-snet-aca` (`rede.tf`, 2 regras) | O app é público de propósito: só 80/tcp (redireciona para HTTPS) e 443/tcp, nada de administração. | Sem mudança (é o desenho do app). |
| Semgrep | `terraform.azure.security.keyvault.keyvault-purge-enabled.keyvault-purge-enabled` | `azurerm_key_vault.main` (`segredos.tf`) | Mesmo motivo do `AVD-AZU-0016`: purge protection desligada para o `destroy` funcionar na assinatura de estudante. | Purge protection ligada. |
| Semgrep | `terraform.azure.security.keyvault.keyvault-specify-network-acl.keyvault-specify-network-acl` | `azurerm_key_vault.main` (`segredos.tf`) | Mesmo motivo do `AVD-AZU-0013`: acesso público aberto no MVP. | `network_acls` com `default_action = "Deny"` + service endpoint na `snet-aca`. |
| Semgrep | `terraform.azure.security.storage.storage-queue-services-logging.storage-queue-services-logging` | `azurerm_storage_account.main` (`storage.tf`) | O Queue Storage não é usado nesta conta (só Azure Files e Blob): não há fila para registrar. | Sem mudança, a menos que passe a usar filas. |

**Segredos com validade** (`terraform.azure.security.keyvault.keyvault-ensure-secret-expires`, Trivy `AVD-AZU-0017`): em vez de aceitar o risco, os 7 segredos do Key Vault têm `expiration_date` **fixa** em `2027-06-30T00:00:00Z` (`local.validade_segredos` em `segredos.tf`; nunca `timeadd`/`timestamp`, que mudariam a cada plan). A data cobre a entrega da GS e a correção. **Depois dela o segredo vence, o Container App deixa de lê-lo e a API cai**: antes de 30/06/2027, renove a data ou rotacione os segredos e rode o `apply`.

## 4. O que copiar para o GitHub

Depois do `apply`:

```bash
terraform output
```

No repositório, em **Settings → Environments → `production`** (o nome precisa ser exatamente esse, é o `subject` da credencial federada), crie estas **variáveis** (não são segredos):

| Variável no GitHub | Output do Terraform |
|---|---|
| `AZURE_CLIENT_ID` | `github_client_id` |
| `AZURE_TENANT_ID` | `tenant_id` |
| `AZURE_SUBSCRIPTION_ID` | `subscription_id` |
| `AZURE_RESOURCE_GROUP` | `resource_group` |
| `API_APP_NAME` | `api_app_name` |
| `WEB_APP_NAME` | `web_app_name` |

Os outros outputs (`app_url`, `environment_name`, `key_vault_name`, `storage_account_name`, `postgres_fqdn`) servem para consulta. Nenhum output é segredo; os segredos ficam só no Key Vault.

Restrinja o environment `production` à branch `main` e exija aprovação para o deploy: a credencial federada confia em qualquer job que rode nesse environment.

Login e troca de imagem no workflow (sem senha, via OIDC):

```bash
az login --service-principal -u "$AZURE_CLIENT_ID" -t "$AZURE_TENANT_ID" --federated-token "$TOKEN_OIDC"   # na prática: azure/login@v2
az containerapp update -n "$API_APP_NAME" -g "$AZURE_RESOURCE_GROUP" --image ghcr.io/passo-seguro/passo-seguro-api:<sha>
```

O Terraform ignora mudanças na imagem dos contêineres (`ignore_changes`), então um `plan` depois de um deploy não desfaz a imagem nova.

## 5. Subir o arquivo do painel

`GET /painel` lê o `painel.json` exportado pelo pipeline de dados, que fica no container de blob **privado** `painel` (sem acesso anônimo) da conta de armazenamento. A API o lê **sem SAS e sem chave**: a identidade gerenciada `id-passoseguro-apps` tem o papel *Storage Blob Data Reader* com escopo **só nesse container**, e a API recebe `PAINEL_BLOB_URL` (saída `painel_blob_url`) e `AZURE_CLIENT_ID` (o `client_id` dessa identidade, que o `DefaultAzureCredential` precisa para escolher a identidade user-assigned; não é segredo). O resultado validado fica em memória por 10 minutos, então um arquivo novo aparece em até 10 minutos, sem reiniciar nada.

Enquanto o arquivo não existir, `GET /painel` responde 404 (`painel_indisponivel`), o que é o comportamento esperado do primeiro deploy. Arquivo fora do schema do contrato (até 5 MB) ou falha na leitura: 503 (`painel_invalido`), com o motivo no log. O formato é uma lista de `PrioridadeSubprefeitura`; use [`docs/exemplos/vw_prioridades.json`](../docs/exemplos/vw_prioridades.json) como modelo.

Quem **grava** é o pipeline de dados, com uma identidade dele. O Terraform concede escrita (*Storage Blob Data Contributor*, **só no container `painel`**) a cada object ID da variável `painel_publicadores_object_ids` (lista, vazia por padrão). Os IDs reais **não entram no git**: ponha no `infra/terraform.tfvars` (o git ignora `*.tfvars`) ou em `TF_VAR_painel_publicadores_object_ids`, e o `terraform apply` é **manual**, rodado por quem tem esse `terraform.tfvars` local: o pipeline do GitHub não aplica a infra e não conhece esses IDs.

Como obter o object ID:

```bash
# Você (para o teste manual abaixo)
az ad signed-in-user show --query id -o tsv

# O pipeline de dados: o object ID do PRINCIPAL, não o client ID do app
az ad sp show --id <client id do service principal> --query id -o tsv
az identity show -g <resource group> -n <nome da identidade> --query principalId -o tsv   # identidade gerenciada
```

```hcl
# terraform.tfvars (não versionado)
painel_publicadores_object_ids = ["<object id da pessoa>", "<object id do pipeline de dados>"]
```

Quem não está na lista (nem o dono da assinatura, que não tem papel de dados por padrão) não consegue gravar. Depois do `terraform apply`, o papel leva alguns minutos para propagar.

### Ordem de implantação deste PR

1. **Merge na `main` primeiro.** O pipeline roda em push na `main`, publica a imagem nova da API (com a leitura do blob) e a coloca no Container App com `az containerapp update`.
2. **Logo em seguida, `terraform apply` manual**, na máquina de quem tem o `terraform.tfvars` com os object ids. Ele cria o container `painel`, os papéis e entrega `PAINEL_BLOB_URL` e `AZURE_CLIENT_ID` à API.
3. **No intervalo entre os dois, `GET /painel` responde 404** (`painel_indisponivel`): a imagem nova ainda não tem a URL do blob, ou o blob ainda não existe. É o comportamento esperado, e o resto da API não é afetado. Faça o `apply` logo depois do deploy para encurtar esse intervalo.
4. Só depois publique o primeiro `painel.json` (abaixo).

### Como publicar o `painel.json`

Quem está em `painel_publicadores_object_ids` envia sem usar a chave da conta:

```bash
az storage blob upload --auth-mode login --account-name <storage> -c painel -n painel.json -f painel.json --overwrite
curl <app_url>/api/painel
```

`<storage>` é a saída `storage_account_name` e `<app_url>` é a saída `app_url` (`terraform output -raw storage_account_name`, `terraform output -raw app_url`). Para um teste, o modelo é [`docs/exemplos/vw_prioridades.json`](../docs/exemplos/vw_prioridades.json).

Se a conferência não mostrar o arquivo novo, lembre de dois atrasos:

- **Cache de 10 minutos** na API: um `painel.json` novo (ou uma correção) aparece em até 10 minutos, sem reiniciar nada. Uma falha de leitura fica em cache por 30 s.
- **Propagação do papel**: logo após o `apply`, o upload (papel de escrita) e a leitura da API (papel de leitura) podem falhar com 403 por alguns minutos. Espere e tente de novo.

O nome do blob precisa ser exatamente `painel.json`. O pipeline de dados deve **sobrescrever** o blob (a troca é atômica; a API nunca lê um arquivo pela metade).

> **Legado:** o share `painel` (Azure Files, montado em `/data/painel`) era o caminho antigo, quando a API lia `PAINEL_EXPORT_PATH`. A API não lê mais esse arquivo e a variável deixou de ser entregue; o share e o volume continuam declarados só para o `apply` não apagar nada. Podem ser removidos num PR próprio, depois que o `painel.json` do blob estiver no ar.

## Decisões e cuidados

- **Segredos** são gerados pelo Terraform e moram no Key Vault. Os apps leem por referência com `id-passoseguro-apps` (user-assigned, para o papel existir antes dos apps). Quem roda o Terraform recebe *Key Vault Secrets Officer*. O state remoto contém os valores; proteja o acesso à conta do state.
- **Login do pipeline (OIDC)**: o repositório usa o subject *imutável* do GitHub, então a credencial federada `github-environment-production` aceita `repo:Passo-Seguro@<id da org>/passo-seguro@<id do repo>:environment:production`, e não o formato com nomes. Se o login da Azure falhar com `AADSTS700213`, compare o `subject` de `identidade.tf` com o que o job mostra em "Federated token details" (ou com `gh api repos/Passo-Seguro/passo-seguro/actions/oidc/customization/sub`). O ID do repositório muda se ele for apagado e recriado; um rename não o altera.
- **Rede**: o Postgres não tem endereço público; só `snet-aca` alcança a porta 5432. O NSG de `snet-aca` só aceita 80 e 443 da internet. Não existe regra para 22, 3389 nem porta de administração. A API tem ingress interno.
- **Ingress da API aceita HTTP** (`allow_insecure_connections = true`) porque o nginx a chama por `http://ca-passoseguro-api` dentro do ambiente; com a opção desligada o ingress responderia um redirecionamento para HTTPS e o nginx não o seguiria. O app público força HTTPS.
- **Painel em blob, lido pela API com identidade gerenciada**: nada de montar volume. O papel *Storage Blob Data Reader* é concedido só no container `painel` (não na conta, nem no `ouro-export`). A identidade `id-passoseguro-apps` é compartilhada pelos dois Container Apps, então o app (nginx) também a recebe, mas não usa o papel; separar uma identidade só da API é uma melhoria futura.
- **`METRICS_TOKEN` na API e no app**: os dois usam o mesmo segredo `metrics-token`. O nginx do app confere em `/metrics/api` e repassa o cabeçalho; a API confere de novo (sem o token configurado ela responde 401 sempre).
- **`HABILITAR_RC2=true`**: a emenda rc2 do contrato (`/relatos/proximos`, `/meus-relatos`, `PATCH /relatos/{id}`) é o que o app usa. Com a flag, `SALT_AUTOR` é obrigatório (já é entregue).
- **Storage com chave habilitada**: o Container Apps só monta Azure Files com a chave da conta. O firewall do storage fica aberto porque o Databricks lê o `ouro-export` de fora da VNet. Em produção real: private endpoint.
- **Escala a zero** (`min_replicas = 0`): economiza crédito, mas a primeira requisição depois de um tempo parado tem partida a frio, e a API ainda roda `alembic upgrade head` ao subir. Para a demonstração, use `min_replicas = 1`.
- **A API conecta como `passo_admin`** (dono do banco), porque as migrações criam extensão e tabelas. Melhoria futura: um papel só de leitura e escrita para a API e outro para as migrações.
- **Migrações concorrentes**: com `max_replicas = 2`, duas réplicas novas podem rodar `alembic upgrade head` ao mesmo tempo. É improvável com `min_replicas` 0 ou 1; o remédio futuro é um Container Apps Job só para migrar.
- **Alerta de 5xx**: usa a métrica `Requests` do Container App com a dimensão `statusCodeCategory = 5xx`. Confirme no portal, depois do primeiro `apply`, que o valor `5xx` aparece na dimensão.
- **Orçamento**: só avisa por e-mail, não desliga nada. `budget_start_date` deve ser o dia 1 de um mês atual ou futuro.

## Pendências fora desta pasta

Não são da infraestrutura, mas o que está descrito aqui depende delas:

1. ~~**App (`app/`)**: nginx como *template* com proxy de `/api` e `VITE_API_URL=/api`.~~ Resolvido no PR #12: o nginx repassa `/api/` para `API_UPSTREAM`, bloqueia `/api/metrics` e serve `/metrics/api` com `METRICS_TOKEN`.
2. ~~**API (`api/`)**: variáveis e migrações da `feat/api-integracao`, `METRICS_TOKEN` e `PAINEL_EXPORT_PATH`.~~ Resolvido: a branch já está na `main`, e a API agora recebe `METRICS_TOKEN` (mesmo segredo do app), `HABILITAR_RC2`, `PAINEL_BLOB_URL` e `AZURE_CLIENT_ID` (container `painel`; o share `painel` e `PAINEL_EXPORT_PATH` são legado). Falta só **o pipeline de dados gravar o primeiro `painel.json` no container** (seção 5; a escrita é concedida por `painel_publicadores_object_ids`); até lá `GET /painel` dá 404.
3. ~~**Workflow de deploy** (`.github/workflows/`)~~ Resolvido: o job `deploy` do [`ci.yml`](../.github/workflows/ci.yml) usa `id-passoseguro-github` (OIDC) e roda só em push na `main`.
4. **Assistente**: `ASSISTENTE_URL` e `ASSISTENTE_TOKEN` já são entregues, mas o serviço do assistente não está em nenhum lugar da nuvem; sem ele `POST /assistente` responde a recusa padrão com o link do SP156. O mesmo vale para a visão (`VISAO_URL`/`VISAO_TOKEN` não são entregues ainda: sem eles o relato nasce sem categoria).

## Se o deploy der 403

`id-passoseguro-github` recebe *Contributor* **só no escopo de cada Container App**, mais *Reader* no resource group. Não existe papel embutido específico para `az containerapp update`. O comando faz um PUT que referencia o ambiente e a identidade `id-passoseguro-apps`, e o Azure pode exigir `Microsoft.App/managedEnvironments/join/action` no ambiente e `Microsoft.ManagedIdentity/userAssignedIdentities/assign/action` na identidade, que o *Contributor* do app não cobre. Se o primeiro deploy falhar com `AuthorizationFailed` citando uma dessas ações, ative o bloco abaixo (cole em `identidade.tf`, `terraform apply`). Ele cria um papel mínimo no escopo do resource group e o atribui só ao ambiente e à identidade dos apps, nada na assinatura:

```hcl
# resource "azurerm_role_definition" "deploy_containerapps" {
#   name        = "passoseguro-deploy-containerapps"
#   scope       = azurerm_resource_group.main.id
#   description = "Permite ao pipeline usar o ambiente e a identidade dos apps em um az containerapp update."
#
#   permissions {
#     actions = [
#       "Microsoft.App/managedEnvironments/join/action",
#       "Microsoft.ManagedIdentity/userAssignedIdentities/assign/action",
#     ]
#   }
#
#   assignable_scopes = [azurerm_resource_group.main.id]
# }
#
# resource "azurerm_role_assignment" "github_ambiente" {
#   scope              = azurerm_container_app_environment.main.id
#   role_definition_id = azurerm_role_definition.deploy_containerapps.role_definition_resource_id
#   principal_id       = azurerm_user_assigned_identity.github.principal_id
# }
#
# resource "azurerm_role_assignment" "github_identidade_apps" {
#   scope              = azurerm_user_assigned_identity.apps.id
#   role_definition_id = azurerm_role_definition.deploy_containerapps.role_definition_resource_id
#   principal_id       = azurerm_user_assigned_identity.github.principal_id
# }
```

Uma alternativa mais estreita que o *Contributor* seria um papel próprio só com `Microsoft.App/containerApps/read` e `write`; fica como evolução, depois que o primeiro deploy confirmar quais ações o `az containerapp update` realmente usa.
