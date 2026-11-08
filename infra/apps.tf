# Ambiente de Container Apps (perfil de carga Consumption, dentro da VNet) e os dois apps:
#   ca-passoseguro-app  PWA + nginx, ingress EXTERNO (a única porta de entrada da internet)
#   ca-passoseguro-api  FastAPI, ingress INTERNO (só o app fala com ela, pelo nome interno)

locals {
  # Endereço público do app, calculado a partir do domínio do ambiente (e não lido do app)
  # para a API poder usá-lo sem criar dependência circular entre os dois apps.
  app_fqdn = "ca-passoseguro-app.${azurerm_container_app_environment.main.default_domain}"

  # Referências aos segredos do Key Vault: o app lê com a identidade id-passoseguro-apps.
  # "versionless_id" faz o app sempre pegar a versão atual (rotação sem novo apply).
  segredos_api = {
    "database-url"     = azurerm_key_vault_secret.database_url.versionless_id
    "service-token"    = azurerm_key_vault_secret.gerado["service-token"].versionless_id
    "device-token"     = azurerm_key_vault_secret.gerado["device-token"].versionless_id
    "salt-autor"       = azurerm_key_vault_secret.gerado["salt-autor"].versionless_id
    "metrics-token"    = azurerm_key_vault_secret.gerado["metrics-token"].versionless_id # o mesmo que o app usa
    "assistente-token" = azurerm_key_vault_secret.assistente_token.versionless_id
  }
}

resource "azurerm_container_app_environment" "main" {
  name                = "cae-passoseguro"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  logs_destination           = "log-analytics"

  infrastructure_subnet_id       = azurerm_subnet.aca.id
  internal_load_balancer_enabled = false # o app é público; a API é protegida pelo ingress interno
  zone_redundancy_enabled        = false

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }

  tags = local.tags

  depends_on = [azurerm_subnet_network_security_group_association.aca]
}

# Volume das fotos: o Azure Files "fotos", montado na API em /data/fotos.
resource "azurerm_container_app_environment_storage" "fotos" {
  name                         = "fotos"
  container_app_environment_id = azurerm_container_app_environment.main.id
  account_name                 = azurerm_storage_account.main.name
  share_name                   = azurerm_storage_share.fotos.name
  access_key                   = azurerm_storage_account.main.primary_access_key
  access_mode                  = "ReadWrite"
}

# Volume do painel: o Azure Files "painel", montado SOMENTE LEITURA na API em /data/painel.
# Quem grava o arquivo é o pipeline de dados (ver infra/README.md, "Subir o arquivo do painel").
resource "azurerm_container_app_environment_storage" "painel" {
  name                         = "painel"
  container_app_environment_id = azurerm_container_app_environment.main.id
  account_name                 = azurerm_storage_account.main.name
  share_name                   = azurerm_storage_share.painel.name
  access_key                   = azurerm_storage_account.main.primary_access_key
  access_mode                  = "ReadOnly"
}

