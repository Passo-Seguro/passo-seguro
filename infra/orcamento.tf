# Orçamento mensal do resource group, com aviso por e-mail ao passar de 50%, 80% e 100%.
# O orçamento só AVISA; não desliga nada. Fique de olho no saldo da assinatura de estudante.

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "orcamento-passoseguro-prod"
  resource_group_id = azurerm_resource_group.main.id

  amount     = var.budget_amount
  time_grain = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  dynamic "notification" {
    for_each = toset([50, 80, 100])

    content {
      enabled        = true
      threshold      = notification.value
      threshold_type = "Actual"
      operator       = "GreaterThan"
      contact_emails = [var.alert_email]
    }
  }

  # O Azure só aceita start_date no mês atual ou futuro; depois de criado, o valor não deve
  # ser "corrigido" pelo plano a cada virada de mês.
  lifecycle {
    ignore_changes = [time_period]
  }
}
