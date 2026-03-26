from fastapi import APIRouter, Depends, File, UploadFile

from api.controllers.ingest_controller import IngestController
from api.dependencies import get_ingest_controller, get_manual_controller, get_manual_repository
from api.controllers.manual_controller import ManualController
from repositories.manual_repository import ManualRepository
from schemas.ingestion import DeleteManualSourceResponse, IngestManualResponse, ManualSourceResponse


router = APIRouter(tags=["ingestion"])


@router.post("/ingest-manual", response_model=IngestManualResponse)
async def ingest_manual(
    file: UploadFile = File(...),
    controller: IngestController = Depends(get_ingest_controller),
) -> IngestManualResponse:
    return await controller.ingest_manual(file)


@router.get("/manuals", response_model=list[ManualSourceResponse])
async def list_manuals(
    repo: ManualRepository = Depends(get_manual_repository),
) -> list[ManualSourceResponse]:
    rows = await repo.list_sources()
    return [
        ManualSourceResponse(
            source=r.source,
            category=r.category,
            chunk_count=r.chunk_count,
            ingested_at=r.ingested_at,
        )
        for r in rows
    ]


@router.delete("/manuals/{source}", response_model=DeleteManualSourceResponse)
async def delete_manual_source(
    source: str,
    controller: ManualController = Depends(get_manual_controller),
) -> DeleteManualSourceResponse:
    return await controller.delete_source(source=source)
