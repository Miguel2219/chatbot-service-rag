"""
Tests del cap defensivo de chat_history en ConversationalRAGEngine.query().

Fase 5: el history viene en el request (no se mantiene en self.chat_history).
El engine aplica un cap defensivo: si el backend manda más de N×2 mensajes,
el RAG trunca a los últimos N×2 antes de construir el prompt — protege
contra requests con history excesivamente largo.
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from schemas.models import ChatMessage
from config import settings


class _FakeLLMResponse:
    def __init__(self, text):
        self.content = text
        self.response_metadata = {"token_usage": {}}


@pytest.fixture
def engine(monkeypatch):
    """
    Construye un ConversationalRAGEngine con vector_store y LLM mockeados.
    El LLM responde siempre con un JSON válido de respuesta neutral.
    """
    monkeypatch.setattr(settings, "chat_history_max_turns", 3)  # cap chico

    fake_vs = MagicMock()
    fake_vs.similarity_search_with_score.return_value = []

    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _FakeLLMResponse(
        '{"response": "respuesta", "lead_captured": false, "cede_control": false}'
    )

    with patch("services.rag_service.get_vector_store", return_value=fake_vs), \
         patch("services.rag_service.ChatOpenAI", return_value=fake_llm):
        from services.rag_service import ConversationalRAGEngine
        eng = ConversationalRAGEngine(bot_id="test-bot")
        # El engine ya no mantiene history. Devolvemos también el mock del
        # LLM para que los tests inspeccionen los messages que se le mandaron.
        yield eng, fake_llm


def _extract_history_passed_to_llm(fake_llm) -> list:
    """
    Saca los mensajes que el engine le pasó al LLM, excluyendo el SystemMessage
    inicial y el HumanMessage final (que es el `message` actual + RAG context).
    Lo que queda es el chat_history aplicado al prompt.
    """
    args, kwargs = fake_llm.invoke.call_args
    messages = args[0] if args else kwargs.get("input")
    # primer msg = SystemMessage (reglas), último = HumanMessage (mensaje + ctx)
    return messages[1:-1]


class TestNoStatePersisted:
    def test_engine_does_not_persist_history_between_calls(self, engine):
        eng, fake_llm = engine
        # Primer query con history A
        eng.query(
            "msg1",
            chat_history=[
                ChatMessage(role="user", content="hola"),
                ChatMessage(role="assistant", content="hola!"),
            ],
        )
        # Segundo query SIN history
        eng.query("msg2", chat_history=None)
        # El segundo prompt no debería tener nada del history del primero
        history_in_2nd = _extract_history_passed_to_llm(fake_llm)
        assert len(history_in_2nd) == 0


class TestHistoryFromRequest:
    def test_history_from_request_passed_to_llm(self, engine):
        eng, fake_llm = engine
        eng.query(
            "msg",
            chat_history=[
                ChatMessage(role="user", content="hola"),
                ChatMessage(role="assistant", content="qué tal"),
            ],
        )
        history = _extract_history_passed_to_llm(fake_llm)
        assert len(history) == 2
        assert isinstance(history[0], HumanMessage)
        assert history[0].content == "hola"
        assert isinstance(history[1], AIMessage)
        assert history[1].content == "qué tal"

    def test_empty_history_works(self, engine):
        eng, fake_llm = engine
        eng.query("msg", chat_history=[])
        history = _extract_history_passed_to_llm(fake_llm)
        assert history == []

    def test_none_history_treated_as_empty(self, engine):
        eng, fake_llm = engine
        eng.query("msg", chat_history=None)
        history = _extract_history_passed_to_llm(fake_llm)
        assert history == []


class TestDefensiveCap:
    def test_excess_history_truncated_to_last_n(self, engine):
        """
        Cap defensivo: si el backend manda más de N×2 mensajes, el RAG
        trunca a los últimos N×2 (con N=chat_history_max_turns).
        """
        eng, fake_llm = engine
        # Cap settings.chat_history_max_turns = 3 → max 6 mensajes.
        # Mando 10 turnos (20 mensajes).
        long_history = []
        for i in range(10):
            long_history.append(ChatMessage(role="user", content=f"u{i}"))
            long_history.append(ChatMessage(role="assistant", content=f"a{i}"))
        # 20 mensajes en el request

        eng.query("msg", chat_history=long_history)
        history = _extract_history_passed_to_llm(fake_llm)

        # El engine debe haber dejado solo los últimos 6.
        assert len(history) == 6
        # El último HumanMessage del history debe ser u9 (no u4).
        last_human = [m for m in history if isinstance(m, HumanMessage)][-1]
        assert last_human.content == "u9"
        # El primer mensaje debe ser u7 (turnos 7,8,9 = msg 14..19 → 6 mensajes).
        assert history[0].content == "u7"
