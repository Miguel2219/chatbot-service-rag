import dependencies
from fastapi import APIRouter, HTTPException
from schemas.models import ChatRequest,ChatResponse, LeadData
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def conversation(request: ChatRequest):
    try:
        logger.info(f"Try getting or create the session: {request.session_id}")
        engine = dependencies.session_manager.get_or_create_session(
        session_id=request.session_id,
        bot_id=request.bot_id
        )
        logger.info(f"session {request.session_id} created successfully")
        response = engine.query(message=request.message)
        lead_info = response.get("lead_data")
        lead_data = LeadData(**lead_info) if lead_info else None
        return ChatResponse(
            session_id=request.session_id,
            response=response.get("response"),
            lead_captured=response.get("lead_captured"),
            lead_data=lead_data
        )
    except ValueError as e:
        logger.error(f"Error getting conversation")
        raise HTTPException(status_code=400, detail=str(e))
    except TypeError as e:
        logger.error(f"Error getting conversations. Type error")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting conversation")
        raise HTTPException(status_code=500, detail=str(e))
    

