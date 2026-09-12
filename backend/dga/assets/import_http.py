"""Transport-only adapter for the asset import public application interface."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from dga.shared.auth.public import require_permission
from .imports import AssetImports, XLSX_TYPE
from .import_workbook import MAX_BYTES
from .lifecycle import fail


class PublishInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    validation_revision: StrictInt = Field(ge=1)
    acknowledge_warnings: StrictBool = False


def import_router(imports: AssetImports, actor_dependency, mutation_actor):
    def no_store(response: Response):
        response.headers['Cache-Control'] = 'no-store'
    router = APIRouter(prefix='/api/assets/imports', dependencies=[Depends(no_store)])

    @router.get('/template')
    def template(actor=Depends(actor_dependency)):
        return Response(imports.template(actor), media_type=XLSX_TYPE,
                        headers={'Content-Disposition': 'attachment; filename="asset-import-v1.xlsx"', 'Cache-Control': 'no-store'})

    @router.get('')
    def batches(query: str = Query(default='', max_length=200), page: int = Query(default=1, ge=1, le=100000), actor=Depends(actor_dependency)):
        return imports.list_batches(actor, query=query, page=page)

    @router.post('', status_code=201)
    async def submit(request: Request, filename: str = Query(min_length=1, max_length=200), actor=Depends(mutation_actor)):
        require_permission(actor, 'assets.import')
        if request.headers.get('content-type', '').split(';')[0].lower() != XLSX_TYPE:
            fail('invalid_import_content_type', 415)
        content = bytearray()
        async for part in request.stream():
            if len(content) + len(part) > MAX_BYTES:
                fail('import_file_size', 413)
            content.extend(part)
        return await run_in_threadpool(imports.submit, actor, filename=filename, content=bytes(content))

    @router.get('/{batch_id}')
    def preview(batch_id: UUID, actor=Depends(actor_dependency)):
        return imports.get(actor, batch_id)

    @router.post('/{batch_id}/publish')
    def publish(batch_id: UUID, body: PublishInput, actor=Depends(mutation_actor)):
        try:
            return imports.publish(actor, batch_id, **body.model_dump())
        except SQLAlchemyError:
            # Never return SQL/payload details. A retry must reload the retained batch.
            fail('import_publish_unavailable', 503)

    return router
