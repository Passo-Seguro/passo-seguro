from pydantic import BaseModel, Field, field_validator


class PerguntaAssistente(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)

    @field_validator("pergunta")
    @classmethod
    def _nao_so_espacos(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("não pode ser vazia")
        return valor


class FonteCitada(BaseModel):
    titulo: str
    url: str | None = None


class RespostaAssistente(BaseModel):
    resposta: str
    fontes: list[FonteCitada]
    confianca: float = Field(ge=0, le=1)
    recusou: bool
