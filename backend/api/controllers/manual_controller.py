from fastapi import HTTPException

from services.manual_service import ManualService
from schemas.ingestion import DeleteManualSourceResponse


class ManualController:
    def __init__(self, manual_service: ManualService) -> None:
        self.manual_service = manual_service

    async def delete_source(self, source: str) -> DeleteManualSourceResponse:
        try:
            return await self.manual_service.delete_source(source=source)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

