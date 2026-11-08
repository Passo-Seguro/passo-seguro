# Key Vault com todos os segredos da aplicação. Os valores são gerados pelo Terraform
# (random_password) e vivem só no state remoto e no cofre; nada vai para o git nem para
# outputs. Os Container Apps leem os segredos por referência, com a identidade
# id-passoseguro-apps (ver identidade.tf).

resource "azurerm_key_vault" "main" {
  name                = "kv-passoseguro-${local.sufixo}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Permissões por RBAC (papéis), sem access policies.
  rbac_authorization_enabled = true

  # Soft delete mínimo (7 dias). A purge protection fica DESLIGADA para o terraform destroy
  # apagar o cofre de verdade na assinatura de estudante (com ela ligada o nome ficaria preso
  # até o fim da retenção). Em produção real: purge protection ligada.
  soft_delete_retention_days = 7
  #trivy:ignore:AVD-AZU-0016 Desligada de propósito para o destroy funcionar na assinatura de estudante.
  purge_protection_enabled = false

  # Acesso público permitido: os Container Apps leem os segredos pelo endereço público do
  # cofre. Em produção real usaríamos private endpoint e fecharíamos o acesso público.
  #trivy:ignore:AVD-AZU-0013 Aberto de propósito no MVP (ver comentário acima); o acesso exige Entra ID + RBAC.
  public_network_access_enabled = true

  tags = local.tags
}

# Quem roda o Terraform precisa escrever segredos.
resource "azurerm_role_assignment" "executor_secrets_officer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# A propagação de RBAC no Azure pode levar alguns segundos e causar 403 logo após a criação
# do papel. Esta espera evita que a criação dos segredos falhe por isso.
resource "time_sleep" "rbac_executor" {
  create_duration = "60s"

  depends_on = [azurerm_role_assignment.executor_secrets_officer]
}

# ---------- Segredos gerados ----------
locals {
  segredos_gerados = toset(["service-token", "device-token", "metrics-token", "salt-autor"])
}

resource "random_password" "gerado" {
  for_each = local.segredos_gerados

  length  = 48
  special = false
}

resource "azurerm_key_vault_secret" "gerado" {
  for_each = local.segredos_gerados

  name         = each.key
  value        = random_password.gerado[each.key].result
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"
  tags         = local.tags

  depends_on = [time_sleep.rbac_executor]
}

resource "azurerm_key_vault_secret" "db_password" {
  name         = "db-password"
  value        = random_password.db.result
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"
  tags         = local.tags

  depends_on = [time_sleep.rbac_executor]
}

# URL de conexão da API (SQLAlchemy + psycopg). O endereço é o nome privado do servidor.
resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  value        = "postgresql+psycopg://${azurerm_postgresql_flexible_server.main.administrator_login}:${random_password.db.result}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.passo_seguro.name}?sslmode=require"
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"
  tags         = local.tags

  depends_on = [time_sleep.rbac_executor]
}

# Token do serviço do assistente (LLM no Railway). O valor vem de var.assistente_token.
resource "azurerm_key_vault_secret" "assistente_token" {
  name         = "assistente-token"
  value        = var.assistente_token
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"
  tags         = local.tags

  depends_on = [time_sleep.rbac_executor]
}
