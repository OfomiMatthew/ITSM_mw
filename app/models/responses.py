from pydantic import BaseModel
from typing import Optional, List


# ── Shared ticket shape returned by all ticket endpoints ───────────────────────

class TicketOut(BaseModel):
    """
    Normalised ticket object.
    FastAPI maps raw Freshservice fields to these clean names
    so Power Automate always gets a consistent shape.
    """
    ticket_id:      int
    subject:        str
    status:         int
    status_label:   str           # Human-readable: Open, Pending, Resolved, Closed
    priority:       int
    priority_label: str           # Human-readable: Low, Medium, High, Urgent
    created_at:     str
    due_by:         Optional[str] = None
    requester_id:   Optional[int] = None


# ── Per-endpoint response models ───────────────────────────────────────────────

class CreateTicketResponse(BaseModel):
    """Returned after POST /tickets"""
    success:   bool
    ticket_id: Optional[int] = None
    subject:   Optional[str] = None
    message:   str


class GetTicketResponse(BaseModel):
    """Returned after GET /tickets/{ticket_id}"""
    success:       bool
    ticket:        Optional[TicketOut] = None
    error_message: Optional[str]       = None


class TicketListResponse(BaseModel):
    """Returned after GET /tickets?email=..."""
    success:      bool
    ticket_count: int
    tickets:      List[TicketOut]
    summary:      str    # Pre-formatted string — Copilot Studio can display this directly


class GenericResponse(BaseModel):
    """Returned after PUT /tickets/{id} and POST /tickets/{id}/notes"""
    success: bool
    message: str


class HealthResponse(BaseModel):
    """Returned after GET /health"""
    status:  str
    service: str
    env:     str
