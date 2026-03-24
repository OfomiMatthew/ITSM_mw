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



# ── Layer 3: Ownership verification ────────────────────────────────────────────
async def verify_ticket_ownership(
    ticket_id: int,
    email:     str = Query(..., description="Caller's email address"),
    api_key:   str = Security(api_key_header),
    settings:  Settings = Depends(get_settings),
) -> dict:
    """
    Dependency — verifies:
      1. Valid x-api-key
      2. If caller is a REQUESTER, they can only access THEIR tickets
      3. If caller is an AGENT/MANAGER, they can access ANY ticket
    
    Returns the caller's role data.
    Raises 403 if requester tries to access someone else's ticket.
    """
    if not api_key or api_key != settings.middleware_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    
    # Get caller's role
    role_data = await _get_role(email, api_key, settings)
    
    # Agents and managers can access any ticket
    if role_data.get("is_agent") or role_data.get("is_manager"):
        return role_data
    
    # Requesters can only access their own tickets
    if role_data.get("is_requester"):
        import app.services.freshservice as fs
        try:
            ticket = await fs.get_ticket(ticket_id)
            ticket_email = ticket.get("requester_email", "").lower()
            caller_email = email.lower()
            
            if ticket_email != caller_email:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. You can only view your own tickets. This ticket belongs to someone else.",
                )
            return role_data
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not verify ticket ownership: {str(e)}",
            )
    
    # Unknown role
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not authorized to access tickets.",
    )