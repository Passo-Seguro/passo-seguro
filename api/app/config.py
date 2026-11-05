"""Configuração da API, toda por variável de ambiente (nenhum segredo no código).

Os valores padrão abaixo servem só para desenvolvimento local e são fictícios. Segredos
(tokens, sal) começam VAZIOS: vazio significa "recurso desligado" (ver app/seguranca.py).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.dominio import MAX_UPLOAD_BYTES


class BoundingBox:
    """Retângulo lat/lon, usado para limitar onde um relato pode ser criado."""

    def __init__(self, lat_min: float, lon_min: float, lat_max: float, lon_max: float):
        if lat_min >= lat_max or lon_min >= lon_max:
            raise ValueError("bounding box inválida: mínimos devem ser menores que máximos")
        self.lat_min, self.lon_min, self.lat_max, self.lon_max = lat_min, lon_min, lat_max, lon_max

    @classmethod
    def de_texto(cls, texto: str) -> "BoundingBox":
        """Lê 'lat_min,lon_min,lat_max,lon_max'."""
        partes = [float(p) for p in texto.split(",")]
        if len(partes) != 4:
            raise ValueError("esperado 'lat_min,lon_min,lat_max,lon_max'")
        return cls(*partes)

    def contem(self, lat: float, lon: float) -> bool:
        return self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Banco (Postgres + PostGIS). Valor de DESENVOLVIMENTO, fictício.
    database_url: str = "postgresql+psycopg://passo:passo-dev@localhost:5432/passo_seguro"

    # Segredos. Vazio = recurso desligado (fecha por padrão).
    service_token: str = ""  # chamadas entre serviços (bearerAuth)
    device_token: str = ""  # robô inspetor (X-Device-Token), só com a emenda rc2
    metrics_token: str = ""  # raspagem do /metrics
    salt_autor: str = ""  # sal do hash do autor_id (nunca logar o id nem o hash)

    # Fotos (armazenamento local em desenvolvimento).
    media_dir: Path = Path("./dados/fotos")
    public_base_url: str = "http://localhost:8000"

    # CORS: origens separadas por vírgula, ou "*" (só para desenvolvimento).
    cors_origins: str = "*"

    # Onde um relato pode ser criado. Padrão: caixa que envolve o município de São Paulo.
    # Formato 'lat_min,lon_min,lat_max,lon_max'. Use 'sem-limite' para desligar a checagem.
    area_permitida: str = "-24.01,-46.84,-23.35,-46.36"

    max_upload_bytes: int = Field(default=MAX_UPLOAD_BYTES, gt=0)

    # Serviço de visão (POST /deteccoes de outro serviço). Sem URL e sem fake, a visão fica
    # "fora do ar": o relato é criado mesmo assim, com categoria e confiança nulas.
    visao_url: str = ""
    visao_token: str = ""
    visao_timeout_s: float = Field(default=5.0, gt=0)
    use_fake_visao: bool = False

    # Emenda rc2 do contrato (autor_id, X-Device-Token, /relatos/proximos, /meus-relatos e
    # PATCH /relatos/{id}). DESLIGADA até o grupo aprovar o contrato rc2.
    habilitar_rc2: bool = False

    log_level: str = "INFO"

    @property
    def caixa_permitida(self) -> BoundingBox | None:
        if self.area_permitida.strip().lower() == "sem-limite":
            return None
        return BoundingBox.de_texto(self.area_permitida)

    @property
    def origens_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
