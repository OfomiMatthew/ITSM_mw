from fastapi import HTTPException, Security, Depends, status
from fastapi.security import APIKeyHeader
from app.config import get_settings, Settings

api_key_header = APIKeyHeader(name='x-api-key', auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header), settings: Settings = Depends(get_settings)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing API key. Add x-api-key to your request headers',
            
        )
    if api_key != settings.middleware_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Invalid API key. Access denied',
        )
        
    return api_key