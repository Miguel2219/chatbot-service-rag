from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from services.chroma_services import get_vector_store
from config import settings

class ConversationalRAGEngine():
    def __init__(self, bot_id):
        self.vector_storage = get_vector_store(bot_id=bot_id)
        self.llm = ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openai_api_key
        )
        self.chat_history = []
    
    def query(self, message: str) -> str:
        retriever = self.vector_storage.as_retriever(search_kwargs={"k": 3})
        docs = retriever.invoke(message) #searcyes ChromaDb with the message as quey, return relevant chunks
        context = "\n\n".join([doc.page_content for doc in docs])
        messages = [
            SystemMessage(content=f"You are a hepful message assistant. Use this context to answer: {context}"),
            *self.chat_history, #spreads the history messages into the list
            HumanMessage(content=message)
        ]
        response = self.llm.invoke(messages) #sends the full messages List to OpenAI, returns a response object
        self.chat_history.append(HumanMessage(content=message))
        self.chat_history.append(AIMessage(content=response.content))
        
        return response.content


