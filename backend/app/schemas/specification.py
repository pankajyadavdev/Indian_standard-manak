from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.services.entity_extractor import SpecificationEntities

class SpecificationExtractionRequest(BaseModel):
    document_id: Optional[str] = Field(None, max_length=36)
    custom_text: Optional[str] = Field(None, max_length=250000)

class SpecificationExtractionResponse(BaseModel):
    document_id: Optional[str] = None
    entities: SpecificationEntities
    total_entities_found: int
    standards_matched_count: int

    model_config = ConfigDict(from_attributes=True)
