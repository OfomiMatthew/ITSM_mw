"""
Freshservice Service Layer
──────────────────────────
All communication with the Freshservice REST API lives here.
No route file should import httpx or know about Freshservice directly.
If Freshservice changes their API, this is the ONLY file you update.
"""

import httpx
from app.config import get_settings
from typing import Optional


# ── Label maps ─────────────────────────────────────────────────────────────────
PRIORITY_MAP = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Urgent",
}

STATUS_MAP = {
    2: "Open",
    3: "Pending",
    4: "Resolved",
    5: "Closed",
}


# ── HTTP client factory ────────────────────────────────────────────────────────
def _get_client() -> httpx.AsyncClient:
    """
    Creates a configured async HTTP client for Freshservice.
    Uses Basic Auth: API key as username, 'X' as password (Freshservice standard).
    """
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.freshservice_base_url,
        auth=(settings.freshservice_api_key, "X"),
        headers={"Content-Type": "application/json"},
        timeout=15.0,
    )


# ── Internal helper ────────────────────────────────────────────────────────────
def _normalise_ticket(raw: dict) -> dict:
    """
    Maps raw Freshservice ticket fields to our clean internal shape.
    This is what gets returned to Power Automate / Copilot Studio.
    """
    return {
        "ticket_id":      raw.get("id"),
        "subject":        raw.get("subject", ""),
        "status":         raw.get("status", 2),
        "status_label":   STATUS_MAP.get(raw.get("status", 2), "Unknown"),
        "priority":       raw.get("priority", 2),
        "priority_label": PRIORITY_MAP.get(raw.get("priority", 2), "Unknown"),
        "created_at":     raw.get("created_at", ""),
        "due_by":         raw.get("due_by"),
        "requester_id":   raw.get("requester_id"),
    }


# ── CREATE TICKET ──────────────────────────────────────────────────────────────
async def create_ticket(data: dict) -> dict:
    """
    Creates a new incident ticket in Freshservice.

    Args:
        data: Validated dict from CreateTicketRequest

    Returns:
        Normalised ticket dict
    
    Raises:
        httpx.HTTPStatusError on non-2xx from Freshservice
    """
    payload = {
        "subject":     data["subject"],
        "description": data["description"],
        "email":       data["email"],
        "priority":    data.get("priority", 2),
        "status":      2,              # Always open on creation
        "type":        "Incident",
    }

    # Only add optional fields if they were provided
    if data.get("category"):
        payload["category"] = data["category"]
    if data.get("urgency"):
        payload["urgency"] = data["urgency"]

    async with _get_client() as client:
        response = await client.post("/tickets", json=payload)
        response.raise_for_status()
        ticket = response.json().get("ticket", {})
        return _normalise_ticket(ticket)


# ── GET TICKET BY ID ───────────────────────────────────────────────────────────
async def get_ticket(ticket_id: int) -> dict:
    """
    Fetches a single ticket by its ID.

    Args:
        ticket_id: The Freshservice ticket number (e.g. 3)

    Returns:
        Normalised ticket dict

    Raises:
        httpx.HTTPStatusError — 404 if ticket not found
    """
    async with _get_client() as client:
        response = await client.get(f"/tickets/{ticket_id}")
        response.raise_for_status()
        ticket = response.json().get("ticket", {})
        return _normalise_ticket(ticket)


# ── GET TICKETS BY EMAIL ───────────────────────────────────────────────────────

async def get_tickets_by_email(email: str, status: Optional[int] = 2) -> list:
    """
    Step 1: Look up the requester ID from their email address.
    Step 2: Use that ID to filter tickets via the filter endpoint.
    This two-step approach is the correct way per Freshservice API v2 docs.
    """
    async with _get_client() as client:

        # ── STEP 1: Get requester ID from email ───────────────────
        requester_resp = await client.get(
            "/requesters",
            params={"email": email}
        )
        requester_resp.raise_for_status()

        requesters = requester_resp.json().get("requesters", [])
        if not requesters:
            # No requester found with that email — return empty list
            return []

        requester_id = requesters[0]["id"]

        # ── STEP 2: Filter tickets by requester_id ────────────────
        # Build the query string — status is optional
        if status is not None:
            query = f'"requester_id:{requester_id} AND status:{status}"'
        else:
            query = f'"requester_id:{requester_id}"'

        tickets_resp = await client.get(
            "/tickets/filter",
            params={
                "query":      query,
                "per_page":   10,
                "order_type": "desc",
            }
        )
        tickets_resp.raise_for_status()

        tickets = tickets_resp.json().get("tickets", [])
        return [_normalise_ticket(t) for t in tickets]
      
# async def get_tickets_by_email(email: str, status: Optional[int] = 2) -> list:
#     """
#     Fetches all tickets for a given requester email address.
#     Defaults to open tickets (status=2) only.

#     Args:
#         email:  Requester email
#         status: Freshservice status code (2=Open, 3=Pending, 4=Resolved, 5=Closed)
#                 Pass None to get tickets of all statuses

#     Returns:
#         List of normalised ticket dicts
#     """
#     params = {
#         "email":      email,
#         "per_page":   10,
#         "order_type": "desc",
#         "filter": "all",
#     }
#     if status is not None:
#         params["status"] = status

#     async with _get_client() as client:
#         response = await client.get("/tickets", params=params)
#         response.raise_for_status()
#         tickets = response.json().get("tickets", [])
#         return [_normalise_ticket(t) for t in tickets]


# ── UPDATE TICKET ──────────────────────────────────────────────────────────────
async def update_ticket(ticket_id: int, updates: dict) -> dict:
    """
    Updates specific fields on an existing ticket.
    Only fields present in the updates dict are changed.

    Args:
        ticket_id: The ticket to update
        updates:   Dict of fields to change e.g. {"priority": 3, "status": 3}

    Returns:
        Normalised updated ticket dict
    """
    async with _get_client() as client:
        response = await client.put(f"/tickets/{ticket_id}", json=updates)
        response.raise_for_status()
        ticket = response.json().get("ticket", {})
        return _normalise_ticket(ticket)


# ── ADD NOTE TO TICKET ─────────────────────────────────────────────────────────
async def add_note(ticket_id: int, body: str, private: bool = True) -> dict:
    """
    Adds a note/comment to an existing ticket.

    Args:
        ticket_id: The ticket to comment on
        body:      The note text
        private:   True = internal note (only agents see it)
                   False = public reply (requester gets notified)

    Returns:
        Raw note response from Freshservice
    """
    async with _get_client() as client:
        response = await client.post(
            f"/tickets/{ticket_id}/notes",
            json={"body": body, "private": private},
        )
        response.raise_for_status()
        return response.json()
