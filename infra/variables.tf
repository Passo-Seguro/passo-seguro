variable "location" {
  description = "Região de TUDO (VNet, Container Apps e Postgres precisam estar na mesma). Na assinatura Azure for Students usamos centralus."
  type        = string
}

variable "image_api" {
  description = "Imagem da API, ex.: ghcr.io/passo-seguro/passo-seguro-api:bootstrap. O pipeline troca a tag a cada deploy."
  type        = string
}

variable "image_app" {
  description = "Imagem do app (PWA + nginx), ex.: ghcr.io/passo-seguro/passo-seguro-app:bootstrap. O pipeline troca a tag a cada deploy."
  type        = string
}

variable "min_replicas" {
  description = "Réplicas mínimas de cada Container App. 0 escala a zero (custo mínimo, partida a frio); 1 mantém sempre no ar."
  type        = number
  default     = 0

  validation {
    condition     = var.min_replicas >= 0 && var.min_replicas <= 2
    error_message = "min_replicas deve ficar entre 0 e 2 (o máximo de cada app é 2)."
  }
}

variable "assistente_url" {
  description = "URL do serviço do assistente (LLM), hospedado no Railway."
  type        = string
}

variable "assistente_token" {
  description = "Token do serviço do assistente (Railway). Vai para o Key Vault; nunca versione."
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "E-mail que recebe os alertas de erro 5xx e os avisos de orçamento."
  type        = string
}

variable "budget_amount" {
  description = "Orçamento mensal do resource group, em dólares."
  type        = number
  default     = 10
}

variable "budget_start_date" {
  description = "Início do orçamento: dia 1 do mês atual ou futuro, no formato 2026-11-01T00:00:00Z. O Azure rejeita datas de meses passados; depois de criado, o valor é ignorado nos planos."
  type        = string
  default     = "2026-11-01T00:00:00Z"

  validation {
    condition     = can(regex("^[0-9]{4}-[0-9]{2}-01T00:00:00Z$", var.budget_start_date))
    error_message = "budget_start_date deve ser o dia 1 de um mês, às 00:00:00 UTC (ex.: 2026-11-01T00:00:00Z)."
  }
}
