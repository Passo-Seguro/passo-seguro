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
  subject   = "repo:Passo-Seguro/passo-seguro:environment:production"
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