# ---------- API ----------
resource "azurerm_container_app" "api" {
  name                         = "ca-passoseguro-api"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  workload_profile_name        = "Consumption"
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  dynamic "secret" {
    for_each = local.segredos_api

    content {
      name                = secret.key
      key_vault_secret_id = secret.value
      identity            = azurerm_user_assigned_identity.apps.id
    }
  }

  ingress {
    external_enabled = false # interno: sem endereço na internet
    target_port      = 8000
    transport        = "auto"

    # O app (nginx) chama a API por http://ca-passoseguro-api, dentro do ambiente. Com a
    # opção desligada o ingress responderia 301 para HTTPS e o nginx não seguiria o
    # redirecionamento. O tráfego não sai da VNet; a TLS fica no app público.
    allow_insecure_connections = true

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = 2

    volume {
      name         = "fotos"
      storage_name = azurerm_container_app_environment_storage.fotos.name
      storage_type = "AzureFile"
      # A imagem roda como uid/gid 10001 (usuário "app", sem privilégios): o volume precisa
      # pertencer a ele para a API gravar as fotos.
      mount_options = "uid=10001,gid=10001,file_mode=0660,dir_mode=0770"
    }

    volume {
      name         = "painel"
      storage_name = azurerm_container_app_environment_storage.painel.name
      storage_type = "AzureFile"
      # Só leitura (o share foi registrado como ReadOnly); o arquivo pertence ao usuário da API.
      mount_options = "uid=10001,gid=10001,file_mode=0440,dir_mode=0550"
    }

    container {
      name   = "api"
      image  = var.image_api
      cpu    = 0.5
      memory = "1Gi"

      # Mesmo comando do docker-compose.dev.yml: migra o banco e sobe a API. O exec faz o
      # uvicorn virar o processo principal (recebe os sinais de parada).
      command = [
        "sh", "-c",
        "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log",
      ]

      env {
        name  = "MEDIA_DIR"
        value = "/data/fotos"
      }
      # A emenda rc2 do contrato (mapa por perto, meus relatos, correção de categoria) é o que o
      # app usa; sem isto essas rotas não existem na API.
      env {
        name  = "HABILITAR_RC2"
        value = "true"
      }
      # Arquivo JSON do painel (formato: docs/exemplos/vw_prioridades.json), no share "painel".
      env {
        name  = "PAINEL_EXPORT_PATH"
        value = "/data/painel/vw_prioridades.json"
      }
      env {
        name  = "ASSISTENTE_URL"
        value = var.assistente_url
      }
      env {
        name  = "PUBLIC_BASE_URL"
        value = "https://${local.app_fqdn}/api"
      }
      env {
        name  = "CORS_ORIGINS"
        value = "https://${local.app_fqdn}"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "SERVICE_TOKEN"
        secret_name = "service-token"
      }
      env {
        name        = "DEVICE_TOKEN"
        secret_name = "device-token"
      }
      # Mesmo segredo do app: o nginx confere em /metrics/api e repassa o cabeçalho; a API confere de novo.
      env {
        name        = "METRICS_TOKEN"
        secret_name = "metrics-token"
      }
      env {
        name        = "SALT_AUTOR"
        secret_name = "salt-autor"
      }
      env {
        name        = "ASSISTENTE_TOKEN"
        secret_name = "assistente-token"
      }

      volume_mounts {
        name = "fotos"
        path = "/data/fotos"
      }
      volume_mounts {
        name = "painel"
        path = "/data/painel"
      }

      # A partida inclui "alembic upgrade head"; a startup_probe dá tempo (até ~2 min) antes
      # de a liveness poder reiniciar o contêiner.
      startup_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/saude"
        interval_seconds        = 5
        timeout                 = 3
        failure_count_threshold = 24
      }

      liveness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/saude"
        interval_seconds        = 15
        timeout                 = 3
        failure_count_threshold = 3
      }

      readiness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/saude"
        interval_seconds        = 10
        timeout                 = 3
        failure_count_threshold = 3
      }
    }
  }

  # O pipeline troca a imagem a cada deploy (az containerapp update); o Terraform não deve
  # desfazer isso no plano seguinte.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    time_sleep.rbac_apps,
    azurerm_postgresql_flexible_server_configuration.extensoes, # PostGIS liberado antes da migração
  ]
}

# ---------- App (PWA + nginx) ----------
resource "azurerm_container_app" "app" {
  name                         = "ca-passoseguro-app"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  workload_profile_name        = "Consumption"
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  secret {
    name                = "metrics-token"
    key_vault_secret_id = azurerm_key_vault_secret.gerado["metrics-token"].versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }

  ingress {
    external_enabled           = true
    target_port                = 8080
    transport                  = "auto"
    allow_insecure_connections = false # HTTP é redirecionado para HTTPS

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = 2

    container {
      name   = "app"
      image  = var.image_app
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "API_UPSTREAM"
        value = "http://${azurerm_container_app.api.name}" # nome interno da API no ambiente
      }
      env {
        name        = "METRICS_TOKEN"
        secret_name = "metrics-token"
      }

      liveness_probe {
        transport               = "HTTP"
        port                    = 8080
        path                    = "/healthz"
        interval_seconds        = 15
        timeout                 = 3
        failure_count_threshold = 3
      }

      readiness_probe {
        transport               = "HTTP"
        port                    = 8080
        path                    = "/healthz"
        interval_seconds        = 10
        timeout                 = 3
        failure_count_threshold = 3
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [time_sleep.rbac_apps]
}
