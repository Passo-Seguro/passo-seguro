# Identidades gerenciadas.
#
# 1) id-passoseguro-apps: usada pelos Container Apps para ler os segredos do Key Vault.
#    É user-assigned (e não a identidade do próprio app) para o papel existir ANTES dos apps:
#    com identidade do sistema, o app precisaria existir para receber o papel, mas não sobe
#    sem ler os segredos.
# 2) id-passoseguro-github: usada pelo pipeline (GitHub Actions) via OIDC, sem senha.

resource "azurerm_user_assigned_identity" "apps" {
  name                = "id-passoseguro-apps"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_role_assignment" "apps_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

# Espera a propagação do papel antes de criar os apps (que leem os segredos ao subir).
resource "time_sleep" "rbac_apps" {
  create_duration = "60s"

  depends_on = [azurerm_role_assignment.apps_secrets_user]
}

# Leitura do painel: a API lê o painel.json do container "painel" com esta identidade (via
# DefaultAzureCredential). Escopo SÓ no container (nem a conta, nem o ouro-export) e papel só de
# leitura. Quem GRAVA o arquivo (o pipeline de dados) é outra identidade, concedida abaixo por var.painel_publicadores_object_ids.
resource "azurerm_role_assignment" "apps_painel_leitura" {
  scope                = azurerm_storage_container.painel.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

# Publicação do painel: quem GRAVA o painel.json (o pipeline de dados e, se for o caso, pessoas
# para teste manual). Escopo SÓ no container "painel". Os object IDs vêm de
# var.painel_publicadores_object_ids, que fica fora do git (terraform.tfvars ou TF_VAR_*); com a
# lista vazia (o padrão) nada é criado e ninguém além do dono da assinatura consegue gravar.
resource "azurerm_role_assignment" "painel_publicadores" {
  for_each = toset(var.painel_publicadores_object_ids)

  scope                = azurerm_storage_container.painel.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
}

# ---------- Identidade do pipeline (GitHub Actions via OIDC) ----------
# Sem senha e sem App Registration no Entra ID: a identidade gerenciada recebe uma credencial
# federada que só aceita o token do GitHub emitido para este repositório e este environment.
resource "azurerm_user_assigned_identity" "github" {
  name                = "id-passoseguro-github"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_federated_identity_credential" "github" {
  name      = "github-environment-production"
  parent_id = azurerm_user_assigned_identity.github.id
  issuer    = "https://token.actions.githubusercontent.com"
  audience  = ["api://AzureADTokenExchange"]
  # O repositório usa o subject OIDC IMUTÁVEL (use_immutable_subject = true): o GitHub troca os
  # nomes por IDs, e o token de verdade chega como o valor abaixo, não como
  # "repo:Passo-Seguro/passo-seguro:...". Com o nome o login falha (AADSTS700213). Os IDs são
  # os da organização (352685166) e do repositório (1446389696); o ID do repositório só muda se
  # ele for apagado e recriado, e um rename não o altera. Conferir com:
  #   gh api repos/Passo-Seguro/passo-seguro/actions/oidc/customization/sub
  # (campo sub_claim_prefix).
  subject = "repo:Passo-Seguro@352685166/passo-seguro@1446389696:environment:production"
}

# Menor privilégio: o papel é concedido SÓ no escopo de cada um dos dois Container Apps, e
# nada no escopo da assinatura. Não existe papel embutido específico para
# "az containerapp update"; o Contributor no escopo do próprio app é o menor que o permite.
# Se o primeiro deploy der 403, veja a seção "Se o deploy der 403" em infra/README.md.
resource "azurerm_role_assignment" "github_api" {
  scope                = azurerm_container_app.api.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}

resource "azurerm_role_assignment" "github_app" {
  scope                = azurerm_container_app.app.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}

# Reader no resource group: o "az containerapp update" lê o ambiente e os recursos vizinhos.
resource "azurerm_role_assignment" "github_leitura" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}
