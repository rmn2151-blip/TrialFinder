"""Pydantic schemas for the conversational intake agent."""

from typing import Optional

from pydantic import BaseModel, Field


class IntakeTurn(BaseModel):
    role: str = Field(..., description="'assistant' or 'user'")
    content: str


class IntakeStartResponse(BaseModel):
    session_id: str
    question: str = Field(..., description="The first question to ask the user")


class IntakeAnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(..., max_length=2000)


class IntakeAnswerResponse(BaseModel):
    session_id: str
    question: Optional[str] = Field(
        default=None, description="Next question, or null when the intake is complete"
    )
    complete: bool = Field(default=False)
    profile: Optional[dict] = Field(
        default=None,
        description="When complete=true, the structured PatientProfile payload "
        "ready to POST to /api/match",
    )
    turns_so_far: int = Field(default=0)
    max_turns: int = Field(default=10)
