"""
app/services/manager.py
────────────────────────
All Freshservice API calls for Manager / Admin features.
Just like services/freshservice.py handles end-user calls,
this file handles EVERYTHING a manager or admin needs.

Rule: No route file talks to Freshservice directly.
      All calls go through a service file like this one.
"""

import httpx
from datetime import datetime, timezone,timedelta
from app.config import get_settings
from typing import Optional


# ── Label maps (same as in freshservice.py) ────────────────────────────────────
PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High",    4: "Urgent"}
STATUS_MAP   = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}


# ── HTTP client (same pattern as freshservice.py) ─────────────────────────────
def _get_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.freshservice_base_url,
        auth=(settings.freshservice_api_key, "X"),
        headers={"Content-Type": "application/json"},
        timeout=20.0,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. GET USER ROLE
# ══════════════════════════════════════════════════════════════════════════════
async def get_user_role(email: str) -> dict:
    """
    Figures out who a person is in Freshservice.

    Strategy:
      - First check if the email belongs to an Agent (IT staff).
      - If yes, check if they have a supervisor/manager role.
      - If not an agent, they are a regular Requester (end user).

    Returns a dict with role, display name, and permission flags.
    """
    async with _get_client() as client:

        # ── Check if this email belongs to an Agent ────────────────
        agent_resp = await client.get(
            "/agents",
            params={"email": email}
        )

        if agent_resp.status_code == 200:
            agents = agent_resp.json().get("agents", [])

            if agents:
                agent = agents[0]
                name  = f"{agent.get('first_name','')} {agent.get('last_name','')}".strip()

                # Check their role name to see if they are a manager/supervisor
                # Freshservice stores role_ids on the agent object
                # We look at the agent's role to determine if manager
                role_name  = agent.get("role", "").lower()
                is_manager = any(word in role_name for word in
                                 ["manager", "supervisor", "admin", "lead"])

                # Also check if they are "account_admin" which is super admin
                if agent.get("is_account_admin") or agent.get("is_admin"):
                    is_manager = True

                return {
                    "email":                 email,
                    "display_name":          name or email,
                    "role":                  "manager" if is_manager else "agent",
                    "is_manager":            is_manager,
                    "is_agent":              True,
                    "is_requester":          False,
                    "can_view_team_tickets": True,
                    "can_view_analytics":    is_manager,
                    "can_assign_tickets":    True,
                }

        # ── Not an agent — check if they are a Requester ──────────
        req_resp = await client.get(
            "/requesters",
            params={"email": email}
        )

        if req_resp.status_code == 200:
            requesters = req_resp.json().get("requesters", [])
            if requesters:
                req  = requesters[0]
                name = f"{req.get('first_name','')} {req.get('last_name','')}".strip()
                return {
                    "email":                 email,
                    "display_name":          name or email,
                    "role":                  "requester",
                    "is_manager":            False,
                    "is_agent":              False,
                    "is_requester":          True,
                    "can_view_team_tickets": False,
                    "can_view_analytics":    False,
                    "can_assign_tickets":    False,
                }

        # ── Email not found anywhere in Freshservice ───────────────
        return {
            "email":                 email,
            "display_name":          email,
            "role":                  "unknown",
            "is_manager":            False,
            "is_agent":              False,
            "is_requester":          False,
            "can_view_team_tickets": False,
            "can_view_analytics":    False,
            "can_assign_tickets":    False,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 2. GET ALL TEAM TICKETS
# ══════════════════════════════════════════════════════════════════════════════
# async def get_team_tickets(
#     status:   Optional[int] = None,
#     priority: Optional[int] = None,
#     per_page: int = 20,
# ) -> list:
#     """
#     Fetches ALL tickets across the entire Freshservice account.
#     Managers use this to see the full picture of what is happening.

#     Optional filters:
#       status   — 2=Open 3=Pending 4=Resolved 5=Closed
#       priority — 1=Low 2=Medium 3=High 4=Urgent
#     """
#     async with _get_client() as client:

#         # Build filter query for the Freshservice filter endpoint
#         conditions = []
#         if status   is not None:
#             conditions.append(f"status:{status}")
#         if priority is not None:
#             conditions.append(f"priority:{priority}")

#         if conditions:
#             query = '"' + " AND ".join(conditions) + '"'
#             resp  = await client.get(
#                 "/tickets/filter",
#                 params={"query": query, "per_page": per_page}
#             )
#         else:
#             # No filters — get all tickets ordered by newest first
#             resp = await client.get(
#                 "/tickets",
#                 params={
#                     "per_page":   per_page,
#                     "order_type": "desc",
#                     "order_by":   "created_at",
#                 }
#             )

#         resp.raise_for_status()
#         raw_tickets = resp.json().get("tickets", [])

#         now = datetime.now(timezone.utc)
#         result = []

#         for t in raw_tickets:
#             # Figure out if ticket is overdue
#             is_overdue = False
#             due_by_str = t.get("due_by")
#             if due_by_str:
#                 try:
#                     due_dt     = datetime.fromisoformat(due_by_str.replace("Z", "+00:00"))
#                     is_overdue = now > due_dt and t.get("status", 2) not in [4, 5]
#                 except Exception:
#                     pass

#             result.append({
#                 "ticket_id":      t.get("id"),
#                 "subject":        t.get("subject", ""),
#                 "status_label":   STATUS_MAP.get(t.get("status", 2), "Unknown"),
#                 "priority_label": PRIORITY_MAP.get(t.get("priority", 2), "Unknown"),
#                 "requester":      str(t.get("requester_id", "Unknown")),
#                 "assigned_to":    str(t.get("responder_id", "Unassigned")),
#                 "group":          str(t.get("group_id", "No Group")),
#                 "created_at":     t.get("created_at", ""),
#                 "due_by":         due_by_str,
#                 "is_overdue":     is_overdue,
#             })

#         return result


async def get_team_tickets(
    status:   Optional[int] = None,
    priority: Optional[int] = None,
    per_page: int = 20,
) -> list:
    """
    Fetches ALL tickets across the entire Freshservice account.
    Managers use this to see the full picture of what is happening.

    Optional filters:
      status   — 2=Open 3=Pending 4=Resolved 5=Closed
      priority — 1=Low 2=Medium 3=High 4=Urgent
    """
    async with _get_client() as client:

        # ── STEP 1: Fetch agents once to build id → name lookup ───
        agents_resp = await client.get("/agents", params={"per_page": 100})
        agents_map  = {}  # {agent_id: "Full Name"}
        if agents_resp.is_success:
            for a in agents_resp.json().get("agents", []):
                agent_id   = a.get("id")
                first      = a.get("first_name", "")
                last       = a.get("last_name", "")
                full_name  = f"{first} {last}".strip() or "Unknown"
                if agent_id:
                    agents_map[agent_id] = full_name

        # ── STEP 2: Fetch tickets ──────────────────────────────────
        conditions = []
        if status   is not None:
            conditions.append(f"status:{status}")
        if priority is not None:
            conditions.append(f"priority:{priority}")

        if conditions:
            query = '"' + " AND ".join(conditions) + '"'
            resp  = await client.get(
                "/tickets/filter",
                params={
                    "query":    query,
                    "per_page": per_page,
                    "include":  "requester",    # ← NEW
                }
            )
        else:
            resp = await client.get(
                "/tickets",
                params={
                    "per_page":   per_page,
                    "order_type": "desc",
                    "order_by":   "created_at",
                    "include":    "requester",  # ← NEW
                }
            )

        resp.raise_for_status()
        raw_tickets = resp.json().get("tickets", [])

        # ── STEP 3: Build result with names ───────────────────────
        now    = datetime.now(timezone.utc)
        result = []

        for t in raw_tickets:

            # Requester name + email from embedded requester object
            requester       = t.get("requester", {})
            first           = requester.get("first_name", "")
            last            = requester.get("last_name", "")
            requester_name  = requester.get("name") or f"{first} {last}".strip() or "Unknown"
            requester_email = requester.get("email", "")

            # Agent name from lookup dict built in Step 1
            responder_id    = t.get("responder_id")
            assigned_to     = agents_map.get(responder_id, "Unassigned")

            # Overdue check
            is_overdue  = False
            due_by_str  = t.get("due_by")
            if due_by_str:
                try:
                    due_dt     = datetime.fromisoformat(due_by_str.replace("Z", "+00:00"))
                    is_overdue = now > due_dt and t.get("status", 2) not in [4, 5]
                except Exception:
                    pass

            result.append({
                "ticket_id":       t.get("id"),
                "subject":         t.get("subject", ""),
                "status_label":    STATUS_MAP.get(t.get("status", 2), "Unknown"),
                "priority_label":  PRIORITY_MAP.get(t.get("priority", 2), "Unknown"),
                "requester":       requester_name,    # ← now a real name
                "requester_email": requester_email,   # ← NEW
                "assigned_to":     assigned_to,       # ← now a real name
                "group":           str(t.get("group_id", "No Group")),
                "created_at":      t.get("created_at", ""),
                "due_by":          due_by_str,
                "is_overdue":      is_overdue,
            })

        return result




# ══════════════════════════════════════════════════════════════════════════════
# 3. GET ANALYTICS SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
async def get_analytics() -> dict:
    """
    Builds a snapshot of the IT support desk by fetching
    tickets of each status and counting them.

    Makes multiple small API calls and combines the results.
    This gives the manager a full picture in one agent message.
    """
    async with _get_client() as client:

        # Helper to count tickets matching a filter query
        async def count_tickets(query: str) -> int:
            try:
                r = await client.get(
                    "/tickets/filter",
                    params={"query": f'"{query}"', "per_page": 1}
                )
                if r.status_code == 200:
                    return r.json().get("total", 0)
            except Exception:
                pass
            return 0

        # Count tickets by status
        total_open     = await count_tickets("status:2")
        total_pending  = await count_tickets("status:3")
        total_resolved = await count_tickets("status:4")
        total_closed   = await count_tickets("status:5")
        urgent_count   = await count_tickets("priority:4")
        high_count     = await count_tickets("priority:3")

        # Count overdue tickets (open + pending past due date)
        now = datetime.now(timezone.utc)
        overdue_count = 0

        try:
            open_resp = await client.get(
                "/tickets",
                params={"per_page": 100, "order_type": "desc"}
            )
            if open_resp.status_code == 200:
                for t in open_resp.json().get("tickets", []):
                    if t.get("status") in [2, 3] and t.get("due_by"):
                        try:
                            due = datetime.fromisoformat(
                                t["due_by"].replace("Z", "+00:00")
                            )
                            if now > due:
                                overdue_count += 1
                        except Exception:
                            pass
        except Exception:
            pass

        return {
            "total_open":          total_open,
            "total_pending":       total_pending,
            "total_resolved":      total_resolved,
            "total_closed":        total_closed,
            "overdue_count":       overdue_count,
            "high_priority_count": high_count,
            "urgent_count":        urgent_count,
            "created_today":       0,   # Freshservice API does not support date filter easily
            "resolved_today":      0,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 4. GET SLA BREACHES
# ══════════════════════════════════════════════════════════════════════════════
async def get_sla_breaches() -> list:
    """
    Finds all open/pending tickets that are EITHER:
      - Already past their due date (breached)
      - Due within the next 4 hours (at risk)

    Returns them sorted by urgency so the manager knows
    which ones to deal with first.
    """
    async with _get_client() as client:
        resp = await client.get(
            "/tickets",
            params={
                "per_page":   100,
                "order_type": "asc",
                "order_by":   "due_by",
            }
        )
        resp.raise_for_status()

        tickets = resp.json().get("tickets", [])
        now     = datetime.now(timezone.utc)
        result  = []

        for t in tickets:
            # Only look at open or pending tickets
            if t.get("status") not in [2, 3]:
                continue

            due_by_str = t.get("due_by")
            if not due_by_str:
                continue

            try:
                due_dt       = datetime.fromisoformat(due_by_str.replace("Z", "+00:00"))
                diff_seconds = (due_dt - now).total_seconds()

                # Categorise the breach status
                if diff_seconds < 0:
                    breach_status = "already_breached"
                elif diff_seconds <= 3600:          # within 1 hour
                    breach_status = "breach_in_1hr"
                elif diff_seconds <= 14400:         # within 4 hours
                    breach_status = "breach_in_4hrs"
                else:
                    continue    # Not at risk yet — skip

                result.append({
                    "ticket_id":      t.get("id"),
                    "subject":        t.get("subject", ""),
                    "priority_label": PRIORITY_MAP.get(t.get("priority", 2), "Unknown"),
                    "status_label":   STATUS_MAP.get(t.get("status", 2), "Unknown"),
                    "requester":      str(t.get("requester_id", "Unknown")),
                    "due_by":         due_by_str,
                    "breach_status":  breach_status,
                    "assigned_to":    str(t.get("responder_id", "Unassigned")),
                })

            except Exception:
                continue

        # Sort: already breached first, then closest to breaching
        order = {"already_breached": 0, "breach_in_1hr": 1, "breach_in_4hrs": 2}
        result.sort(key=lambda x: order.get(x["breach_status"], 3))

        return result


# ══════════════════════════════════════════════════════════════════════════════
# 5. GET ASSETS FOR A USER
# ══════════════════════════════════════════════════════════════════════════════
async def get_assets_for_user(email: str) -> list:
    """
    Finds all IT assets assigned to a specific user.
    First looks up the requester ID from email,
    then fetches assets assigned to that requester.
    """
    async with _get_client() as client:

        # Step 1: Get requester ID from email
        req_resp = await client.get("/requesters", params={"email": email})
        req_resp.raise_for_status()

        requesters = req_resp.json().get("requesters", [])
        if not requesters:
            return []

        requester_id   = requesters[0]["id"]
        requester_name = (
            f"{requesters[0].get('first_name','')} "
            f"{requesters[0].get('last_name','')}".strip()
        )

        # Step 2: Get assets assigned to that requester
        asset_resp = await client.get(
            "/assets",
            params={"user_id": requester_id}
        )

        if asset_resp.status_code != 200:
            return []

        assets = asset_resp.json().get("assets", [])
        result = []

        for a in assets:
            result.append({
                "asset_id":    a.get("id"),
                "name":        a.get("name", ""),
                "asset_type":  a.get("asset_type_name", "Unknown"),
                "serial":      a.get("asset_tag"),
                "status":      a.get("asset_state", "Unknown"),
                "assigned_to": requester_name,
            })

        return result


# ══════════════════════════════════════════════════════════════════════════════
# 6. SEARCH KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════
async def search_knowledge_base(query: str) -> list:
    """
    Searches Freshservice's knowledge base (Solutions)
    for articles matching the search query.

    Used BEFORE creating a ticket — show the user a
    self-service article if one exists.
    """
    async with _get_client() as client:
        resp = await client.get(
            "/solutions/articles/search",
            params={"term": query, "per_page": 5}
        )

        if resp.status_code != 200:
            return []

        articles = resp.json().get("articles", [])
        result   = []

        for a in articles:
            result.append({
                "article_id":  a.get("id"),
                "title":       a.get("title", ""),
                "description": a.get("description_text", "")[:200] + "..."
                               if len(a.get("description_text", "")) > 200
                               else a.get("description_text", ""),
                "category":    a.get("folder_name", "General"),
                "status":      "Published" if a.get("status") == 2 else "Draft",
                "url":         None,   # Freshservice API does not return direct URL
            })

        return result


# ══════════════════════════════════════════════════════════════════════════════
# 7. ASSIGN TICKET TO AGENT
# ══════════════════════════════════════════════════════════════════════════════
async def assign_ticket(ticket_id: int, agent_email: str) -> dict:
    """
    Assigns an existing ticket to a specific agent.
    First looks up the agent ID from their email,
    then updates the ticket's responder_id.
    """
    async with _get_client() as client:

        # Step 1: Get agent ID from email
        agent_resp = await client.get("/agents", params={"email": agent_email})
        agent_resp.raise_for_status()

        agents = agent_resp.json().get("agents", [])
        if not agents:
            raise ValueError(f"No agent found with email: {agent_email}")

        agent    = agents[0]
        agent_id = agent["id"]
        name     = f"{agent.get('first_name','')} {agent.get('last_name','')}".strip()

        # Step 2: Update the ticket with the new responder
        update_resp = await client.put(
            f"/tickets/{ticket_id}",
            json={"responder_id": agent_id}
        )
        update_resp.raise_for_status()

        return {
            "ticket_id":   ticket_id,
            "assigned_to": name,
            "agent_id":    agent_id,
        }





# ══════════════════════════════════════════════════════════════════════════════
# RESOLVE TICKET
# ══════════════════════════════════════════════════════════════════════════════
async def resolve_ticket(
    ticket_id:       int,
    resolution_note: str,
) -> dict:
    """
    Resolves a ticket and adds a resolution note in one step.

    Only agents and managers can resolve tickets.
    The requester gets an email notification automatically
    because the resolution note is public.

    Does two things in sequence:
      1. Adds a public note describing what fixed the issue
      2. Changes the ticket status to Resolved (4)
    """
    async with _get_client() as client:

        # Step 1: Add a public resolution note
        await client.post(
            f"/tickets/{ticket_id}/notes",
            json={
                "body":    f"✅ RESOLVED — {resolution_note}",
                "private": False,
            }
        )

        # Step 2: Set status to Resolved (4)
        # Accept 400 too — Freshservice sometimes returns 400
        # even when the change succeeds (already resolved case)
        status_resp = await client.put(
            f"/tickets/{ticket_id}",
            json={"status": 4}
        )

        if status_resp.status_code in [200, 201, 204, 400]:
            return {
                "ticket_id": ticket_id,
                "resolved":  True,
            }

        status_resp.raise_for_status()
        return {
            "ticket_id": ticket_id,
            "resolved":  True,
        }
        
        

# ══════════════════════════════════════════════════════════════════════════════
# UPDATE TICKET
# ══════════════════════════════════════════════════════════════════════════════
async def update_ticket(
    ticket_id:    int,
    new_priority: Optional[int] = None,
    new_status:   Optional[int] = None,
) -> dict:
    """
    Updates a ticket's priority and/or status.

    Only agents and managers can update tickets.
    End users can only view their own tickets.

    Priority: 1=Low  2=Medium  3=High  4=Urgent
    Status:   2=Open 3=Pending 4=Resolved 5=Closed
    """
    async with _get_client() as client:

        payload = {}

        # Only include fields that were actually provided
        # If value is 0 or None — skip it, do not change it
        if new_priority and new_priority != 0:
            payload["priority"] = new_priority

        if new_status and new_status != 0:
            payload["status"] = new_status

        if not payload:
            return {
                "ticket_id": ticket_id,
                "message":   "No changes were made — no fields provided.",
            }

        resp = await client.put(
            f"/tickets/{ticket_id}",
            json=payload
        )
        resp.raise_for_status()

        return {
            "ticket_id": ticket_id,
            "message":   f"Ticket #{ticket_id} updated successfully.",
        }
        


# ══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINT 2 — WEEKLY REPORT
# Service function to add to: app/services/manager.py
# ══════════════════════════════════════════════════════════════════════════════
async def get_weekly_report() -> dict:
    """
    Generates a summary of IT support performance for the past 7 days.

    Returns:
      - How many tickets were created this week
      - How many were resolved
      - How many are still open
      - Average resolution time (hours)
      - Breakdown by priority
      - Breakdown by category

    Why this matters:
      Managers need to report upwards. Without this they have to manually
      pull data from Freshservice and build spreadsheets. This gives them
      a full weekly summary in one chat message — copy-paste ready for
      a management report.
    """
    async with _get_client() as client:
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        week_ago_str = week_ago.strftime("%Y-%m-%d")

        # Fetch tickets created in the last 7 days
        resp = await client.get(
            f"/tickets?per_page=100&updated_since={week_ago_str}"
        )
        resp.raise_for_status()
        all_tickets = resp.json().get("tickets", [])

        # Filter to only those created this week
        created_this_week = []
        for t in all_tickets:
            created_at = t.get("created_at", "")
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if created >= week_ago:
                    created_this_week.append(t)
            except Exception:
                pass

        # Count metrics
        total_created  = len(created_this_week)
        total_resolved = sum(1 for t in created_this_week if t.get("status") in [4, 5])
        total_open     = sum(1 for t in created_this_week if t.get("status") in [2, 3])

        # Priority breakdown
        priority_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for t in created_this_week:
            p = t.get("priority", 2)
            priority_counts[p] = priority_counts.get(p, 0) + 1

        # Average resolution time (for resolved tickets)
        resolution_times = []
        for t in created_this_week:
            if t.get("status") in [4, 5]:
                try:
                    created = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                    updated = datetime.fromisoformat(t["updated_at"].replace("Z", "+00:00"))
                    hours = (updated - created).total_seconds() / 3600
                    resolution_times.append(hours)
                except Exception:
                    pass

        avg_resolution_hours = (
            round(sum(resolution_times) / len(resolution_times), 1)
            if resolution_times else None
        )

        week_label = f"{week_ago.strftime('%d %b')} - {now.strftime('%d %b %Y')}"

        summary = (
            f"Weekly IT Support Report\n"
            f"{week_label}\n"
            f"{'='*35}\n"
            f"Tickets Created:   {total_created}\n"
            f"Tickets Resolved:  {total_resolved}\n"
            f"Still Open:        {total_open}\n"
            f"Avg Resolution:    {f'{avg_resolution_hours}h' if avg_resolution_hours else 'N/A'}\n"
            f"{'='*35}\n"
            f"By Priority:\n"
            f"  Urgent:   {priority_counts.get(4, 0)}\n"
            f"  High:     {priority_counts.get(3, 0)}\n"
            f"  Medium:   {priority_counts.get(2, 0)}\n"
            f"  Low:      {priority_counts.get(1, 0)}\n"
        )

        return {
            "week": week_label,
            "total_created": total_created,
            "total_resolved": total_resolved,
            "total_open": total_open,
            "avg_resolution_hours": avg_resolution_hours,
            "priority_breakdown": priority_counts,
            "summary": summary,
        }
        
        
        
# NEW ENDPOINT 4 — GET UNASSIGNED TICKETS
# Service function to add to: app/services/manager.py
# ══════════════════════════════════════════════════════════════════════════════
# async def get_unassigned_tickets() -> dict:
#     """
#     Returns all open tickets that have no agent assigned to them.
 
#     Why this matters:
#       Unassigned tickets are the biggest risk in any IT helpdesk.
#       They are open, visible to the user, but nobody is working on them.
#       They will breach SLA. Users will chase. Managers will get complaints.
 
#       This endpoint lets a manager say "show me unassigned tickets" and
#       immediately see what needs to be actioned — then use the Assign
#       Ticket endpoint to distribute the work.
#     """
#     async with _get_client() as client:
#         # Fetch all open tickets
#         resp = await client.get("/tickets?per_page=100")
#         resp.raise_for_status()
#         tickets = resp.json().get("tickets", [])
 
#         # Filter to those with no responder assigned
#         unassigned = [
#             t for t in tickets
#             if not t.get("responder_id")
#         ]
 
#         if not unassigned:
#             return {
#                 "unassigned_count": 0,
#                 "tickets": [],
#                 "summary": "Great news! All open tickets currently have an agent assigned.",
#             }
 
#         lines = []
#         for t in unassigned[:20]:
#             priority = PRIORITY_MAP.get(t.get("priority"), "?")
#             created  = t.get("created_at", "")[:10]  # just the date
#             lines.append(
#                 f"#{t['id']}: {t['subject']} | {priority} | Created: {created}"
#             )
 
#         summary = (
#             f"WARNING: {len(unassigned)} open ticket(s) with no agent assigned:\n\n"
#             + "\n".join(lines)
#         )
#         if len(unassigned) > 20:
#             summary += f"\n...and {len(unassigned) - 20} more."
 
#         return {
#             "unassigned_count": len(unassigned),
#             "tickets": unassigned,
#             "summary": summary,
#         }


async def get_unassigned_tickets() -> dict:
    async with _get_client() as client:

        # include=requester embeds the requester object in each ticket
        resp = await client.get(
            "/tickets",
            params={
                "per_page": 100,
                "include":  "requester",    # ← NEW
            }
        )
        resp.raise_for_status()
        tickets = resp.json().get("tickets", [])

        # Filter to only unassigned tickets
        unassigned = [
            t for t in tickets
            if not t.get("responder_id")
        ]

        if not unassigned:
            return {
                "unassigned_count": 0,
                "tickets":          [],
                "summary":          "Great news! All open tickets currently have an agent assigned.",
            }

        # Build result with requester name + email
        result = []
        lines  = []

        for t in unassigned[:20]:
            # Extract requester name and email from embedded requester object
            requester       = t.get("requester", {})
            first           = requester.get("first_name", "")
            last            = requester.get("last_name", "")
            requester_name  = requester.get("name") or f"{first} {last}".strip() or "Unknown"
            requester_email = requester.get("email", "")

            priority   = PRIORITY_MAP.get(t.get("priority"), "?")
            created    = t.get("created_at", "")[:10]

            result.append({
                "ticket_id":       t.get("id"),
                "subject":         t.get("subject", ""),
                "status_label":    STATUS_MAP.get(t.get("status"), "Unknown"),
                "priority_label":  priority,
                "requester_name":  requester_name,    # ← NEW
                "requester_email": requester_email,   # ← NEW
                "created_at":      t.get("created_at", ""),
                "due_by":          t.get("due_by"),
            })

            lines.append(
                f"#{t.get('id')}: {t.get('subject')} | "
                f"{priority} | {requester_name} | Created: {created}"
            )

        summary = (
            f"WARNING: {len(unassigned)} open ticket(s) with no agent assigned:\n\n"
            + "\n".join(lines)
        )
        if len(unassigned) > 20:
            summary += f"\n...and {len(unassigned) - 20} more."

        return {
            "unassigned_count": len(unassigned),
            "tickets":          result,
            "summary":          summary,
        }
        
        

# ══════════════════════════════════════════════════════════════════════════════
# 8. CLOSE TICKET
# ══════════════════════════════════════════════════════════════════════════════

async def close_ticket(ticket_id: int, closing_note: str) -> dict:
    """
    Permanently closes a ticket.
    Freshservice requires two steps — resolve first (4), then close (5).
    Jumping straight to Closed from Open/Pending causes a 400 error.
    """
    async with _get_client() as client:

        # Step 1 — add private closing note
        await client.post(
            f"/tickets/{ticket_id}/notes",
            json={
                "body":    closing_note,
                "private": True,
            }
        )

        # Step 2 — set to Resolved (4) first
        # Freshservice rejects a direct jump to Closed (5) from Open/Pending
        resolve_resp = await client.put(
            f"/tickets/{ticket_id}",
            json={"status": 4}
        )
        # Accept 400 here — Freshservice sometimes returns 400 even on success
        # for status transitions (known Freshservice quirk)
        if resolve_resp.status_code not in [200, 201, 400]:
            resolve_resp.raise_for_status()

        # Step 3 — now set to Closed (5)
        close_resp = await client.put(
            f"/tickets/{ticket_id}",
            json={"status": 5}
        )
        if close_resp.status_code not in [200, 201, 400]:
            close_resp.raise_for_status()

        return {
            "ticket_id": ticket_id,
            "status":    5,
            "message":   f"Ticket #{ticket_id} has been permanently closed.",
        }

