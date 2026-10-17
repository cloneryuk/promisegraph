from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class DocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=24000)
    source_type: Literal["meeting", "ticket", "chat"]
    author_id: str
    timestamp: datetime
    timezone: str = "Asia/Kolkata"

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, v):
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("Include the document's timezone offset.")
        return v


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["deadline", "forecast", "requires"]
    subject: str
    object: str = ""
    date_expression: str = ""
    quote: str = Field(min_length=1)
    polarity: Literal["affirmed", "negated", "tentative"] = "affirmed"
    replaces_date_expression: str = ""


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[Candidate] = Field(default_factory=list, max_length=80)


class ReviewInput(BaseModel):
    action: Literal["accept", "reject"]
    expected_old_id: str = ""
    confirm_replacement: bool = False
    reason: str = Field(default="", max_length=500)


class AskInput(BaseModel):
    question: str = Field(
        default="Which commitments have deadline conflicts?", max_length=1000
    )
    mode: Literal["live", "rehearsal"] = "live"
    scope: list[str] = Field(default_factory=list, max_length=20)


class DemoInput(BaseModel):
    mode: Literal["live", "rehearsal"] = "rehearsal"
    include_revision: bool = False
