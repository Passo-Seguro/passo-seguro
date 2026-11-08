# PostgreSQL Flexible Server 16, só com endereço privado (sub-rede delegada + DNS privado).
# O PostGIS vem da migração 0001 da API (CREATE EXTENSION IF NOT EXISTS postgis); aqui só
# liberamos a extensão na lista do servidor.

resource "random_password" "db" {
  length  = 32
  special = false # a senha entra numa URL (DATABASE_URL); sem especiais não precisa de URL-encode
  upper   = true
  lower   = true
  numeric = true

  min_upper   = 1
  min_lower   = 1
  min_numeric = 1
}

# Zona de DNS privada: o nome do servidor resolve para o IP da sub-rede, só dentro da VNet.
resource "azurerm_private_dns_zone" "postgres" {
  name                = "passoseguro.private.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name                  = "vnet-passoseguro"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id    = azurerm_virtual_network.main.id
  registration_enabled  = false
  tags                  = local.tags
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                = "psql-passoseguro-${local.sufixo}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  version    = "16"
  sku_name   = "B_Standard_B1ms"
  storage_mb = 32768

  backup_retention_days        = 7
  geo_redundant_backup_enabled = false

  # Acesso só pela rede privada: sem endereço público.
  delegated_subnet_id           = azurerm_subnet.db.id
  private_dns_zone_id           = azurerm_private_dns_zone.postgres.id
  public_network_access_enabled = false

  administrator_login    = "passo_admin"
  administrator_password = random_password.db.result

  tags = local.tags

  # A zona de disponibilidade é escolhida pelo Azure na criação; sem isto o plano
  # tentaria "corrigi-la" a cada execução.
  lifecycle {
    ignore_changes = [zone]
  }

  depends_on = [azurerm_private_dns_zone_virtual_network_link.postgres]
}

# Libera a extensão PostGIS (a migração 0001 faz o CREATE EXTENSION).
resource "azurerm_postgresql_flexible_server_configuration" "extensoes" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "POSTGIS"
}

resource "azurerm_postgresql_flexible_server_database" "passo_seguro" {
  name      = "passo_seguro"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}
