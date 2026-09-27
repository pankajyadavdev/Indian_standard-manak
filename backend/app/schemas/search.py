from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Search query or technical tender clause")
    search_type: str = Field("hybrid", description="exact, keyword, semantic, or hybrid")
    category_filter: Optional[str] = None
    top_k: int = Field(5, ge=1, le=20)
    min_score: float = Field(0.35, ge=0.0, le=1.0)

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
