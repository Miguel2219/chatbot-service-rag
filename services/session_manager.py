"""
Cache de ConversationalRAGEngine por bot_id.

Antes (Fase 1): este módulo guardaba un engine por session_id con TTL+LRU
porque cada sesión tenía su propio chat_history en memoria.

Ahora (Fase 5): el engine es stateless, así que solo cacheamos la conexión
al vector store por bot_id. La cantidad de bots en un tenant SaaS típico
es chica (decenas a centenas), no hay riesgo de leak. Por eso eliminamos
la complejidad de TTL/LRU.

Los métodos start_cleanup/stop_cleanup quedan como no-op por compatibilidad
con el lifespan en main.py (no hace falta cambiar nada en startup).
"""
import logging
from typing import Dict
from services.rag_service import ConversationalRAGEngine

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self) -> None:
        self._engines: Dict[str, ConversationalRAGEngine] = {}

    def get_engine(self, bot_id: str) -> ConversationalRAGEngine:
        """
        Devuelve el engine cacheado para `bot_id`, creándolo si es la
        primera vez. El engine no tiene estado por sesión — solo cachea
        la conexión al vector store del bot.
        """
        if bot_id not in self._engines:
            self._engines[bot_id] = ConversationalRAGEngine(bot_id=bot_id)
            logger.info(f"[SessionManager] engine creado para bot {bot_id}")
        return self._engines[bot_id]

    # Compat con `routers/chat.py` previo (Fase 1) y con tests que llamaban
    # get_or_create_session(session_id, bot_id). Hoy ignoramos session_id.
    def get_or_create_session(
        self, session_id: str, bot_id: str
    ) -> ConversationalRAGEngine:
        return self.get_engine(bot_id)

    def start_cleanup(self) -> None:
        """No-op. Antes arrancaba la task background de TTL — ya no aplica."""
        pass

    async def stop_cleanup(self) -> None:
        """No-op. Compat con el lifespan de main.py."""
        pass
