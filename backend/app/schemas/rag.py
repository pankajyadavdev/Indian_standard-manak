from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class EvidenceItem(BaseModel):
    source: str
    snippet: str
    confidence: float
    clause: Optional[str] = None

class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Technical specification or compliance query")
    document_id: Optional[str] = None
    project_id: Optional[str] = None

class RAGQueryResponse(BaseModel):
    query: str
    explanation: str
    is_verified: bool
    evidence: List[EvidenceItem]
    recommended_standards: List[str]

    model_config = ConfigDict(from_attributes=True)
