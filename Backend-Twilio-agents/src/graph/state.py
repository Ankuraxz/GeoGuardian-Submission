# src/graph/state.py
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional
from datetime import datetime

class CallState(BaseModel):
    """
    Represents the state of an active emergency call session.
    Tracks real-time conversation state and media stream metadata.
    """
    client_id: str = Field(..., description="Unique identifier for the client connection")
    transcript_saved: bool = Field(
        default=False,
        description="Flag indicating if transcript has been persisted"
    )
    stream_sid: Optional[str] = Field(
        default=None,
        description="Twilio media stream identifier"
    )
    transcripts: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of conversation messages with role/text/timestamp"
    )
    latest_media_timestamp: int = Field(
        default=0,
        ge=0,
        description="Last received media packet timestamp from Twilio"
    )
    mark_queue: List[str] = Field(
        default_factory=list,
        description="Queue of Twilio mark events for synchronization"
    )
    current_user_input: str = Field(
        default="",
        max_length=500,
        description="Current partial user input being processed"
    )
    tool_calls: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Pending LangChain tool executions"
    )
    call_ended: bool = Field(
        default=False,
        description="Flag indicating if call was properly terminated"
    )
    escalated: bool = Field(
        default=False,
        description="Flag indicating emergency escalation status"
    )

    @validator('transcripts')
    def validate_transcripts(cls, v):
        for msg in v:
            if 'role' not in msg or 'text' not in msg:
                raise ValueError("Transcript items must contain 'role' and 'text'")
        return v

class TicketState(BaseModel):
    """
    Tracks state through the ticket creation workflow
    """
    transcripts: List[Dict[str, str]] = Field(
        ...,
        description="Full conversation transcript for ticket creation"
    )
    completion: Optional[str] = Field(
        default=None,
        description="Raw GPT-4 completion output"
    )
    parsed_response: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Processed ticket data structure"
    )
    error: Optional[Dict[str, str]] = Field(
        default=None,
        description="Error details if workflow failed"
    )
    status: str = Field(
        default="pending",
        description="Workflow state: pending/processing/completed/failed"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Initial workflow creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Last state update timestamp"
    )

    @validator('status')
    def validate_status(cls, v):
        allowed = ["pending", "processing", "completed", "failed"]
        if v not in allowed:
            raise ValueError(f"Invalid status {v}. Must be one of {allowed}")
        return v

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
        json_schema_extra = {
            "example": {
                "transcripts": [{"role": "user", "text": "Help! There's a fire!"}],
                "status": "processing",
                "created_at": "2024-02-20T12:34:56Z",
                "updated_at": "2024-02-20T12:35:00Z"
            }
        }