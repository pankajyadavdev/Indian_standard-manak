from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.services.entity_extractor import SpecificationEntities

class SpecificationExtractionRequest(BaseModel):
    document_id: Optional[str] = None
    custom_text: Optional[str] = None

class SpecificationExtractionResponse(BaseModel):
    document_id: Optional[str] = None
    entities: SpecificationEntities
    total_entities_found: int
    standards_matched_count: int

    model_config = ConfigDict(from_attributes=True)
