"""
app/models/manager.py
─────────────────────
Pydantic models for all Manager / Admin endpoints.
These describe the shape of data coming IN and going OUT
for manager-only features like analytics, SLA breaches,
team tickets, assets, and knowledge base search.
"""

from pydantic import BaseModel
from typing import Optional, List


# ══════════════════════════════════════════════════════════════
# USER ROLE MODELS
# ══════════════════════════════════════════════════════════════

class UserRoleResponse(BaseModel):
    """
    Returned by GET /users/role?email=...
    Tells Copilot Studio exactly who this person is
    and what features they are allowed to see.
    """
    success:               bool
    email:                 str
    display_name:          str
    role:                  str        # "requester", "agent", or "manager"
    is_manager:            bool
    is_agent:              bool
    is_requester:          bool
    can_view_team_tickets: bool
    can_view_analytics:    bool
    can_assign_tickets:    bool
    error_message:         Optional[str] = None


# ══════════════════════════════════════════════════════════════
# TEAM TICKETS MODELS
# ══════════════════════════════════════════════════════════════

class TeamTicketOut(BaseModel):
    """
    A single ticket in the team view.
    Includes extra fields managers care about
    (who it is assigned to, which group, department).
    """
    ticket_id:      int
    subject:        str
    status_label:   str
    priority_label: str
    requester:      str           # Name of the person who raised it
    requester_email: Optional[str] = None
    assigned_to:    str           # Name of agent it is assigned to
    group:          str           # Which IT group owns it
    created_at:     str
    due_by:         Optional[str] = None
    is_overdue:     bool = False  # True if past the due date


class TeamTicketsResponse(BaseModel):
    """
    Returned by GET /manager/tickets
    Full list of tickets across the whole team.
    """
    success:      bool
    ticket_count: int
    tickets:      List[TeamTicketOut]
    summary:      str
    error_message: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# ANALYTICS MODELS
# ══════════════════════════════════════════════════════════════

class TicketAnalytics(BaseModel):
    """
    The numbers inside the analytics report.
    Each field is a count or average the manager cares about.
    """
    total_open:          int
    total_pending:       int
    total_resolved:      int
    total_closed:        int
    overdue_count:       int
    high_priority_count: int
    urgent_count:        int
    created_today:       int
    resolved_today:      int


class AnalyticsResponse(BaseModel):
    """
    Returned by GET /manager/analytics
    A full snapshot of the IT support desk right now.
    """
    success:       bool
    analytics:     Optional[TicketAnalytics] = None
    summary:       str    # Pre-formatted text for Copilot Studio to display
    error_message: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# SLA BREACH MODELS
# ══════════════════════════════════════════════════════════════

class SLABreachTicket(BaseModel):
    """
    A single ticket that is at risk of or has already
    breached its SLA deadline.
    """
    ticket_id:      int
    subject:        str
    priority_label: str
    status_label:   str
    requester:      str
    due_by:         str
    breach_status:  str   # "already_breached", "breach_in_1hr", "breach_in_4hrs"
    assigned_to:    str


class SLABreachResponse(BaseModel):
    """
    Returned by GET /manager/sla-breaches
    Lists all tickets that are overdue or close to breaching.
    """
    success:       bool
    breach_count:  int
    breaches:      List[SLABreachTicket]
    summary:       str
    error_message: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# ASSET MODELS
# ══════════════════════════════════════════════════════════════

class AssetOut(BaseModel):
    """
    A single IT asset (laptop, phone, monitor etc.)
    assigned to a specific user.
    """
    asset_id:    int
    name:        str
    asset_type:  str           # Laptop, Monitor, Phone, etc.
    serial:      Optional[str] = None
    status:      str           # In Use, In Store, Retired
    assigned_to: str


class AssetResponse(BaseModel):
    """
    Returned by GET /manager/assets?email=...
    Lists all assets assigned to a specific user.
    """
    success:       bool
    asset_count:   int
    assets:        List[AssetOut]
    summary:       str
    error_message: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# KNOWLEDGE BASE MODELS
# ══════════════════════════════════════════════════════════════

class KBArticle(BaseModel):
    """
    A single knowledge base article found in the search.
    """
    article_id:   int
    title:        str
    description:  str           # Short preview of the article
    category:     str
    status:       str           # Published, Draft
    url:          Optional[str] = None


class KBSearchResponse(BaseModel):
    """
    Returned by GET /manager/knowledge-base/search?query=...
    Lists matching KB articles for the search term.
    """
    success:        bool
    result_count:   int
    articles:       List[KBArticle]
    summary:        str
    error_message:  Optional[str] = None


# ══════════════════════════════════════════════════════════════
# TICKET ASSIGNMENT MODEL
# ══════════════════════════════════════════════════════════════

class AssignTicketResponse(BaseModel):
    """
    Returned by PUT /manager/tickets/{id}/assign
    Confirms a ticket was assigned to a specific agent.
    """
    success:    bool
    message:    str
    ticket_id:  Optional[int]  = None
    assigned_to: Optional[str] = None
