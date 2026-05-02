from pydantic import BaseModel, field_validator, ValidationInfo
from typing import List, Literal, Optional


class ChatMessage(BaseModel):
    """
    Mensaje individual del histórico conversacional.

    El backend reconstruye el historial desde la tabla `conversations` de
    PostgreSQL y lo manda en cada request. Esto hace al RAG stateless por
    sesión: sobrevive reinicios y multi-worker, una sola fuente de verdad.
    """
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    bot_id: str
    session_id: str
    message: str
    system_prompt: Optional[str] = None
    # Histórico reconstruido por el backend (últimos N turnos antes de
    # `message`). Default vacío → permite despliegue gradual: si el backend
    # todavía no fue actualizado y no manda este campo, el RAG funciona pero
    # el bot empieza sin memoria.
    chat_history: List[ChatMessage] = []


class ProcessRequest(BaseModel):
    bot_id: str
    file_id: str
    # Key del objeto en R2 (ej: "bots/{bot_id}/{uuid}_{filename}").
    # El backend la genera al subir el archivo a R2 y la pasa acá para
    # que el RAG descargue del mismo bucket.
    s3_key: str


class LeadData(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class LLMResponse(BaseModel):
    """
    Contrato del JSON que devuelve el LLM en JSON mode.

    Validamos shape y tipos al recibirlo para fallar rápido y consistente,
    en vez de arrastrar dicts crudos por el código y descubrir errores
    tarde (ej. al construir ChatResponse en el handler).

    Si el LLM devuelve algo que no parsea contra este schema, el caller
    cae al fallback con lead_captured=False/cede_control=False.
    """
    response: str
    lead_captured: bool = False
    lead_data: Optional[LeadData] = None
    request_detail: Optional[str] = None
    cede_control: bool = False

    @field_validator("lead_data")
    @classmethod
    def clear_lead_data_if_not_captured(
        cls, v: Optional[LeadData], info: ValidationInfo
    ) -> Optional[LeadData]:
        """
        Regla de negocio: si lead_captured=False, lead_data debe ser None.
        Limpia data espuria que el LLM pudo dejar por alucinación o por
        no respetar la consistencia del schema.
        """
        if not info.data.get("lead_captured"):
            return None
        return v


class ChatResponse(BaseModel):
    session_id: str
    response: str
    lead_captured: bool
    lead_data: Optional[LeadData] = None
    request_detail: Optional[str] = None
    cede_control: bool
