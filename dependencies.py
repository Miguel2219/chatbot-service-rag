"""
Singletons globales del proceso. Se inicializan en main.lifespan() y
se reutilizan por todos los routers/services.

Usamos type hints como string (PEP 563-style) para evitar un ciclo:
   dependencies → SessionManager → ConversationalRAGEngine → chroma_services → dependencies
El string annotation permite declarar el tipo sin importar el módulo.
"""
from typing import Optional, TYPE_CHECKING
import chromadb

if TYPE_CHECKING:
    # Solo para type checkers (mypy, IDE). En runtime no se ejecuta.
    from services.session_manager import SessionManager

chroma_client: Optional[chromadb.ClientAPI] = None
session_manager: "Optional[SessionManager]" = None
