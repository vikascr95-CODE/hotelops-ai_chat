from typing import Literal
from pydantic import BaseModel, Field, field_validator

DepartmentIntent = Literal["housekeeping", "maintenance", "reservations", "room_service", "front_office", "concierge", "accounts", "security", "other"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

class GuestIntent(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3, max_length=1000)
    intent_type: DepartmentIntent
    room_number: str | None = Field(default=None, max_length=30)
    priority: Priority = "MEDIUM"

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text cannot be blank")
        return value

class ExtractionResult(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)
    needs_human: bool = False
    tasks: list[GuestIntent] = Field(default_factory=list, max_length=20)
