"""
Tests del SessionManager (Fase 5: stateless por sesión, cachea por bot_id).

- get_engine devuelve la misma instancia para el mismo bot_id (cache).
- Bots distintos producen engines distintos.
- get_or_create_session sigue funcionando como compat (delega a get_engine).
- start_cleanup / stop_cleanup son no-ops.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def patched_engine():
    """Mockea ConversationalRAGEngine (no toca ChromaDB ni OpenAI)."""
    with patch("services.session_manager.ConversationalRAGEngine") as mock_cls:
        mock_cls.side_effect = lambda bot_id: MagicMock(name=f"engine_for_{bot_id}")
        yield mock_cls


class TestEngineCaching:
    def test_same_bot_returns_same_engine(self, patched_engine):
        from services.session_manager import SessionManager
        mgr = SessionManager()

        e1 = mgr.get_engine("bot-A")
        e2 = mgr.get_engine("bot-A")

        assert e1 is e2  # mismo engine cacheado
        assert patched_engine.call_count == 1  # solo se construyó una vez

    def test_different_bots_return_different_engines(self, patched_engine):
        from services.session_manager import SessionManager
        mgr = SessionManager()

        e_a = mgr.get_engine("bot-A")
        e_b = mgr.get_engine("bot-B")

        assert e_a is not e_b
        assert patched_engine.call_count == 2

    def test_session_id_is_ignored_in_compat_method(self, patched_engine):
        """
        get_or_create_session(session_id, bot_id) es compat con la API
        previa. Hoy el session_id se ignora — el cache es por bot_id.
        """
        from services.session_manager import SessionManager
        mgr = SessionManager()

        e1 = mgr.get_or_create_session("session-X", "bot-A")
        e2 = mgr.get_or_create_session("session-Y", "bot-A")  # otra sesión, mismo bot

        assert e1 is e2  # son el mismo engine porque el bot es el mismo
        assert patched_engine.call_count == 1


class TestLifecycleNoOps:
    @pytest.mark.asyncio
    async def test_start_and_stop_cleanup_are_noops(self, patched_engine):
        from services.session_manager import SessionManager
        mgr = SessionManager()
        # Solo verificamos que no tiren excepción — son compat con main.lifespan.
        mgr.start_cleanup()
        await mgr.stop_cleanup()
