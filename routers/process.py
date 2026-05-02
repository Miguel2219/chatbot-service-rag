from pathlib import Path
from fastapi import APIRouter, Response, HTTPException, Request
from schemas.models import ProcessRequest
from services.document_loader import load_and_split
from services.chroma_services import add_documents
from services.storage import download_from_r2, cleanup_tmp_file
from services.rate_limiter import rate_limiter, parse_rate
from config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_process_rate_limit(request: Request) -> None:
    """Rate limit por IP. Baja frecuencia esperada (uploads administrativos)."""
    ip = request.client.host if request.client else "unknown"
    max_n, window = parse_rate(settings.rate_limit_process_per_ip)
    if not rate_limiter.hit(f"process:ip:{ip}", max_n, window):
        logger.warning(f"Rate limit IP exceeded en /process: {ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit excedido: {settings.rate_limit_process_per_ip} por IP",
            headers={"Retry-After": str(int(window))},
        )


@router.post("/process")
async def process_document(request: Request, payload: ProcessRequest):
    """
    Procesa un documento: descarga de R2 → split en chunks → indexa en ChromaDB.

    El archivo vive en R2 (Cloudflare). El backend lo subió ahí y nos pasa la
    `s3_key`; descargamos a /tmp, procesamos con LangChain (que necesita un
    path de filesystem real para sus loaders), y limpiamos el tmp file en
    `finally` para no acumular basura aunque algo explote.
    """
    _check_process_rate_limit(request)

    tmp_path: Path | None = None
    try:
        # 1. Descargar de R2 a un tmp file con la extensión correcta
        #    (load_and_split despacha por extensión).
        tmp_path = download_from_r2(payload.s3_key)

        # 2. Procesar e indexar (sin cambios respecto al flujo anterior).
        chunks = load_and_split(str(tmp_path))
        add_documents(bot_id=payload.bot_id, chunks=chunks, file_id=payload.file_id)

        return Response(status_code=200)
    except HTTPException:
        # No envolver 429 en 500.
        raise
    except FileNotFoundError as e:
        logger.exception(f"S3 object not found: {payload.s3_key}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        # Errores de credenciales R2, formato de archivo no soportado, etc.
        logger.exception(f"Error processing document: {payload.file_id}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error processing document: {payload.file_id}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup garantizado del tmp file. Idempotente y nunca propaga.
        if tmp_path is not None:
            cleanup_tmp_file(tmp_path)
