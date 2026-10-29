"""Transport-only adapter for the asset import public application interface."""
from uuid import UUID
from typing import Literal
from urllib.parse import quote
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from dga.shared.auth.public import require_permission
from .imports import AssetImports, XLSX_TYPE
from .import_workbook import MAX_BYTES
from .site_import_workbook import MAX_BYTES as SITE_MAX_BYTES
from .lifecycle import fail


class PublishInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    validation_revision: StrictInt = Field(ge=1)
    acknowledge_warnings: StrictBool = False
    idempotency_key: str | None = Field(default=None,min_length=36,max_length=36)
    acknowledged_warning_ids: list[str] = Field(default_factory=list,max_length=3000)


class RevisionChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sheet: Literal['Customers','Sites']
    row: StrictInt = Field(ge=2)
    values: dict = Field(max_length=15)


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: StrictInt = Field(ge=0)
    changes: list[RevisionChange] = Field(min_length=1,max_length=1000)
    reason: str = Field(min_length=1,max_length=1000)
    idempotency_key: str = Field(min_length=36,max_length=36)


def import_router(imports: AssetImports, actor_dependency, mutation_actor):
    def read_call(command,*args,**kwargs):
        try:
            return command(*args,**kwargs)
        except SQLAlchemyError:
            fail('import_read_unavailable',503)

    def no_store(response: Response):
        response.headers['Cache-Control'] = 'no-store'
    router = APIRouter(prefix='/api/assets/imports', dependencies=[Depends(no_store)])

    @router.get('/template')
    def template(format_version: int = Query(default=1,ge=1,le=2), mode: Literal['ASSETS','SITES'] = 'ASSETS', actor=Depends(actor_dependency)):
        return Response(read_call(imports.template,actor,format_version=format_version,mode=mode), media_type=XLSX_TYPE,
                        headers={'Content-Disposition': f'attachment; filename="asset-import-v{format_version}.xlsx"', 'Cache-Control': 'no-store'})

    @router.get('')
    def batches(query: str = Query(default='', max_length=200), page: int = Query(default=1, ge=1, le=100000), actor=Depends(actor_dependency)):
        return read_call(imports.list_batches,actor,query=query,page=page)

    @router.post('', status_code=201)
    async def submit(request: Request, filename: str = Query(min_length=1, max_length=200), format_version: int = Query(default=1,ge=1,le=2), mode: Literal['ASSETS','SITES'] = 'ASSETS', idempotency_key: str | None = Header(default=None,alias='Idempotency-Key',max_length=36), actor=Depends(mutation_actor)):
        require_permission(actor, 'assets.import')
        if request.headers.get('content-type', '').split(';')[0].lower() != XLSX_TYPE:
            fail('invalid_import_content_type', 415)
        content = bytearray()
        async for part in request.stream():
            if len(content) + len(part) > (SITE_MAX_BYTES if format_version==2 else MAX_BYTES):
                fail('import_file_size', 413)
            content.extend(part)
        try:
            return await run_in_threadpool(imports.submit, actor, filename=filename, content=bytes(content),format_version=format_version,mode=mode,idempotency_key=idempotency_key)
        except SQLAlchemyError:
            fail('import_submit_unavailable', 503)

    @router.get('/operations/{key}')
    def operation(key: UUID, actor=Depends(actor_dependency)):
        return read_call(imports.operation,actor,str(key))

    @router.get('/{batch_id}/source')
    def source(batch_id: UUID, actor=Depends(actor_dependency)):
        source=read_call(imports.source_file,actor,batch_id)
        return Response(source['content'],media_type=XLSX_TYPE,headers={
            'Content-Disposition': "attachment; filename=asset-import.xlsx; filename*=UTF-8''"+quote(source['filename'],safe=''),
            'Cache-Control':'no-store'})

    @router.get('/{batch_id}/revisions')
    def revision_history(batch_id: UUID,page: int = Query(default=1,ge=1,le=100000),actor=Depends(actor_dependency)):
        return read_call(imports.revision_history,actor,batch_id,page=page)

    @router.post('/{batch_id}/revisions')
    def revise(batch_id: UUID,body: RevisionInput,actor=Depends(mutation_actor)):
        try:
            return imports.revise(actor,batch_id,**body.model_dump())
        except SQLAlchemyError:
            fail('import_revision_unavailable',503)

    @router.get('/{batch_id}')
    def preview(batch_id: UUID, page: int = Query(default=1,ge=1,le=100000), actor=Depends(actor_dependency)):
        return read_call(imports.get,actor,batch_id,page=page)

    @router.post('/{batch_id}/publish')
    def publish(batch_id: UUID, body: PublishInput, actor=Depends(mutation_actor)):
        try:
            return imports.publish(actor, batch_id, **body.model_dump())
        except SQLAlchemyError:
            # Never return SQL/payload details. A retry must reload the retained batch.
            fail('import_publish_unavailable', 503)

    return router
