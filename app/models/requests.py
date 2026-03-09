from pydantic import BaseModel, Field
from typing import Optional
from enum import IntEnum


# ── Enums ──────────────────────────────────────────────────────────────────────

class Priority(IntEnum):
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3
    URGENT = 4


class TicketStatus(IntEnum):
    OPEN     = 2
    PENDING  = 3
    RESOLVED = 4
    CLOSED   = 5


# ── Ticket Requests ────────────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    """
    Payload Power Automate sends when creating a new ticket.
    All fields validated automatically by Pydantic before hitting Freshservice.
    """
    subject:     str              = Field(..., min_length=5,  max_length=255,
                                          description="Short title of the issue")
    description: str              = Field(..., min_length=10,
                                          description="Detailed description of the issue")
    email:       str              = Field(...,
                                          description="Requester email address")
    priority:    Priority         = Field(Priority.MEDIUM,
                                          description="1=Low 2=Medium 3=High 4=Urgent")
    category:    Optional[str]    = Field(None,
                                          description="e.g. Hardware, Software, Network")
    urgency:     Optional[int]    = Field(1, ge=1, le=4,
                                          description="1=Low 2=Medium 3=High 4=Urgent")

    model_config = {
        "json_schema_extra": {
            "example": {
                "subject":     "Laptop screen flickering",
                "description": "My laptop screen has been flickering since this morning after a Windows update.",
                "email":       "testuser@dummycompany.com",
                "priority":    2,
                "category":    "Hardware",
            }
        }
    }


class UpdateTicketRequest(BaseModel):
    """
    Payload for updating an existing ticket.
    All fields are optional — only send what you want to change.
    """
    priority: Optional[Priority]     = Field(None, description="New priority level")
    status:   Optional[TicketStatus] = Field(None, description="New status")

    model_config = {
        "json_schema_extra": {
            "example": {
                "priority": 3,
                "status":   3,
            }
        }
    }


class AddNoteRequest(BaseModel):
    """
    Payload for adding a note/comment to an existing ticket.
    """
    body:    str  = Field(..., min_length=5, description="The note text")
    private: bool = Field(True, description="True = internal note, False = reply to requester")

    model_config = {
        "json_schema_extra": {
            "example": {
                "body":    "User called to follow up. Issue is still happening after restart.",
                "private": True,
            }
        }
    }
