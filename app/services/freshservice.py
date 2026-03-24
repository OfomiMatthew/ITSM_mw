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


# def _normalise_ticket(raw: dict) -> dict:
#     requester      = raw.get("requester", {})
#     first          = requester.get("first_name", "")
#     last           = requester.get("last_name", "")
#     requester_name = requester.get("name") or f"{first} {last}".strip() or "Unknown"

#     return {
#         "ticket_id":       raw.get("id"),
#         "subject":         raw.get("subject", ""),
#         "status":          raw.get("status", 2),
#         "status_label":    STATUS_MAP.get(raw.get("status", 2), "Unknown"),
#         "priority":        raw.get("priority", 2),
#         "priority_label":  PRIORITY_MAP.get(raw.get("priority", 2), "Unknown"),
#         "created_at":      raw.get("created_at", ""),
#         "due_by":          raw.get("due_by"),
#         "requester_id":    raw.get("requester_id"),
#         "requester_name":  requester_name,
#         "requester_email": requester.get("email", ""),
#     }



def _normalise_ticket(raw: dict) -> dict:
    requester      = raw.get("requester", {})
    first          = requester.get("first_name", "")
    last           = requester.get("last_name", "")
    requester_name = requester.get("name") or f"{first} {last}".strip() or "Unknown"

    status = raw.get("status")   # ← no default — trust exactly what Freshservice returns

    return {
        "ticket_id":       raw.get("id"),
        "subject":         raw.get("subject", ""),
        "status":          status,
        "status_label":    STATUS_MAP.get(status, "Unknown"),   # ← no default fallback to Open
        "priority":        raw.get("priority", 2),
        "priority_label":  PRIORITY_MAP.get(raw.get("priority", 2), "Unknown"),
        "created_at":      raw.get("created_at", ""),
        "due_by":          raw.get("due_by"),
        "requester_id":    raw.get("requester_id"),
        "requester_name":  requester_name,
        "requester_email": requester.get("email", ""),
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
    async with _get_client() as client:
        response = await client.get(f"/tickets/{ticket_id}?include=requester")  # ← only change here
        response.raise_for_status()
        ticket = response.json().get("ticket", {})
        return _normalise_ticket(ticket)


# ── GET TICKETS BY EMAIL ───────────────────────────────────────────────────────

# async def get_tickets_by_email(email: str, status: Optional[int] = 2) -> list:
#     async with _get_client() as client:

#         # ── STEP 1: Try requester lookup first ────────────────────
#         requester_resp = await client.get("/requesters", params={"email": email})
#         requester_resp.raise_for_status()
#         requesters = requester_resp.json().get("requesters", [])

#         if requesters:
#             requester_id = requesters[0]["id"]
#         else:
#             # ── STEP 1b: Not a requester — try agents endpoint ────
#             agent_resp = await client.get("/agents", params={"email": email})
#             agent_resp.raise_for_status()
#             agents = agent_resp.json().get("agents", [])

#             if not agents:
#                 # Not a requester OR an agent — truly not found
#                 return []

#             requester_id = agents[0]["id"]

#         # ── STEP 2: Filter tickets by requester_id ────────────────
#         if status is not None:
#             url = f'/tickets/filter?query="requester_id:{requester_id} AND status:{status}"&per_page=10&order_type=desc'
#         else:
#             url = f'/tickets/filter?query="requester_id:{requester_id}"&per_page=10&order_type=desc'

#         tickets_resp = await client.get(url)
#         tickets_resp.raise_for_status()

#         tickets = tickets_resp.json().get("tickets", [])
#         return [_normalise_ticket(t) for t in tickets]
    
   
# async def get_tickets_by_email(email: str, status: Optional[int] = 2) -> list:
async def get_tickets_by_email(email: str, status: Optional[int] = None) -> list:
    async with _get_client() as client:

        # ── STEP 1: Try requester lookup first ────────────────────
        requester_resp = await client.get("/requesters", params={"email": email})
        requester_resp.raise_for_status()
        requesters = requester_resp.json().get("requesters", [])

        if requesters:
            requester_id    = requesters[0]["id"]
            first           = requesters[0].get("first_name", "")
            last            = requesters[0].get("last_name", "")
            requester_name  = f"{first} {last}".strip() or "Unknown"
            requester_email = requesters[0].get("primary_email", "")
        else:
            # ── STEP 1b: Not a requester — try agents endpoint ────
            agent_resp = await client.get("/agents", params={"email": email})
            agent_resp.raise_for_status()
            agents = agent_resp.json().get("agents", [])

            if not agents:
                # Not a requester OR an agent — truly not found
                return []

            requester_id    = agents[0]["id"]
            first           = agents[0].get("first_name", "")
            last            = agents[0].get("last_name", "")
            requester_name  = f"{first} {last}".strip() or "Unknown"
            requester_email = agents[0].get("email", "")

        # ── STEP 2: Fetch all tickets for this requester ──────────
        params = {
            "requester_id": requester_id,
            "per_page":     100,
            "order_type":   "desc",
            "order_by":     "created_at",
        }

        tickets_resp = await client.get("/tickets", params=params)
        tickets_resp.raise_for_status()

        tickets = tickets_resp.json().get("tickets", [])

        # ── STEP 3: Filter by status in Python ────────────────────
        # Freshservice ignores the status param on /tickets endpoint
        # so we filter client-side instead
        if status is not None:
            tickets = [t for t in tickets if t.get("status") == status]

        # ── STEP 4: Inject requester name + email into each ticket ─
        for t in tickets:
            t["requester"] = {
                "name":  requester_name,
                "email": requester_email,
            }

        return [_normalise_ticket(t) for t in tickets]


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




# async def add_note(
#     ticket_id:      int,
#     body:           str,
#     private:        bool = True,
#     author_name:    str  = "",
#     author_email:   str  = "",
# ) -> dict:
#     """
#     Adds a note to a ticket.
#     Includes the author's name in the note body so Freshservice
#     shows who actually wrote it — not just the API key owner.
#     """
#     # Prefix the note with the author's name so it is always visible
#     if author_name:
#         formatted_body = (
#             f"📝 Note added by: {author_name}"
#             + (f" ({author_email})" if author_email else "")
#             + f"\n{'─' * 40}\n"
#             + body
#         )
#     else:
#         formatted_body = body

#     async with _get_client() as client:
#         response = await client.post(
#             f"/tickets/{ticket_id}/notes",
#             json={
#                 "body":    formatted_body,
#                 "private": private,
#             },
#         )
#         response.raise_for_status()
#         return {
#             "ticket_id":    ticket_id,
#             "note_body":    formatted_body,
#             "private":      private,
#             "author_name":  author_name  or "Unknown",
#             "author_email": author_email or "",
#             "message":      f"Note added to ticket #{ticket_id} by {author_name or 'Unknown'}.",
#         }




# async def add_note(
#     ticket_id:    int,
#     body:         str,
#     private:      bool = True,
#     author_name:  str  = "",
#     author_email: str  = "",
# ) -> dict:
#     """
#     Adds a note to a ticket.
#     If author_email is provided, verifies the person exists
#     in Freshservice before allowing the note to be added.
#     """
#     async with _get_client() as client:

#         # ── Check if the author exists in Freshservice ─────────────
#         # Only runs if an email was provided
#         if author_email:

#             # Check requesters first
#             req_resp   = await client.get("/requesters", params={"email": author_email})
#             found_user = (
#                 req_resp.is_success and
#                 len(req_resp.json().get("requesters", [])) > 0
#             )

#             # If not a requester, check agents
#             if not found_user:
#                 agent_resp = await client.get("/agents", params={"email": author_email})
#                 found_user = (
#                     agent_resp.is_success and
#                     len(agent_resp.json().get("agents", [])) > 0
#                 )

#             # If not found anywhere — block the note
#             if not found_user:
#                 raise ValueError(
#                     f"User '{author_email}' does not exist in Freshservice. "
#                     f"Only registered users and agents can add notes to tickets."
#                 )

#         # ── Format the note body with author attribution ────────────
#         if author_name:
#             formatted_body = (
#                 f"📝 Note added by: {author_name}"
#                 + (f" ({author_email})" if author_email else "")
#                 + f"\n{'─' * 40}\n"
#                 + body
#             )
#         else:
#             formatted_body = body

#         # ── Post the note to Freshservice ───────────────────────────
#         response = await client.post(
#             f"/tickets/{ticket_id}/notes",
#             json={
#                 "body":    formatted_body,
#                 "private": private,
#             },
#         )
#         response.raise_for_status()

#         return {
#             "ticket_id":    ticket_id,
#             "note_body":    formatted_body,
#             "private":      private,
#             "author_name":  author_name  or "Unknown",
#             "author_email": author_email or "",
#             "message":      f"Note added to ticket #{ticket_id} by {author_name or 'Unknown'}.",
#         }




# ══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINT 4 — CREATE A NEW REQUESTER (USER)
# Paste this into the bottom of app/services/freshservice.py
# ══════════════════════════════════════════════════════════════════════════════
async def create_requester(
    first_name: str,
    last_name:  str,
    email:      str,
) -> dict:
    """
    Creates a new requester (employee) in Freshservice.

    Used when a brand new employee tries to use the agent
    for the first time and does not exist in Freshservice yet.

    The agent calls this automatically if get_user_role()
    returns role: 'unknown' — it creates them on the spot
    so they can start raising tickets immediately.
    """
    async with _get_client() as client:
        resp = await client.post(
            "/requesters",
            json={
                "first_name":    first_name,
                "last_name":     last_name,
                "primary_email": email,
            }
        )
        resp.raise_for_status()

        req = resp.json().get("requester", {})

        return {
            "requester_id": req.get("id"),
            "name":         f"{first_name} {last_name}".strip(),
            "email":        email,
        }
        
        



