# Initialize shared resource when the server starts and register the routes
# so fastapi knows about endpoints.
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
import chromadb
from config import settings  # Instance created in config.py
import dependencies
from services.session_manager import SessionManager
from routers import chat, documents, process
from services.security import verify_internal_key
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    chroma_client = chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
    )
    dependencies.chroma_client = chroma_client
    dependencies.session_manager = SessionManager()
    # Arranca la task background que purga sesiones expiradas (TTL).
    dependencies.session_manager.start_cleanup()
    yield
    # Cierre limpio: cancela la task de cleanup al apagar el servidor.
    await dependencies.session_manager.stop_cleanup()


app = FastAPI(lifespan=lifespan)

app.include_router(chat.router, dependencies=[Depends(verify_internal_key)])
app.include_router(process.router, dependencies=[Depends(verify_internal_key)])
app.include_router(documents.router, dependencies=[Depends(verify_internal_key)])
