# Storage account: share "fotos" (Azure Files, montado na API) e containers de blob privados:
# "ouro-export" (camada Ouro exportada pelo pipeline de dados) e "painel" (painel.json que a API
# serve em GET /painel). O share "painel" (Azure Files) é o caminho antigo e já não é usado pela
# API; ver o comentário dele abaixo.

# Semgrep storage-queue-services-logging: o Queue Storage não é usado nesta conta (só Azure Files e Blob), então não há fila para registrar.
#trivy:ignore:AVD-AZU-0012 Firewall aberto de propósito: o Databricks lê o container "ouro-export" de fora da VNet (ver comentário abaixo).
resource "azurerm_storage_account" "main" { # nosemgrep: terraform.azure.security.storage.storage-queue-services-logging.storage-queue-services-logging
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

# LEGADO: caminho antigo do painel (o Container Apps só monta Azure Files). A API agora lê o
# blob do container "painel" abaixo, com identidade gerenciada, e deixou de receber
# PAINEL_EXPORT_PATH. O share e o volume ficam por ora para o apply não apagar nada; podem ser
# removidos num PR próprio, depois que o painel.json do blob estiver no ar.
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

# Painel de prioridades: o pipeline de dados grava o painel.json aqui e a API o lê em GET /painel.
# Privado (sem acesso anônimo): a leitura é só pela identidade gerenciada da API, sem SAS e sem chave.
resource "azurerm_storage_container" "painel" {
  name                  = "painel"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

locals {
  # URL do blob, sem SAS e sem chave (o primary_blob_endpoint termina em "/").
  painel_blob_url = "${azurerm_storage_account.main.primary_blob_endpoint}${azurerm_storage_container.painel.name}/painel.json"
}
