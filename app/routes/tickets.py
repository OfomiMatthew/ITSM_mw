"""
Ticket Routes
─────────────
All endpoints related to tickets. Each endpoint maps to one
Power Automate flow / Copilot Studio action.

Endpoint summary:
  POST   /tickets                  → Create a new ticket
  GET    /tickets/{ticket_id}      → Get a ticket by ID
  GET    /tickets?email=...        → List open tickets for a user
  PUT    /tickets/{ticket_id}      → Update priority / status
  POST   /tickets/{ticket_id}/notes → Add a note to a ticket
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.security import verify_api_key
from app.models.requests import CreateTicketRequest, UpdateTicketRequest, AddNoteRequest
from app.models.responses import (
    CreateTicketResponse,
    GetTicketResponse,
    TicketListResponse,
    GenericResponse,
)
import app.services.freshservice as fs

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
    dependencies=[Depends(verify_api_key)],   # Every route here requires x-api-key
)


# ── POST /tickets ──────────────────────────────────────────────────────────────
@router.post(
    "/",
    response_model=CreateTicketResponse,
    status_code=201,
    summary="Create a new ticket",
    description="Called by Power Automate flow: **Create Ticket**. Raises a new incident in Freshservice.",
)
async def create_ticket(body: CreateTicketRequest):
    """
    Example Power Automate HTTP action:
        Method: POST
        URI:    https://your-app.azurewebsites.net/tickets
        Header: x-api-key = <your middleware key>
        Body:   { subject, description, email, priority, category }
    """
    try:
        ticket = await fs.create_ticket(body.model_dump())
        return CreateTicketResponse(
            success=True,
            ticket_id=ticket["ticket_id"],
            subject=ticket["subject"],
            message=f"Ticket #{ticket['ticket_id']} created successfully.",
        )
    except Exception as e:
        return CreateTicketResponse(
            success=False,
            message=f"Failed to create ticket: {str(e)}",
        )


# ── GET /tickets/{ticket_id} ───────────────────────────────────────────────────
@router.get(
    "/{ticket_id}",
    response_model=GetTicketResponse,
    summary="Get a ticket by ID",
    description="Called by Power Automate flow: **Get Ticket Status**.",
)
async def get_ticket(ticket_id: int):
    """
    Example Power Automate HTTP action:
        Method: GET
        URI:    https://your-app.azurewebsites.net/tickets/@{variables('ticketId')}
        Header: x-api-key = <your middleware key>
    """
    try:
        ticket = await fs.get_ticket(ticket_id)
        return GetTicketResponse(success=True, ticket=ticket)
    except Exception as e:
        return GetTicketResponse(
            success=False,
            error_message=f"Could not retrieve ticket #{ticket_id}: {str(e)}",
        )


# ── GET /tickets?email=... ─────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=TicketListResponse,
    summary="List open tickets for a user",
    description="Called by Power Automate flow: **Get My Open Tickets**.",
)
async def list_tickets(
    email:  str           = Query(..., description="Requester email address"),
    status: Optional[int] = Query(2,   description="Filter by status code. Default 2=Open. Pass null for all."),
):
    """
    Example Power Automate HTTP action:
        Method: GET
        URI:    https://your-app.azurewebsites.net/tickets?email=@{triggerBody()?['email']}
        Header: x-api-key = <your middleware key>
    """
    try:
        tickets = await fs.get_tickets_by_email(email, status)

        # Build a pre-formatted summary string Copilot Studio can display directly
        if not tickets:
            summary = "You have no open tickets at the moment. 🎉"
        else:
            lines = [
                f"#{t['ticket_id']}: {t['subject']} | {t['status_label']} | {t['priority_label']}"
                for t in tickets
            ]
            summary = "\n".join(lines)

        return TicketListResponse(
            success=True,
            ticket_count=len(tickets),
            tickets=tickets,
            summary=summary,
        )
    except Exception as e:
        return TicketListResponse(
            success=False,
            ticket_count=0,
            tickets=[],
            summary=f"Error fetching tickets: {str(e)}",
        )


# ── PUT /tickets/{ticket_id} ───────────────────────────────────────────────────
@router.put(
    "/{ticket_id}",
    response_model=GenericResponse,
    summary="Update a ticket",
    description="Called by Power Automate flow: **Update Ticket**. Change priority or status.",
)
async def update_ticket(ticket_id: int, body: UpdateTicketRequest):
    """
    Example Power Automate HTTP action:
        Method: PUT
        URI:    https://your-app.azurewebsites.net/tickets/@{variables('ticketId')}
        Header: x-api-key = <your middleware key>
        Body:   { "priority": 3 }
    """
    try:
        updates = body.model_dump(exclude_none=True)

        if not updates:
            return GenericResponse(
                success=False,
                message="No fields provided to update.",
            )

        await fs.update_ticket(ticket_id, updates)
        return GenericResponse(
            success=True,
            message=f"Ticket #{ticket_id} updated successfully.",
        )
    except Exception as e:
        return GenericResponse(
            success=False,
            message=f"Failed to update ticket #{ticket_id}: {str(e)}",
        )


# ── POST /tickets/{ticket_id}/notes ───────────────────────────────────────────
@router.post(
    "/{ticket_id}/notes",
    response_model=GenericResponse,
    status_code=201,
    summary="Add a note to a ticket",
    description="Called by Power Automate flow: **Add Note**.",
)
async def add_note(ticket_id: int, body: AddNoteRequest):
    """
    Example Power Automate HTTP action:
        Method: POST
        URI:    https://your-app.azurewebsites.net/tickets/@{variables('ticketId')}/notes
        Header: x-api-key = <your middleware key>
        Body:   { "body": "User called to follow up.", "private": true }
    """
    try:
        await fs.add_note(ticket_id, body.body, body.private)
        return GenericResponse(
            success=True,
            message=f"Note added to ticket #{ticket_id} successfully.",
        )
    except Exception as e:
        return GenericResponse(
            success=False,
            message=f"Failed to add note to ticket #{ticket_id}: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# NEW ROUTE 4 — CREATE A NEW REQUESTER
# Add this to the bottom of app/routes/tickets.py
# ══════════════════════════════════════════════════════════════════════════════
@router.post(
    "/requesters",
    summary="Create a new requester (employee)",
    description=(
        "Creates a brand new employee in Freshservice as a requester. "
        "Called automatically when a new employee uses the agent for "
        "the first time and does not yet exist in Freshservice."
    ),
    status_code=201,
)
async def create_requester(
    first_name: str = Query(..., description="First name of the new employee"),
    last_name:  str = Query(..., description="Last name of the new employee"),
    email:      str = Query(..., description="Work email address"),
):
    """
    Power Automate HTTP action:
        Method: POST
        URI:    https://your-app.azurewebsites.net/tickets/requesters
                    ?first_name=John&last_name=Smith&email=john@company.com
        Header: x-api-key = <middleware key>
    """
    try:
        result = await fs.create_requester(first_name, last_name, email)
        return {
            "success": True,
            "message": f"Requester {result['name']} created successfully. They can now raise tickets.",
            **result,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Could not create requester: {str(e)}",
        }

