# Infraestrutura (Terraform)

Descreve toda a nuvem do MVP na Azure. Produção 100% gerenciada: **Container Apps + PostgreSQL Flexible Server**, tudo em `centralus`. Nenhum segredo real é versionado; os valores de exemplo são **fictícios**.

```
internet ──► ca-passoseguro-app (nginx, ingress externo, 8080)
                    │  http://ca-passoseguro-api (nome interno)
                    ▼
             ca-passoseguro-api (FastAPI, ingress interno, 8000) ──► Azure Files "fotos" (/data/fotos)
                    │                                           └──► Azure Files "painel" (/data/painel, só leitura)
                    │ 5432, só pela rede privada
                    ▼
             PostgreSQL Flexible Server 16 + PostGIS (snet-db, sem endereço público)

Key Vault ── segredos (lidos pelos apps com a identidade id-passoseguro-apps)
Storage   ── shares "fotos" e "painel" + container "ouro-export" (Big Data)
Log Analytics, alerta de 5xx e orçamento mensal por e-mail
```

| Arquivo | O que descreve |
|---|---|
| `base.tf` | resource group `rg-passoseguro-prod`, sufixo dos nomes globais, tags |
| `rede.tf` | VNet `10.20.0.0/16`, `snet-aca`, `snet-db` e os NSGs |
| `banco.tf` | PostgreSQL Flexible Server, DNS privado, PostGIS, banco `passo_seguro` |
| `storage.tf` | conta de armazenamento, shares `fotos` e `painel`, container `ouro-export` |
| `segredos.tf` | Key Vault e os segredos (gerados pelo Terraform) |
| `identidade.tf` | `id-passoseguro-apps` (lê segredos) e `id-passoseguro-github` (pipeline, OIDC) |
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

O que o Trivy reporta e foi **aceito de propósito** está marcado com `#trivy:ignore:<ID>` e o motivo, acima do recurso: `AVD-AZU-0012` (firewall aberto do storage, por causa do Databricks), `AVD-AZU-0013` e `AVD-AZU-0016` (Key Vault público e sem purge protection, para o `destroy` funcionar) e `AVD-AZU-0047` (80/443 abertos no app público). Segredos sem data de validade (`AVD-AZU-0017`, LOW) também são de propósito: segredo vencido não pode ser lido e derrubaria a API.

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

`GET /painel` lê um arquivo JSON exportado pelo pipeline de dados. O Container Apps só monta **Azure Files** (não monta blob), então o arquivo mora no share `painel`, montado **somente leitura** na API em `/data/painel`; a API lê `PAINEL_EXPORT_PATH=/data/painel/vw_prioridades.json` a cada chamada, então não precisa reiniciar nada. O container de blob `ouro-export` continua sendo a saída da parte de Big Data; quem publica o painel copia o resultado para o share.

Enquanto o arquivo não existir, `GET /painel` responde 404 (`painel_indisponivel`), o que é o comportamento esperado do primeiro deploy. O formato é uma lista de `PrioridadeSubprefeitura` do contrato; use [`docs/exemplos/vw_prioridades.json`](../docs/exemplos/vw_prioridades.json) como modelo (até 5 MB; fora do schema, a API responde 503 `painel_invalido`).

```bash
cd infra
az storage file upload   --account-name "$(terraform output -raw storage_account_name)"   --share-name painel   --source ../docs/exemplos/vw_prioridades.json   --path vw_prioridades.json   --auth-mode key          # usa a chave da conta (quem tem papel Owner/Contributor na assinatura consegue lê-la)
curl "$(terraform output -raw app_url)/api/painel"
```

O nome do arquivo no share precisa ser exatamente `vw_prioridades.json`. Para enviar sem a chave da conta, troque por `--auth-mode login --enable-file-backup-request-intent` (exige o papel *Storage File Data Privileged Contributor* no share). O pipeline de dados deve **sobrescrever** o arquivo com o mesmo comando; uma leitura exatamente durante a troca pode dar um 503 isolado.

## Decisões e cuidados

- **Segredos** são gerados pelo Terraform e moram no Key Vault. Os apps leem por referência com `id-passoseguro-apps` (user-assigned, para o papel existir antes dos apps). Quem roda o Terraform recebe *Key Vault Secrets Officer*. O state remoto contém os valores; proteja o acesso à conta do state.
- **Rede**: o Postgres não tem endereço público; só `snet-aca` alcança a porta 5432. O NSG de `snet-aca` só aceita 80 e 443 da internet. Não existe regra para 22, 3389 nem porta de administração. A API tem ingress interno.
- **Ingress da API aceita HTTP** (`allow_insecure_connections = true`) porque o nginx a chama por `http://ca-passoseguro-api` dentro do ambiente; com a opção desligada o ingress responderia um redirecionamento para HTTPS e o nginx não o seguiria. O app público força HTTPS.
- **Painel em Azure Files, não em blob**: o Container Apps não monta blob. O share `painel` (1 GB) é montado só leitura na API; a escrita é de quem tem a chave da conta, pelo `az storage file upload` da seção 5.
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
2. ~~**API (`api/`)**: variáveis e migrações da `feat/api-integracao`, `METRICS_TOKEN` e `PAINEL_EXPORT_PATH`.~~ Resolvido: a branch já está na `main`, e a API agora recebe `METRICS_TOKEN` (mesmo segredo do app), `HABILITAR_RC2` e `PAINEL_EXPORT_PATH` (share `painel`). Falta só **subir o primeiro arquivo do painel** (seção 5); até lá `GET /painel` dá 404.
3. **Workflow de deploy** (`.github/workflows/`): ainda não existe (só `api-tests.yml`); usará `id-passoseguro-github`.
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
