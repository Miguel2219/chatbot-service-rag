from fastapi import APIRouter, Response, HTTPException
from schemas.models import ProcessRequest
from services.document_loader import load_and_split
from services.chroma_services import add_documents
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/process")
async def process_document(request: ProcessRequest):
    try:
        logger.info(f"Processing document {request.file_id} for bot {request.bot_id}")
        chunks = load_and_split(request.file_path)
        logger.info(f"Document loaded {request.file_id}")
        add_documents(bot_id=request.bot_id, chunks=chunks, file_id=request.file_id)
        logger.info(f"Document {request.file_id} processed successfully")
        return Response(status_code=200)
    except ValueError as e:
        logger.error(f"Error processing document: {request.file_id}")
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"Error processing document: {request.file_id}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing document: {request.file_id}")
        raise HTTPException(status_code=500, detail=str(e))

