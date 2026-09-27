from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


ReviewActionName = Literal["accept", "reject", "flag", "comment", "request_review"]


class RecommendationCreateRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=36)
    document_id: str = Field(..., min_length=1, max_length=36)
    standard_id: str = Field(..., min_length=1, max_length=36)
    source_excerpt: str = Field(..., min_length=2, max_length=10000)

    @field_validator("source_excerpt")
    @classmethod
    def normalize_excerpt(cls, value: str) -> str:
        return value.strip()


class ReviewActionRequest(BaseModel):
    action: ReviewActionName
    comments: Optional[str] = Field(None, max_length=5000)
    reason_code: Optional[str] = Field(None, max_length=100)

    @field_validator("comments", "reason_code", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value
