"""
app/routes/manager.py
──────────────────────
All Manager / Admin endpoints.

These routes are for IT managers and admins ONLY.
In Copilot Studio, the agent checks the user role first
and only shows these options to managers and admins.

Endpoint summary:
  GET  /users/role                       → Who is this person?
  GET  /manager/tickets                  → All team tickets
  GET  /manager/analytics                → Ticket counts & stats
  GET  /manager/sla-breaches             → Tickets at risk of breach
  GET  /manager/assets                   → Assets assigned to a user
  GET  /manager/knowledge-base/search    → Search KB articles
  PUT  /manager/tickets/{id}/assign      → Assign ticket to agent
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.security import verify_api_key
from app.models.manager import (
    UserRoleResponse,
    TeamTicketsResponse,
    AnalyticsResponse,
    TicketAnalytics,
    SLABreachResponse,
    AssetResponse,
    KBSearchResponse,
    AssignTicketResponse,
)
import app.services.manager as ms

# ── Two routers — one for /users, one for /manager ────────────────────────────
# This keeps the URLs clean and logical

user_router = APIRouter(
    prefix="/users",
    tags=["Users & Roles"],
    dependencies=[Depends(verify_api_key)],
)

manager_router = APIRouter(
    prefix="/manager",
    tags=["Manager & Admin"],
    dependencies=[Depends(verify_api_key)],
)


# ══════════════════════════════════════════════════════════════════════════════
# GET /users/role  — Who is this person?
# ══════════════════════════════════════════════════════════════════════════════
@user_router.get(
    "/role",
    response_model=UserRoleResponse,
    summary="Get user role",
    description=(
        "Called at the START of every Copilot Studio conversation. "
        "Tells the agent if the user is a regular requester, an IT agent, "
        "or a manager — so it can show the right menu."
    ),
)
async def get_user_role(
    email: str = Query(..., description="The user's email address")
):
    """
    Power Automate HTTP action:
        Method: GET
        URI:    https://your-app.azurewebsites.net/users/role?email=@{user_email}
        Header: x-api-key = <middleware key>
    """
    try:
        role_data = await ms.get_user_role(email)
        return UserRoleResponse(
            success=True,
            **role_data,
        )
    except Exception as e:
        return UserRoleResponse(
            success=False,
            email=email,
            display_name=email,
            role="unknown",
            is_manager=False,
            is_agent=False,
            is_requester=False,
            can_view_team_tickets=False,
            can_view_analytics=False,
            can_assign_tickets=False,
            error_message=str(e),
        )


# ══════════════════════════════════════════════════════════════════════════════
# GET /manager/tickets  — All team tickets
# ══════════════════════════════════════════════════════════════════════════════
@manager_router.get(
    "/tickets",
    response_model=TeamTicketsResponse,
    summary="Get all team tickets",
    description=(
        "Returns ALL tickets across the Freshservice account. "
        "Managers use this to see everything happening across the IT team. "
        "Optionally filter by status or priority."
    ),
)
async def get_team_tickets(
    status:   Optional[int] = Query(None, description="Filter by status. 2=Open 3=Pending 4=Resolved 5=Closed"),
    priority: Optional[int] = Query(None, description="Filter by priority. 1=Low 2=Medium 3=High 4=Urgent"),
    per_page: int            = Query(20,   description="How many tickets to return. Max 30."),
):
    """
    Power Automate HTTP action:
        Method: GET
        URI:    https://your-app.azurewebsites.net/manager/tickets?status=2
        Header: x-api-key = <middleware key>
    """
    try:
        tickets = await ms.get_team_tickets(status, priority, min(per_page, 30))

        if not tickets:
            summary = "No tickets found matching your filter."
        else:
            overdue = [t for t in tickets if t["is_overdue"]]
            lines   = [
                f"#{t['ticket_id']}: {t['subject']} | "
                f"{t['status_label']} | {t['priority_label']}"
                + (" ⚠ OVERDUE" if t["is_overdue"] else "")
                for t in tickets
            ]
            summary = "\n".join(lines)
            if overdue:
                summary = f"⚠ {len(overdue)} OVERDUE ticket(s) flagged\n\n" + summary

        return TeamTicketsResponse(
            success=True,
            ticket_count=len(tickets),
            tickets=tickets,
            summary=summary,
        )
    except Exception as e:
        return TeamTicketsResponse(
            success=False,
            ticket_count=0,
            tickets=[],
            summary="",
            error_message=str(e),
        )


# ══════════════════════════════════════════════════════════════════════════════
# GET /manager/analytics  — Ticket counts & stats
# ══════════════════════════════════════════════════════════════════════════════
@manager_router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    summary="Get ticket analytics",
    description=(
        "Returns a full snapshot of the IT support desk. "
        "How many tickets are open, pending, resolved, overdue, "
        "high priority, and urgent. Perfect for a daily standup report."
    ),
)
async def get_analytics():
    """
    Power Automate HTTP action:
        Method: GET
        URI:    https://your-app.azurewebsites.net/manager/analytics
        Header: x-api-key = <middleware key>
    """
    try:
        data = await ms.get_analytics()
        a    = TicketAnalytics(**data)

        summary = (
            f"📊 IT Support Desk — Live Snapshot\n"
            f"────────────────────────────────\n"
            f"🟢 Open:          {a.total_open}\n"
            f"🟡 Pending:       {a.total_pending}\n"
            f"✅ Resolved:      {a.total_resolved}\n"
            f"⛔ Closed:        {a.total_closed}\n"
            f"────────────────────────────────\n"
            f"🔴 Overdue:       {a.overdue_count}\n"
            f"🔥 Urgent:        {a.urgent_count}\n"
            f"⚠  High Priority: {a.high_priority_count}"
        )

        return AnalyticsResponse(
            success=True,
            analytics=a,
            summary=summary,
        )
    except Exception as e:
        return AnalyticsResponse(
            success=False,
            summary="",
            error_message=str(e),
        )


# ══════════════════════════════════════════════════════════════════════════════
# GET /manager/sla-breaches  — Tickets at risk of SLA breach
# ══════════════════════════════════════════════════════════════════════════════
@manager_router.get(
    "/sla-breaches",
    response_model=SLABreachResponse,
    summary="Get SLA breach alerts",
    description=(
        "Finds tickets that have ALREADY breached their SLA deadline "
        "or are at risk of breaching within the next 4 hours. "
        "This is the most proactive and powerful manager feature."
    ),
)
async def get_sla_breaches():
    """
    Power Automate HTTP action:
        Method: GET
        URI:    https://your-app.azurewebsites.net/manager/sla-breaches
        Header: x-api-key = <middleware key>
    """
    try:
        breaches = await ms.get_sla_breaches()

        if not breaches:
            summary = "✅ Great news! No SLA breaches or risks right now."
        else:
            already   = [b for b in breaches if b["breach_status"] == "already_breached"]
            in_1hr    = [b for b in breaches if b["breach_status"] == "breach_in_1hr"]
            in_4hrs   = [b for b in breaches if b["breach_status"] == "breach_in_4hrs"]

            lines = []
            if already:
                lines.append(f"🔴 ALREADY BREACHED ({len(already)} tickets):")
                for b in already:
                    lines.append(f"  #{b['ticket_id']}: {b['subject']} | {b['priority_label']}")
            if in_1hr:
                lines.append(f"\n🟠 BREACHING WITHIN 1 HOUR ({len(in_1hr)} tickets):")
                for b in in_1hr:
                    lines.append(f"  #{b['ticket_id']}: {b['subject']} | {b['priority_label']}")
            if in_4hrs:
                lines.append(f"\n🟡 BREACHING WITHIN 4 HOURS ({len(in_4hrs)} tickets):")
                for b in in_4hrs:
                    lines.append(f"  #{b['ticket_id']}: {b['subject']} | {b['priority_label']}")

            summary = "\n".join(lines)

        return SLABreachResponse(
            success=True,
            breach_count=len(breaches),
            breaches=breaches,
            summary=summary,
        )
    except Exception as e:
        return SLABreachResponse(
            success=False,
            breach_count=0,
            breaches=[],
            summary="",
            error_message=str(e),
        )


# ══════════════════════════════════════════════════════════════════════════════
# GET /manager/assets  — Assets assigned to a user
# ══════════════════════════════════════════════════════════════════════════════
@manager_router.get(
    "/assets",
    response_model=AssetResponse,
    summary="Get assets for a user",
    description=(
        "Returns all IT assets (laptops, phones, monitors etc.) "
        "assigned to a specific user. Used when a ticket is raised "
        "to pre-fill the affected device details automatically."
    ),
)
async def get_assets(
    email: str = Query(..., description="The user's email address"),
):
    """
    Power Automate HTTP action:
        Method: GET
        URI:    https://your-app.azurewebsites.net/manager/assets?email=user@company.com
        Header: x-api-key = <middleware key>
    """
    try:
        assets = await ms.get_assets_for_user(email)

        if not assets:
            summary = f"No assets found assigned to {email}."
        else:
            lines = [
                f"• {a['name']} ({a['asset_type']}) — {a['status']}"
                + (f" | S/N: {a['serial']}" if a.get("serial") else "")
                for a in assets
            ]
            summary = f"Assets assigned to {email}:\n" + "\n".join(lines)

        return AssetResponse(
            success=True,
            asset_count=len(assets),
            assets=assets,
            summary=summary,
        )
    except Exception as e:
        return AssetResponse(
            success=False,
            asset_count=0,
            assets=[],
            summary="",
            error_message=str(e),
        )


# ══════════════════════════════════════════════════════════════════════════════
# GET /manager/knowledge-base/search  — Search KB articles
# ══════════════════════════════════════════════════════════════════════════════
@manager_router.get(
    "/knowledge-base/search",
    response_model=KBSearchResponse,
    summary="Search knowledge base",
    description=(
        "Searches Freshservice's knowledge base for self-service articles. "
        "Called BEFORE raising a ticket — if a solution already exists, "
        "show it to the user first. This reduces unnecessary ticket creation."
    ),
)
async def search_knowledge_base(
    query: str = Query(..., description="The search term e.g. 'wifi not working'"),
):
    """
    Power Automate HTTP action:
        Method: GET
        URI:    https://your-app.azurewebsites.net/manager/knowledge-base/search?query=wifi+issue
        Header: x-api-key = <middleware key>
    """
    try:
        articles = await ms.search_knowledge_base(query)

        if not articles:
            summary = (
                f"No knowledge base articles found for '{query}'. "
                f"I will proceed to raise a ticket."
            )
        else:
            lines = [
                f"📄 {a['title']} [{a['category']}]"
                for a in articles
            ]
            summary = (
                f"I found {len(articles)} article(s) that might help:\n"
                + "\n".join(lines)
                + "\n\nWould you like to read one, or shall I raise a ticket instead?"
            )

        return KBSearchResponse(
            success=True,
            result_count=len(articles),
            articles=articles,
            summary=summary,
        )
    except Exception as e:
        return KBSearchResponse(
            success=False,
            result_count=0,
            articles=[],
            summary=f"Could not search knowledge base: {str(e)}",
            error_message=str(e),
        )


# ══════════════════════════════════════════════════════════════════════════════
# PUT /manager/tickets/{id}/assign  — Assign ticket to agent
# ══════════════════════════════════════════════════════════════════════════════
@manager_router.put(
    "/tickets/{ticket_id}/assign",
    response_model=AssignTicketResponse,
    summary="Assign ticket to an agent",
    description=(
        "Assigns an existing ticket to a specific IT agent by their email. "
        "Managers use this when they see an unassigned or incorrectly assigned ticket."
    ),
)
async def assign_ticket(
    ticket_id:   int,
    agent_email: str = Query(..., description="Email of the agent to assign the ticket to"),
):
    """
    Power Automate HTTP action:
        Method: PUT
        URI:    https://your-app.azurewebsites.net/manager/tickets/145/assign?agent_email=agent@company.com
        Header: x-api-key = <middleware key>
    """
    try:
        result = await ms.assign_ticket(ticket_id, agent_email)
        return AssignTicketResponse(
            success=True,
            message=f"Ticket #{ticket_id} assigned to {result['assigned_to']} successfully.",
            ticket_id=ticket_id,
            assigned_to=result["assigned_to"],
        )
    except Exception as e:
        return AssignTicketResponse(
            success=False,
            message=f"Could not assign ticket: {str(e)}",
        )





# ══════════════════════════════════════════════════════════════════════════════
# RESOLVE TICKET — Manager/Agent only
# ══════════════════════════════════════════════════════════════════════════════
@manager_router.post(
    "/tickets/{ticket_id}/resolve",
    summary="Resolve a ticket",
    description=(
        "Marks a ticket as Resolved and adds a resolution note. "
        "The requester gets an email notification automatically. "
        "Only agents and managers can resolve tickets."
    ),
)
async def resolve_ticket(
    ticket_id:       int,
    resolution_note: str = Query(
        ...,
        min_length=10,
        description="What fixed the issue? Minimum 10 characters."
    ),
):
    """
    Power Automate HTTP action:
        Method: POST
        URI:    https://your-app.azurewebsites.net/manager/tickets/147/resolve
                    ?resolution_note=Reinstalled+WiFi+driver
        Header: x-api-key = <middleware key>
    """
    try:
        await ms.resolve_ticket(ticket_id, resolution_note)
        return {
            "success":   True,
            "ticket_id": ticket_id,
            "message":   (
                f"Ticket #{ticket_id} has been marked as Resolved. "
                f"The requester has been notified by email."
            ),
        }
    except Exception as e:
        return {
            "success":   False,
            "ticket_id": ticket_id,
            "message":   str(e),
        }
        
        
        

# ══════════════════════════════════════════════════════════════════════════════
# UPDATE TICKET — Manager/Agent only
# ══════════════════════════════════════════════════════════════════════════════
@manager_router.put(
    "/tickets/{ticket_id}",
    summary="Update a ticket",
    description=(
        "Updates a ticket's priority and/or status. "
        "Only agents and managers can update tickets. "
        "Send 0 for any field you do not want to change."
    ),
)
async def update_ticket(
    ticket_id:    int,
    new_priority: int = Query(0, description="1=Low 2=Medium 3=High 4=Urgent. Send 0 to skip."),
    new_status:   int = Query(0, description="2=Open 3=Pending 4=Resolved 5=Closed. Send 0 to skip."),
):
    """
    Power Automate HTTP action:
        Method: PUT
        URI:    https://your-app.azurewebsites.net/manager/tickets/147
                    ?new_priority=3&new_status=2
        Header: x-api-key = <middleware key>
    """
    try:
        result = await ms.update_ticket(ticket_id, new_priority, new_status)
        return {
            "success": True,
            **result,
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
        }
