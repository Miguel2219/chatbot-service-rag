from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env')

    openai_api_key: str
    internal_api_key: str
    model_name: str = 'gpt-4.1-mini'
    vision_model_name: str = 'gpt-4o'

    # Cap de historial conversacional por sesión: 1 turno = HumanMessage + AIMessage.
    # Evita que el array crezca indefinidamente y dispare tokens/RAM.
    chat_history_max_turns: int = 20

    # TTL/LRU del SessionManager.
    # TTL alto (24h) para soportar conversaciones de WhatsApp con pausas largas.
    # Si el cliente vuelve al día siguiente, el bot todavía recuerda el contexto.
    # Limitación conocida: si el proceso se reinicia, las sesiones se pierden
    # (deuda agendada en Fase 5 — RAG stateless con history desde backend).
    session_ttl_seconds: int = 86400
    session_max_count: int = 2000
    session_cleanup_interval_seconds: int = 300

    # Timeouts y retries para llamadas a OpenAI.
    # LLM: chat normal. Vision: más alto porque las imágenes tardan más.
    # max_retries aplica tanto a langchain-openai (built-in) como al cliente
    # directo de OpenAI usado en vision (vía tenacity).
    openai_llm_timeout_seconds: float = 30.0
    openai_vision_timeout_seconds: float = 45.0
    openai_max_retries: int = 3

    # ── Object Storage (Cloudflare R2 / S3-compatible) ─────────────────────
    # El backend sube los archivos a este bucket y le pasa la s3_key al RAG
    # vía /process. El RAG descarga el archivo a /tmp con boto3, lo procesa,
    # y borra el tmp file. Backend y RAG NO necesitan filesystem compartido.
    #
    # Mismas credenciales que el backend, pero idealmente con un token
    # separado de "Object Read" (sin write/delete) para principio de menor
    # privilegio. El RAG nunca debería escribir o borrar del bucket.
    r2_endpoint: str          # https://<account_id>.r2.cloudflarestorage.com
    r2_bucket: str            # nombre del bucket (debe coincidir con el del backend)
    r2_access_key_id: str     # secret
    r2_secret_access_key: str # secret
    r2_region: str = 'auto'   # R2 usa "auto" por convención

    # Rate limiting (slowapi).
    # /chat: por IP del caller (típicamente el backend, pero protege contra
    # bursts si alguien obtiene la INTERNAL_API_KEY) y por bot_id (evita que
    # un único bot mal configurado queme la cuota de OpenAI).
    # /process: solo por IP, baja frecuencia esperada (uploads administrativos).
    # Formato: "<n>/<unidad>" donde unidad ∈ {second, minute, hour, day}.
    rate_limit_chat_per_ip: str = '60/minute'
    rate_limit_chat_per_bot: str = '30/minute'
    rate_limit_process_per_ip: str = '20/minute'
    
    # Chroma corre como servicio separado (HTTP) en lugar de embebido.
    # El RAG es un cliente delgado que se conecta vía HTTP, así múltiples
    # workers del RAG no se pelean por el mismo SQLite. La persistencia
    # vive en el server (Railway Volume montado en /chroma_data).
    chroma_host: str
    chroma_port: int = 8000


settings = Settings()
