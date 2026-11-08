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
