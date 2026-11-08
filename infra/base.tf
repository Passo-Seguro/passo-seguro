# Base comum: quem está rodando o Terraform, sufixo dos nomes globais, tags e o grupo de recursos.
# (O endereço do app, "app_fqdn", é calculado em apps.tf.)

data "azurerm_client_config" "current" {}

# Nomes de storage, Key Vault e Postgres são únicos no mundo todo; o sufixo evita colisão.
resource "random_string" "sufixo" {
  length  = 5
  upper   = false
  special = false
}

locals {
  tags = {
    projeto    = "passo-seguro"
    ambiente   = "prod"
    disciplina = "secure-devops"
  }

  sufixo = random_string.sufixo.result
}

resource "azurerm_resource_group" "main" {
  name     = "rg-passoseguro-prod"
  location = var.location
  tags     = local.tags
}
