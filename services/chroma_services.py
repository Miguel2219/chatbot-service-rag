from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from config import settings
import dependencies

def get_vector_store(bot_id):
    vector_storage = Chroma(
        collection_name=f"bot_{bot_id}",
        embedding_function=OpenAIEmbeddings(api_key=settings.openai_api_key),
        client=dependencies.chroma_client
    )
    return vector_storage

def add_documents(bot_id, chunks, file_id):
    for chunk in chunks:
        chunk.metadata["file_id"] = file_id
        chunk.metadata["bot_id"] = bot_id
    vector_storage = get_vector_store(bot_id=bot_id)
    vector_storage.add_documents(chunks)

def delete_documents(bot_id, file_id):
    vector_storage = get_vector_store(bot_id=bot_id)
    results = vector_storage.get()
    matching_ids = [
        results["ids"][i] # What i want to keep
        for i in range(len(results["ids"])) # How to iterate
        if results["metadatas"][i].get("file_id") == file_id #The filter
    ]

    if matching_ids:
        vector_storage.delete(ids=matching_ids)
   
