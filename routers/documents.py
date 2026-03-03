from fastapi import APIRouter, Response, Query, HTTPException
from services.chroma_services import delete_documents
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.delete("/delete-document")
async def delete_document(
    botId: str = Query(...), #(...) means, this field is required
    documentId: str = Query(...)
):
    try:
        logger.info(f"Deleting document {documentId} for bot {botId}")
        delete_documents(bot_id=botId, file_id=documentId)
        logger.info(f"Document {documentId} deleted successfully")
        return Response(status_code=200)
    except ValueError as e:
        logger.error(f"Error deleting document {documentId}")
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"Error deleting document {documentId}. File not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting document {documentId}")
        raise HTTPException(status_code=500, detail=str(e))
