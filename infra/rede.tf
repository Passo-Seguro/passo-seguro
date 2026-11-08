# Rede privada: uma VNet com duas sub-redes. O ambiente de Container Apps fica em snet-aca e
# o Postgres em snet-db, sem endereço público. Só o app (nginx) é exposto à internet.

resource "azurerm_virtual_network" "main" {
  name                = "vnet-passoseguro"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.20.0.0/16"]
  tags                = local.tags
}

locals {
  cidr_aca = "10.20.0.0/27"
  cidr_db  = "10.20.1.0/28"
}

resource "azurerm_subnet" "aca" {
  name                 = "snet-aca"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [local.cidr_aca]

  # Exigência do ambiente de Container Apps com workload profiles (sub-rede mínima: /27).
  delegation {
    name = "container-apps"

    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "db" {
  name                 = "snet-db"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [local.cidr_db]

  delegation {
    name = "postgres-flexible"

    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# ---------- NSG do ambiente de Container Apps ----------
# Referência: https://learn.microsoft.com/azure/container-apps/firewall-integration
# Com workload profiles e ambiente externo, o NSG de entrada só vale para o tráfego que passa
# pela VNet, e a documentação pede liberar 80 e 443 para o app público. NÃO criamos regra de
# saída: as regras padrão do NSG (AllowVnetOutBound e AllowInternetOutBound) já cobrem o que a
# plataforma precisa (MicrosoftContainerRegistry, AzureFrontDoor.FirstParty,
# AzureActiveDirectory e AzureMonitor na 443, DNS do Azure em 168.63.129.16 e tráfego
# dentro da própria sub-rede). Um deny de saída exigiria reproduzir essa tabela inteira.
# Nenhuma regra para 22, 3389 ou outra porta de administração.
resource "azurerm_network_security_group" "aca" {
  name                = "nsg-snet-aca"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  #trivy:ignore:AVD-AZU-0047 O app é público de propósito: só 80/tcp (redireciona para HTTPS) e 443/tcp, nada de administração.
  security_rule {
    name                       = "permitir-http-internet"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "Internet"
    destination_address_prefix = local.cidr_aca
  }

  #trivy:ignore:AVD-AZU-0047 O app é público de propósito: só 80/tcp (redireciona para HTTPS) e 443/tcp, nada de administração.
  security_rule {
    name                       = "permitir-https-internet"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "Internet"
    destination_address_prefix = local.cidr_aca
  }
}

resource "azurerm_subnet_network_security_group_association" "aca" {
  subnet_id                 = azurerm_subnet.aca.id
  network_security_group_id = azurerm_network_security_group.aca.id
}

# ---------- NSG do banco ----------
# Só a sub-rede dos Container Apps fala com o Postgres, e só na 5432. O Allow dentro da
# própria sub-rede é necessário ao Postgres Flexible Server (componentes internos do serviço).
# Os Deny explícitos (4000 e 4010) valem mais que as regras padrão AllowVnetInBound, então
# nenhuma outra origem da VNet ou da internet chega ao banco.
resource "azurerm_network_security_group" "db" {
  name                = "nsg-snet-db"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  security_rule {
    name                       = "permitir-postgres-do-aca"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "5432"
    source_address_prefix      = local.cidr_aca
    destination_address_prefix = local.cidr_db
  }

  security_rule {
    name                       = "permitir-trafego-interno-da-subnet"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = local.cidr_db
    destination_address_prefix = local.cidr_db
  }

  security_rule {
    name                       = "negar-internet"
    priority                   = 4000
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "negar-resto-da-vnet"
    priority                   = 4010
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "db" {
  subnet_id                 = azurerm_subnet.db.id
  network_security_group_id = azurerm_network_security_group.db.id
}
