from datetime import datetime

from pydantic import BaseModel


class IngestManualResponse(BaseModel):
    source: str
    chunks_saved: int
    category: str


class ManualSourceResponse(BaseModel):
    source: str
    category: str
    chunk_count: int
    ingested_at: datetime


class DeleteManualSourceResponse(BaseModel):
    source: str
    deleted_chunks: int
