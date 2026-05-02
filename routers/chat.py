import dependencies
from fastapi import APIRouter, HTTPException, Request
from schemas.models import ChatRequest, ChatResponse, LLMResponse
from services.rate_limiter import rate_limiter, parse_rate
from config import settings
import logging


logger = logging.getLogger(__name__)
router = APIRouter()


def _check_chat_rate_limits(request: Request, bot_id: str) -> None:
    """
    Aplica dos límites independientes para /chat:
    - por IP del caller (defensa anti-burst si se filtra INTERNAL_API_KEY).
    - por bot_id (evita que un único bot queme la cuota de OpenAI).

    Si alguno se supera, lanza HTTPException 429 con Retry-After.
    """
    ip = request.client.host if request.client else "unknown"
    ip_max, ip_window = parse_rate(settings.rate_limit_chat_per_ip)
    bot_max, bot_window = parse_rate(settings.rate_limit_chat_per_bot)

    if not rate_limiter.hit(f"chat:ip:{ip}", ip_max, ip_window):
        logger.warning(f"Rate limit IP exceeded: {ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit excedido: {settings.rate_limit_chat_per_ip} por IP",
            headers={"Retry-After": str(int(ip_window))},
        )
    if not rate_limiter.hit(f"chat:bot:{bot_id}", bot_max, bot_window):
        logger.warning(f"Rate limit bot exceeded: {bot_id}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit excedido: {settings.rate_limit_chat_per_bot} por bot",
            headers={"Retry-After": str(int(bot_window))},
        )


@router.post("/chat", response_model=ChatResponse)
async def conversation(request: Request, payload: ChatRequest):
    # Rate limit ANTES de tocar el LLM o crear sesiones — fail fast.
    _check_chat_rate_limits(request, bot_id=payload.bot_id)

    try:
        # Cacheamos el engine por bot_id (stateless por sesión).
        engine = dependencies.session_manager.get_engine(bot_id=payload.bot_id)

        # El history viene reconstruido por el backend desde Postgres.
        # Si no se manda (deploy gradual), llega como [] y el bot empieza
        # sin memoria — fallback seguro pero sin contexto.
        llm_resp: LLMResponse = engine.query(
            message=payload.message,
            system_prompt=payload.system_prompt,
            chat_history=payload.chat_history,
        )

        return ChatResponse(
            session_id=payload.session_id,
            response=llm_resp.response,
            lead_captured=llm_resp.lead_captured,
            lead_data=llm_resp.lead_data,
            request_detail=llm_resp.request_detail,
            cede_control=llm_resp.cede_control,
        )
    except HTTPException:
        # Re-raise sin envolver para no convertir 429 en 500.
        raise
    except ValueError as e:
        logger.exception(
            f"Error getting conversation. session_id={payload.session_id}"
        )
        raise HTTPException(status_code=400, detail=str(e))
    except TypeError as e:
        logger.exception(
            f"Error getting conversation (type error). session_id={payload.session_id}"
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(
            f"Error getting conversation. session_id={payload.session_id}"
        )
        raise HTTPException(status_code=500, detail=str(e))
