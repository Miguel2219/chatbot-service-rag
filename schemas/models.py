from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    bot_id: str
    session_id: str
    message: str           

class ProcessRequest(BaseModel):
    bot_id: str
    file_id: str
    file_path: str

class LeadData(BaseModel):
    name: str
    email: Optional[str]
    phone: Optional[str]

class ChatResponse(BaseModel):
    session_id: str
    response: str
    lead_captured: bool
    lead_data: Optional[LeadData] = None

