import os
import base64
import logging
from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    Docx2txtLoader,
    UnstructuredExcelLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
import fitz  # PyMuPDF
from config import settings

logger = logging.getLogger(__name__)

_VISION_PROMPT = (
    "Extract ALL text content from this image preserving its structure.\n"
    "- For menus: keep each item name together with its price and description.\n"
    "- For tables: preserve the relationship between each row's cells.\n"
    "- For catalogs or brochures: keep product names with their details.\n"
    "- For forms or lists: maintain the label-value pairing.\n"
    "Output only the extracted content in clean plain text. No commentary, no markdown."
)

_MIME_MAP = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".webp": "image/webp",
}

# Splitter para contenido extraído por vision: chunks más grandes para no
# partir item-precio-descripción en menús/catálogos.
_vision_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)

# Splitter para texto estructurado (DOCX, XLSX, TXT).
_text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=100)


# Errores transitorios sobre los que sí reintenta. NO incluye BadRequestError
# ni AuthenticationError (esos no son retryable: si fallan una vez, fallan siempre).
_RETRYABLE_OPENAI_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)


@retry(
    stop=stop_after_attempt(settings.openai_max_retries),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_RETRYABLE_OPENAI_ERRORS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _extract_page_with_vision(
    img_bytes: bytes, mime: str, source: str, page_num: int
) -> Document:
    # timeout en el cliente: corta requests colgadas en vision (típicamente
    # más caras que LLM normal por el tamaño de la imagen).
    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_vision_timeout_seconds,
    )
    b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model=settings.vision_model_name,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": _VISION_PROMPT},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime};base64,{b64}",
                    "detail": "high",
                }},
            ],
        }],
        max_tokens=4096,
    )
    text = response.choices[0].message.content or ""
    return Document(page_content=text, metadata={"source": source, "page": page_num})


def _load_pdf_with_vision(file_path: str) -> list[Document]:
    pdf = fitz.open(file_path)
    documents = []
    for page_num in range(len(pdf)):
        try:
            page = pdf[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("jpeg")
            doc = _extract_page_with_vision(img_bytes, "image/jpeg", file_path, page_num)
            documents.append(doc)
        except Exception:
            # logger.exception preserva stacktrace; usamos warning porque
            # un fallo de página no debería matar el proceso entero.
            logger.exception(
                f"Vision extraction failed on page {page_num} of {file_path}"
            )
    pdf.close()
    return documents


def _load_image_with_vision(file_path: str) -> list[Document]:
    ext = os.path.splitext(file_path)[1].lower()
    mime = _MIME_MAP.get(ext, "image/jpeg")
    with open(file_path, "rb") as f:
        img_bytes = f.read()
    doc = _extract_page_with_vision(img_bytes, mime, file_path, 0)
    return [doc]


def load_and_split(file_path: str) -> list[Document]:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        documents = _load_pdf_with_vision(file_path)
        return _vision_splitter.split_documents(documents)

    if ext in _MIME_MAP:
        documents = _load_image_with_vision(file_path)
        return _vision_splitter.split_documents(documents)

    if ext == ".docx":
        documents = Docx2txtLoader(file_path=file_path).load()
    elif ext in (".xlsx", ".xls"):
        documents = UnstructuredExcelLoader(file_path=file_path).load()
    elif ext == ".txt":
        documents = TextLoader(file_path=file_path).load()
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return _text_splitter.split_documents(documents)
