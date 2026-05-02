from fastapi import APIRouter, Response, Query, HTTPException
from services.chroma_services import delete_documents
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.delete("/delete-document")
async def delete_document(
    botId: str = Query(...),  # (...) means: campo requerido
    documentId: str = Query(...),
):
    try:
        delete_documents(bot_id=botId, file_id=documentId)
        return Response(status_code=200)
    except ValueError as e:
        # logger.exception preserva stacktrace en el log → debugging real.
        logger.exception(f"Error deleting document {documentId}")
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.exception(f"Error deleting document {documentId}. File not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error deleting document {documentId}")
        raise HTTPException(status_code=500, detail=str(e))
