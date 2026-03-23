# from fastapi import HTTPException, Security, Depends, status
# from fastapi.security import APIKeyHeader
# from app.config import get_settings, Settings

# api_key_header = APIKeyHeader(name='x-api-key', auto_error=False)

# async def verify_api_key(api_key: str = Security(api_key_header), settings: Settings = Depends(get_settings)):
#     if not api_key:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail='Missing API key. Add x-api-key to your request headers',
            
#         )
#     if api_key != settings.middleware_api_key:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail='Invalid API key. Access denied',
#         )
        
#     return api_key


from fastapi import HTTPException, Security, Depends, Query, status
from fastapi.security import APIKeyHeader
from app.config import get_settings, Settings

api_key_header = APIKeyHeader(name='x-api-key', auto_error=False)


# ── Layer 1: API Key check (already working) ──────────────────────────────────
async def verify_api_key(
    api_key: str = Security(api_key_header),
    settings: Settings = Depends(get_settings),
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Add x-api-key to your request headers.",
        )
    if api_key != settings.middleware_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key. Access denied.",
        )
    return api_key


# ── Layer 2: Role-based access ────────────────────────────────────────────────
# Import here to avoid circular imports
async def _get_role(email: str, api_key: str, settings: Settings) -> dict:
    """Calls get_user_role service and returns role data."""
    import app.services.manager as ms
    role_data = await ms.get_user_role(email)
    if role_data.get("role") == "unknown":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{email} is not registered in this system. "
                "Contact your IT administrator to get access."
            ),
        )
    return role_data


async def require_registered_user(
    email:     str = Query(..., description="Caller's email address"),
    api_key:   str = Security(api_key_header),
    settings:  Settings = Depends(get_settings),
) -> dict:
    """
    Dependency — verifies:
      1. Valid x-api-key
      2. Email exists in Freshservice (requester or agent)
    Use on end-user endpoints: raise ticket, add note, etc.
    """
    if not api_key or api_key != settings.middleware_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    return await _get_role(email, api_key, settings)


async def require_agent_or_manager(
    email:    str = Query(..., description="Caller's email address"),
    api_key:  str = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Dependency — verifies:
      1. Valid x-api-key
      2. Caller is an IT Agent OR Manager in Freshservice
    Use on: team tickets, SLA breaches, assign, resolve, close, etc.
    """
    if not api_key or api_key != settings.middleware_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    role_data = await _get_role(email, api_key, settings)
    if not (role_data.get("is_agent") or role_data.get("is_manager")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access denied. {email} is not an IT agent or manager. "
                "This endpoint requires agent or manager privileges."
            ),
        )
    return role_data


async def require_manager(
    email:    str = Query(..., description="Caller's email address"),
    api_key:  str = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Dependency — verifies:
      1. Valid x-api-key
      2. Caller is a Manager in Freshservice
    Use on: analytics, weekly reports.
    """
    if not api_key or api_key != settings.middleware_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    role_data = await _get_role(email, api_key, settings)
    if not role_data.get("is_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access denied. {email} is not a manager. "
                "This endpoint requires manager privileges."
            ),
        )
    return role_data