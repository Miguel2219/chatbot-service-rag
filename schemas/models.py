from pydantic import BaseModel

class ChatRequest(BaseModel):
    bot_id: str
    session_id: str
    message: str           

class ProcessRequest(BaseModel):
    bot_id: str
    file_id: str
    file_path: str

class ChatResponse(BaseModel):
    session_id: str
    response: str