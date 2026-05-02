"""
Cliente de object storage (Cloudflare R2 / S3-compatible).

Reemplaza el filesystem compartido entre backend y RAG. El backend sube los
archivos a R2 y le pasa al RAG la `s3_key` (ej: `bots/{botId}/{uuid}_{name}`);
el RAG descarga ese objeto a un tmp file, lo procesa, y limpia el tmp.

Sin esto, ambos servicios necesitarían montar el mismo volumen físico
— imposible en Railway, donde cada servicio corre en su propio contenedor
aislado.
"""

import logging
import os
import tempfile
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from config import settings

logger = logging.getLogger(__name__)


# Cliente S3 inicializado una sola vez al importar el módulo.
# boto3 maneja un connection pool internamente y reusa conexiones.
_s3_client = boto3.client(
    "s3",
    endpoint_url=settings.r2_endpoint,
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
    region_name=settings.r2_region,
    # Path-style requerido por R2: https://endpoint/bucket/key
    # (no virtual-host style https://bucket.endpoint/key).
    config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
)


def download_from_r2(s3_key: str) -> Path:
    """
    Descarga un objeto de R2 a un archivo temporal y devuelve su Path.

    El caller es responsable de borrar el archivo después de usarlo
    (típicamente con try/finally en el endpoint que llama).

    Preserva la extensión del archivo original (deducida del s3_key) para
    que los loaders de LangChain (que dispatchean por extensión) la
    detecten correctamente. Sin esto, todo terminaría en un .tmp y se
    rompería el dispatch en `document_loader.load_and_split`.

    Lanza:
        FileNotFoundError: si el objeto no existe en el bucket.
        ValueError: si hay error de credenciales o configuración.
        RuntimeError: para errores inesperados de R2.
    """
    # Preservar extensión del original (ej: ".pdf", ".docx", ".xlsx").
    # Si no la tiene, queda string vacío y NamedTemporaryFile genera
    # un nombre genérico — el loader dispatch fallará después con un
    # mensaje claro ("Unsupported file type").
    suffix = Path(s3_key).suffix

    # delete=False: queremos cerrar el handle pero NO borrar el archivo.
    # El caller decide cuándo borrarlo (después de procesarlo).
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        _s3_client.download_file(
            Bucket=settings.r2_bucket,
            Key=s3_key,
            Filename=str(tmp_path),
        )
        logger.info(f"Downloaded s3://{settings.r2_bucket}/{s3_key} -> {tmp_path}")
        return tmp_path
    except ClientError as e:
        # Cleanup del tmp si la descarga falla (no queremos leak de archivos).
        tmp_path.unlink(missing_ok=True)
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code in ("404", "NoSuchKey"):
            raise FileNotFoundError(
                f"Object not found in R2: {s3_key}"
            ) from e
        if error_code in ("403", "InvalidAccessKeyId", "SignatureDoesNotMatch"):
            raise ValueError(
                f"R2 credentials/permissions error: {error_code}"
            ) from e
        raise RuntimeError(f"R2 download failed: {error_code}") from e
    except BotoCoreError as e:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"R2 client error: {e}") from e


def cleanup_tmp_file(path: Path) -> None:
    """
    Borra el archivo temporal generado por `download_from_r2`. Idempotente.

    Pensado para ir en un `finally` del endpoint que procesa el documento.
    Loguea pero no propaga errores: si el cleanup falla, el sistema
    operativo eventualmente recoge /tmp en cualquier caso.
    """
    try:
        if path and path.exists():
            os.unlink(path)
            logger.debug(f"Cleaned up tmp file: {path}")
    except OSError as e:
        logger.warning(f"Failed to cleanup tmp file {path}: {e}")
