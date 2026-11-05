from pydantic import BaseModel, Field

from app.dominio import Categoria


class Caixa(BaseModel):
    """Caixa normalizada (0 a 1) em relação à imagem; x e y são o canto superior esquerdo."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    largura: float = Field(ge=0, le=1)
    altura: float = Field(ge=0, le=1)


class Deteccao(BaseModel):
    classe: Categoria
    confianca: float = Field(ge=0, le=1)
    caixa: Caixa
