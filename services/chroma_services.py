from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from config import settings
import dependencies


def get_vector_store(bot_id):
    vector_storage = Chroma(
        collection_name=f"bot_{bot_id}",
        embedding_function=OpenAIEmbeddings(api_key=settings.openai_api_key),
        client=dependencies.chroma_client,
    )
    return vector_storage


def add_documents(bot_id, chunks, file_id):
    for chunk in chunks:
        chunk.metadata["file_id"] = file_id
        chunk.metadata["bot_id"] = bot_id
    vector_storage = get_vector_store(bot_id=bot_id)
    vector_storage.add_documents(chunks)


def delete_documents(bot_id, file_id):
    """
    Borra todos los chunks asociados a un file_id en la colección del bot.

    Delega el filtrado al motor de Chroma usando el filtro `where`. Esto evita
    cargar toda la colección a memoria (problema de la implementación previa,
    que escaneaba todos los chunks en Python para encontrar los matches).

    Internamente: langchain_chroma.Chroma.delete(**kwargs) reenvía `where` a
    chromadb Collection.delete, que filtra server-side por índice de metadata.
    """
    vector_storage = get_vector_store(bot_id=bot_id)
    vector_storage.delete(where={"file_id": file_id})
