# Storage account: shares "fotos" e "painel" (Azure Files, montados na API) e container privado
# "ouro-export" (camada Ouro exportada pelo pipeline de dados).

#trivy:ignore:AVD-AZU-0012 Firewall aberto de propósito: o Databricks lê o container "ouro-export" de fora da VNet (ver comentário abaixo).
resource "azurerm_storage_account" "main" {
  name                = "stpassoseguro${local.sufixo}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"

  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false # nenhum blob é público

  # Os Container Apps só montam Azure Files com a CHAVE da conta (o ambiente não aceita
  # identidade gerenciada nem Entra ID para o volume). Por isso a chave fica habilitada.
  # Ela só é lida pelo Terraform e gravada no ambiente de Container Apps; não vai ao
  # Key Vault, ao git nem aos outputs. Para trocar, gire a chave na conta e rode o apply.
  shared_access_key_enabled = true

  # Sem bloco network_rules: o firewall fica aberto (padrão) de propósito, porque o Databricks
  # (parte de Big Data) lê o container "ouro-export" de fora da VNet. Em produção real
  # usaríamos private endpoint, ou ao menos regras de IP, e fecharíamos o acesso público.

  tags = local.tags
}

resource "azurerm_storage_share" "fotos" {
  name               = "fotos"
  storage_account_id = azurerm_storage_account.main.id
  quota              = 5 # GB
}

# Painel de prioridades: o Container Apps só monta Azure Files (não monta blob). O pipeline de
# dados grava aqui o vw_prioridades.json; a API monta o share SOMENTE LEITURA em /data/painel.
# O container de blob "ouro-export" abaixo continua sendo a saída da parte de Big Data.
resource "azurerm_storage_share" "painel" {
  name               = "painel"
  storage_account_id = azurerm_storage_account.main.id
  quota              = 1 # GB
}

resource "azurerm_storage_container" "ouro_export" {
  name                  = "ouro-export"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}
