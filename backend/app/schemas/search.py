from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=10000, description="Search query or technical tender clause")
    search_type: Literal["exact", "keyword", "semantic", "hybrid"] = Field("hybrid", description="Search strategy")
    category_filter: Optional[str] = Field(None, max_length=100)
    top_k: int = Field(5, ge=1, le=20)
    min_score: float = Field(0.35, ge=0.0, le=1.0)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Search query must contain at least two non-whitespace characters")
        return value

class SearchResultItem(BaseModel):
    standard_id: str
    standard_code: str
    title: str
    category: str
    status: str
    current_version: Optional[str] = None
    score: float
    match_type: str
    explanation: str

    model_config = ConfigDict(from_attributes=True)

class SearchResponse(BaseModel):
    query: str
    search_type: str
    total_results: int
    results: List[SearchResultItem]
    ir_metrics: Optional[Dict[str, float]] = None
