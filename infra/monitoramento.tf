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

# ---------- Alertas ----------
resource "azurerm_monitor_action_group" "email" {
  name                = "ag-passoseguro-email"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "passoseguro" # no máximo 12 caracteres
  tags                = local.tags

  email_receiver {
    name                    = "equipe"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

# Mais de 5 respostas 5xx do app em 5 minutos, avaliado a cada minuto.
# Métrica "Requests" do Container App, filtrada por statusCodeCategory = 5xx.
resource "azurerm_monitor_metric_alert" "erros_5xx_app" {
  name                = "alerta-5xx-ca-passoseguro-app"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.app.id]
  description         = "Mais de 5 respostas 5xx em 5 minutos no app."
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.tags

  criteria {
    metric_namespace = "Microsoft.App/containerapps"
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 5

    dimension {
      name     = "statusCodeCategory"
      operator = "Include"
      values   = ["5xx"]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}
