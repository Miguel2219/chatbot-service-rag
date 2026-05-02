from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from pydantic import ValidationError
from services.chroma_services import get_vector_store
from schemas.models import LLMResponse, ChatMessage
from prompts.default_rules import DEFAULT_RULES_WITHOUT_CONTEXT
from config import settings
from typing import List, Optional
import logging
import re

logger = logging.getLogger(__name__)


def build_stable_system_prompt(system_prompt: Optional[str] = None) -> str:
    """
    Parte ESTABLE del prompt — cacheable por OpenAI.
    Contiene las reglas por default + el system_prompt custom del bot (si existe).
    NO contiene el RAG context (eso va en el user message para no romper el cache).

    Orden importante: reglas default PRIMERO, system_prompt custom DESPUÉS.
    Esto permite que OpenAI cachee las reglas entre TODOS los bots
    y solo añada la parte del bot específico por encima.
    """
    rules = DEFAULT_RULES_WITHOUT_CONTEXT
    if system_prompt:
        return rules + "\n\n━━━ BOT-SPECIFIC INSTRUCTIONS ━━━\n\n" + system_prompt
    return rules


def build_user_message_with_context(
    user_message: str, context: Optional[str] = None
) -> str:
    """
    Parte DINÁMICA — no cacheable.
    Incluye el RAG context (que cambia por request) + el mensaje del usuario.
    Va como HumanMessage en lugar de SystemMessage.
    """
    context_text = context or "No information is available in the context."
    return f"""Context from knowledge base:
{context_text}

User question: {user_message}"""


def _to_lc_message(msg: ChatMessage) -> BaseMessage:
    """Convierte un ChatMessage del schema a un BaseMessage de langchain."""
    if msg.role == "user":
        return HumanMessage(content=msg.content)
    return AIMessage(content=msg.content)


class ConversationalRAGEngine:
    """
    Motor RAG stateless por sesión.

    NO mantiene chat_history en memoria. El history viene reconstruido por
    el backend en cada request (desde la tabla `conversations` de Postgres).
    Esto permite que el RAG sobreviva a reinicios y a multi-worker, y elimina
    la duplicación de estado entre RAG y backend.

    El engine se cachea por bot_id (no por session_id) en SessionManager,
    porque el único estado que vale la pena mantener es la conexión al
    vector store, que es por bot.
    """

    def __init__(self, bot_id):
        self.vector_storage = get_vector_store(bot_id=bot_id)
        # timeout: corta la request si OpenAI no responde a tiempo.
        # max_retries: langchain-openai aplica retry built-in con backoff
        # exponencial sobre errores transitorios (5xx, rate-limit, conexión).
        # No reintenta sobre errores de validación o auth (correcto).
        self.llm = ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openai_api_key,
            model_kwargs={"response_format": {"type": "json_object"}},
            timeout=settings.openai_llm_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )

    def query(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[ChatMessage]] = None,
    ) -> LLMResponse:
        history = chat_history or []

        # Cap defensivo: si el backend manda más turnos de los configurados,
        # truncamos a los últimos N×2 mensajes para no explotar tokens.
        # Aplica sobre el history del request, no sobre estado persistente.
        max_messages = settings.chat_history_max_turns * 2
        if len(history) > max_messages:
            history = history[-max_messages:]

        retriever = self.vector_storage.similarity_search_with_score(query=message, k=5)
        umbral = 0.7
        docs = []
        for doc, score in retriever:
            if score <= umbral:
                docs.append(doc)
        if not docs:
            context = "No information is available in the context."
        else:
            context = "\n\n".join([doc.page_content for doc in docs])

        stable_system = build_stable_system_prompt(system_prompt)
        user_msg_with_context = build_user_message_with_context(message, context)

        messages = [
            SystemMessage(content=stable_system),
            *[_to_lc_message(m) for m in history],
            HumanMessage(content=user_msg_with_context),
        ]
        response = self.llm.invoke(messages)

        usage_metadata = (
            response.response_metadata.get("token_usage", {})
            if hasattr(response, "response_metadata")
            else {}
        )
        prompt_tokens = usage_metadata.get("prompt_tokens", 0)
        completion_tokens = usage_metadata.get("completion_tokens", 0)
        prompt_details = usage_metadata.get("prompt_tokens_details", {})
        cached_tokens = (
            prompt_details.get("cached_tokens", 0)
            if isinstance(prompt_details, dict)
            else 0
        )

        cache_hit_rate = (
            (cached_tokens / prompt_tokens * 100) if prompt_tokens > 0 else 0
        )
        logger.info(
            f"[LLM] model={settings.model_name} "
            f"prompt_tokens={prompt_tokens} "
            f"cached_tokens={cached_tokens} "
            f"completion_tokens={completion_tokens} "
            f"cache_hit={cache_hit_rate:.1f}%"
        )

        raw = response.content.strip()
        # Strip markdown fences que algunos modelos agregan a pesar de la instrucción.
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        # Validación contra el schema Pydantic LLMResponse.
        # model_validate_json combina json.loads + validación de tipos en
        # una sola pasada. Si el LLM devuelve JSON malformado o un shape
        # inválido (tipos incorrectos, campos requeridos faltantes), caemos
        # al fallback seguro: respuesta texto plano + flags en false.
        try:
            parsed = LLMResponse.model_validate_json(raw)
        except (ValueError, ValidationError) as e:
            logger.warning(
                f"LLM returned invalid response, using fallback: {e}. raw={raw!r}"
            )
            parsed = LLMResponse(
                response=raw,
                lead_captured=False,
                cede_control=False,
            )

        logger.info(f"Parsed response: {parsed.model_dump()}")
        return parsed
