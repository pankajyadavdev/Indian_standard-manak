from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class DocumentChunkResponse(BaseModel):
    chunk_index: int
    text: str
    page_number: int
    word_count: int

    model_config = ConfigDict(from_attributes=True)

class DocumentResponse(BaseModel):
    id: str
    project_id: str
    tender_id: Optional[str] = None
    filename: str
    file_type: str
    file_size_bytes: int
    file_hash_sha256: str
    processing_status: str
    ocr_applied: bool
    total_pages: int
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(DocumentResponse):
    extracted_text_preview: Optional[str] = None
    total_chunks: int = 0
