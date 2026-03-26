from __future__ import annotations

from repositories.manual_repository import ManualRepository
from schemas.ingestion import DeleteManualSourceResponse


class ManualService:
    def __init__(self, manual_repository: ManualRepository) -> None:
        self.manual_repository = manual_repository

    async def delete_source(self, *, source: str) -> DeleteManualSourceResponse:
        deleted_chunks = await self.manual_repository.delete_by_source(source=source)
        return DeleteManualSourceResponse(source=source, deleted_chunks=deleted_chunks)

