"""Bounded transport adapter for the laboratory-owned original staging facade."""
import json
from typing import Literal
from uuid import UUID
from urllib.parse import quote
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response, JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from dga.shared.auth.public import require_permission
from .imports import fail
from .import_contracts import MAX_FILE_BYTES, MAX_REQUEST_BYTES, CreateImport, ReviseImport


def import_router(imports, actor_dependency, mutation_actor):
    router = APIRouter(prefix='/api/laboratory/imports')

    def call(command, *args, writing=False, **kwargs):
        try:
            return command(*args, **kwargs)
        except (SQLAlchemyError, ConnectionError):
            # A database COMMIT can have succeeded. Retain/query the original key.
            fail('import_write_unknown' if writing else 'import_read_unavailable', 503)

    async def bounded(request, limit):
        data = bytearray()
        async for part in request.stream():
            if len(data) + len(part) > limit:
                fail('import_file_size' if limit == MAX_FILE_BYTES else 'import_request_size', 413)
            data.extend(part)
        return bytes(data)

    async def command_body(request, model, actor, key, action, batch_id=None):
        if request.headers.get('content-type', '').split(';')[0].lower() != 'application/json':
            fail('import_content_type', 415)
        data = await bounded(request, MAX_REQUEST_BYTES)
        try:
            value = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(value, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            # A malformed/unproven response never grants permission to replace an intent.
            fail('invalid_import_input')
        try:
            return model.model_validate(value).model_dump(mode='json', exclude_unset=True)
        except ValidationError:
            operation = await run_in_threadpool(call, imports.reject_input, actor,
                idempotency_key=str(key), action=action, request=value, batch_id=batch_id, writing=True)
            return JSONResponse(dict(code='invalid_import_input', disposition='DURABLE_REJECTED',
                                     operation=operation), status_code=422, headers={'Cache-Control':'no-store'})

    def download(file):
        return Response(file['content'], media_type=file['content_type'], headers={
            'Content-Disposition': "attachment; filename=lab-import-source; filename*=UTF-8''"+quote(file['filename'], safe=''),
            'Cache-Control':'private, no-store', 'X-Content-Type-Options':'nosniff'})

    @router.get('/template')
    def template(format: Literal['XLSX','CSV_PAIR']='XLSX', example: bool=False, version: int=1,
                 actor=Depends(actor_dependency)):
        return download(call(imports.template, actor, format=format, example=example, version=version))

    @router.get('/sources')
    def sources(query: str=Query(default='',max_length=200), exact_name: str|None=Query(default=None,min_length=1,max_length=200),
                page: int=Query(default=1,ge=1,le=100000), actor=Depends(actor_dependency)):
        return JSONResponse(call(imports.source_labs, actor, query=query, exact_name=exact_name, page=page),
                            headers={'Cache-Control':'no-store'})

    @router.get('/operations/{key}')
    def operation(key: UUID, actor=Depends(actor_dependency)):
        return JSONResponse(call(imports.operation, actor, str(key)), headers={'Cache-Control':'no-store'})

    @router.get('')
    def batches(q: str=Query(default='',max_length=200), state: str|None=None, purpose: str|None=None,
                created_from: str|None=None, created_to: str|None=None, actor_id: UUID|None=None,
                source_lab_id: UUID|None=None, page: int=Query(default=1,ge=1,le=100000),
                actor=Depends(actor_dependency)):
        return JSONResponse(call(imports.list_batches, actor, q=q, state=state, purpose=purpose,
            created_from=created_from, created_to=created_to, actor_id=actor_id, source_lab_id=source_lab_id,
            page=page), headers={'Cache-Control':'no-store'})

    @router.post('', status_code=201)
    async def create(request: Request, key: UUID=Header(alias='Idempotency-Key'), actor=Depends(mutation_actor)):
        require_permission(actor, 'laboratory.write')
        body = await command_body(request, CreateImport, actor, key, 'CREATE')
        if isinstance(body, Response):
            return body
        value = await run_in_threadpool(call, imports.create, actor, idempotency_key=str(key), writing=True, **body)
        return JSONResponse(value,status_code=201,headers={'Cache-Control':'no-store'})

    @router.get('/{batch_id}')
    def detail(batch_id: UUID, actor=Depends(actor_dependency)):
        return JSONResponse(call(imports.get, actor, batch_id), headers={'Cache-Control':'no-store'})

    @router.get('/{batch_id}/files')
    def files(batch_id: UUID,page: int=Query(default=1,ge=1,le=100000),actor=Depends(actor_dependency)):
        return JSONResponse(call(imports.list_files, actor, batch_id, page=page),headers={'Cache-Control':'no-store'})

    @router.post('/{batch_id}/files')
    async def receive(batch_id: UUID, request: Request, role: Literal['WORKBOOK','SAMPLES','TESTS'],
                      filename: str=Query(min_length=1,max_length=255),
                      key: UUID=Header(alias='Idempotency-Key'), actor=Depends(mutation_actor)):
        require_permission(actor, 'laboratory.write')
        content = await bounded(request,MAX_FILE_BYTES)
        value = await run_in_threadpool(call,imports.receive_file,actor,batch_id,idempotency_key=str(key),
            role=role,filename=filename,content_type=request.headers.get('content-type',''),content=content,writing=True)
        return JSONResponse(value,status_code=202 if value.get('in_flight') else 201,headers={'Cache-Control':'no-store'})

    @router.get('/{batch_id}/files/{file_id}/original')
    def original(batch_id: UUID,file_id: UUID,actor=Depends(actor_dependency)):
        return download(call(imports.original,actor,batch_id,file_id))

    @router.get('/{batch_id}/revisions')
    def history(batch_id: UUID,page: int=Query(default=1,ge=1,le=100000),actor=Depends(actor_dependency)):
        return JSONResponse(call(imports.revision_history,actor,batch_id,page=page),headers={'Cache-Control':'no-store'})

    @router.post('/{batch_id}/revisions')
    async def revise(batch_id: UUID,request: Request,key: UUID=Header(alias='Idempotency-Key'),actor=Depends(mutation_actor)):
        require_permission(actor,'laboratory.write')
        body = await command_body(request, ReviseImport, actor, key, 'REVISE', batch_id)
        if isinstance(body, Response):
            return body
        value = await run_in_threadpool(call,imports.revise,actor,batch_id,idempotency_key=str(key),writing=True,**body)
        return JSONResponse(value,headers={'Cache-Control':'no-store'})

    return router




