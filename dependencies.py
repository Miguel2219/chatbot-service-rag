from typing import Optional
import chromadb
from services.session_manager import SessionManager

chroma_client: Optional[chromadb.ClientAPI] = None
session_manager: Optional[SessionManager] = None