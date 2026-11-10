# Nada aqui é segredo: são nomes e identificadores públicos. Segredos ficam no Key Vault.
# A lista de quais copiar para o GitHub está em infra/README.md.

output "app_url" {
  description = "Endereço público do app (PWA)."
  value       = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}

output "resource_group" {
  description = "Nome do resource group."
  value       = azurerm_resource_group.main.name
}

output "api_app_name" {
  description = "Nome do Container App da API (usado pelo pipeline no az containerapp update)."
  value       = azurerm_container_app.api.name
}

output "web_app_name" {
  description = "Nome do Container App do app web (usado pelo pipeline no az containerapp update)."
  value       = azurerm_container_app.app.name
}

output "environment_name" {
  description = "Nome do ambiente de Container Apps."
  value       = azurerm_container_app_environment.main.name
}

output "key_vault_name" {
  description = "Nome do Key Vault."
  value       = azurerm_key_vault.main.name
}

output "storage_account_name" {
  description = "Nome da conta de armazenamento (share fotos e containers ouro-export e painel)."
  value       = azurerm_storage_account.main.name
}

output "postgres_fqdn" {
  description = "Nome privado do servidor PostgreSQL (só resolve dentro da VNet)."
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "github_client_id" {
  description = "client_id da identidade id-passoseguro-github (vai para o GitHub como AZURE_CLIENT_ID)."
  value       = azurerm_user_assigned_identity.github.client_id
}

output "tenant_id" {
  description = "ID do tenant do Entra ID (AZURE_TENANT_ID no GitHub)."
  value       = data.azurerm_client_config.current.tenant_id
}

output "subscription_id" {
  description = "ID da assinatura (AZURE_SUBSCRIPTION_ID no GitHub)."
  value       = data.azurerm_client_config.current.subscription_id
}

output "painel_blob_url" {
  description = "URL do painel.json (container privado \"painel\"), sem SAS nem chave. É o destino do pipeline de dados."
  value       = local.painel_blob_url
}
