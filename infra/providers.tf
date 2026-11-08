# Estado remoto no Azure Storage, com configuração PARCIAL: os valores (conta, container,
# chave) ficam em infra/backend.hcl, que o git ignora. Modelo em backend.hcl.example.
#
#   terraform init -backend-config=backend.hcl
terraform {
  backend "azurerm" {}
}

# O azurerm 4.x exige a assinatura. Não a versionamos: exporte antes de rodar o Terraform
#   export ARM_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
provider "azurerm" {
  features {
    key_vault {
      # A purge protection está desligada de propósito (ver segredos.tf). Com isto o destroy
      # apaga o cofre de verdade e um novo apply pode reutilizar o mesmo nome.
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
  }
}
