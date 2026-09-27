from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=100)
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)

    @field_validator("code", "title", mode="before")
    @classmethod
    def strip_required_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class ProjectResponse(BaseModel):
    id: str
    code: str
    title: str
    description: Optional[str] = None
    status: str
    department_id: Optional[str] = None
    created_by_id: str
    created_at: datetime
    document_count: int = 0

    model_config = ConfigDict(from_attributes=True)
