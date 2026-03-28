from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from services.chroma_services import get_vector_store
from config import settings
import logging
import json

logger = logging.getLogger()

class ConversationalRAGEngine():
    def __init__(self, bot_id):
        self.vector_storage = get_vector_store(bot_id=bot_id)
        self.llm = ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openai_api_key
        )
        self.chat_history = []
    
    def query(self, message: str) -> str:
        retriever = self.vector_storage.similarity_search_with_score(query=message, k=5)
        logger.info(f'retriever: {retriever}')
        umbral = 0.7
        docs = []
        for doc, score in retriever:
            if score <= umbral:
                docs.append(doc)
        if not docs:
            context = 'No information is available in the context.'
        else:
            context = "\n\n".join([doc.page_content for doc in docs])
        logger.info(f"Este es el contexto: {context}")
        system_prompt = f"""
You are a customer service assistant. Your job is to answer questions 
based ONLY on the context provided below.

BEHAVIOR RULES:

1. If the context contains the answer:
   - Respond clearly and directly using only information from the context.
   - You MAY perform calculations (totals, subtotals, comparisons) 
     using values that exist in the context.
   - NEVER invent or infer exact data (numbers, dates, prices, periods) 
     that is not explicitly in the context.

2. If the context does NOT contain enough information to answer:
   - Do NOT say "that information doesn't exist".
   - Say that an advisor can help with that.
   - Ask for the user's name and phone number or email in a friendly way.
   - Example: "Para ayudarte con eso necesitaré algunos datos, 
     ¿me puedes compartir tu nombre y teléfono o correo? 
     Un asesor te contactará muy pronto."

3. If the user is requesting an ACTION (reservation, purchase, complaint, 
   cancellation, or any task the bot cannot execute):
   - Do NOT attempt to execute the action.
   - Inform the user that an advisor will handle it.
   - Ask for name and contact info the same way as rule 2.

4. Once the user provides their contact info:
   - Confirm their data back to them.
   - Thank them warmly.
   - Reassure them that an advisor will reach out soon.

5. If no contact information is available in the context, tell the user 
   to reach out through the company's official channels.

6. Always respond with a valid JSON object with these fields:
    - "response": your message to the user (string)
    - "lead_captured": true is the user just provided their contact info in this message, false otherwhise (boolean)
    - "lead_data": object with "name", "emaiL" and "phone" if lead_captured is true, null otherwise. Use null for email or phone if not provided
    - Respond ONLY with the JSON object. No extra text before or after.

IMPORTANT: Never make up information. If you are not sure, always 
prefer to escalate to a human advisor.

Context:
{context}
"""
        messages = [
            SystemMessage(content=system_prompt),
            *self.chat_history, #spreads the history messages into the list
            HumanMessage(content=message)
        ]
        response = self.llm.invoke(messages) #sends the full messages List to OpenAI, returns a response object
        raw = response.content
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {
                "response": raw,
                "lead_captured": False,
                "lead_data": None
            }
        self.chat_history.append(HumanMessage(content=message))
        self.chat_history.append(AIMessage(content=parsed["response"]))

        logger.info(f"Este es el parsed: {parsed}")
        return parsed


