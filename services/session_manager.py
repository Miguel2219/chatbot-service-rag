from services.rag_service import ConversationalRAGEngine

class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_or_create_session(self, session_id: str, bot_id: str) -> ConversationalRAGEngine:
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationalRAGEngine(bot_id=bot_id)
        return self.sessions[session_id]