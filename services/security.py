from fastapi import Header, HTTPException
from config import settings

async def verify_internal_key(x_internal_key: str = Header(..., alias="x-internal-key")):
    if x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")