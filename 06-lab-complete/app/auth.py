"""
API Key authentication (tiêu chí 6).
"""
import hmac
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Depends(_api_key_header)) -> str:
    """Dependency cho FastAPI — xác thực header X-API-Key."""
    if not settings.agent_api_key or not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    if not hmac.compare_digest(api_key, settings.agent_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
