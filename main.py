# Initialize shared resource when the server stats and register the routes to fastapi knows about endpoints
from contextlib import asynccontextmanager
from fastapi import FastAPI
import chromadb
from config import settings #Instance created in config.py
import dependencies
from services.session_manager import SessionManager
from routers import chat, documents, process
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting up - initializing ChromaDB and SessionManager")
    chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_path)
    dependencies.chroma_client = chroma_client
    dependencies.session_manager = SessionManager()
    yield
    logger.info(f"Shutting down")

app = FastAPI(lifespan=lifespan)

app.include_router(chat.router)
app.include_router(process.router)
app.include_router(documents.router)