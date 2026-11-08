# Logs e alertas. Os logs dos Container Apps vão para este workspace.

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-passoseguro"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  # 0,15 GB/dia ≈ 4,5 GB/mês: fica dentro da franquia gratuita de 5 GB por mês.
  # Ao atingir o teto do dia, a ingestão para até o dia seguinte (os alertas de métrica
  # não dependem dos logs).
  daily_quota_gb = 0.15

  tags = local.tags
}
