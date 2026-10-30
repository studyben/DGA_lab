"""Retained original receipt state machine; the provider call is outside DB transactions."""
from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4
from sqlalchemy import text
from dga.shared.auth.public import require_permission
from dga.shared.files import ObjectStorageError
from .import_contracts import XLSX_TYPE, CSV_TYPE, MAX_FILE_BYTES
from .imports import dumped, fail, ImportAction


FILE_COLUMNS = ('id', 'batch_id', 'role', 'state', 'active', 'filename', 'content_type',
                'byte_size', 'sha256', 'received_by', 'reserved_at', 'received_at', 'failure_code')


class OriginalReceipts:
    def __init__(self, owner):
        self.owner = owner

    def receive(self, actor, batch_id, *, idempotency_key, role, filename, content_type, content):
        o = self.owner
        require_permission(actor, 'laboratory.write')
        batch_id = o._uuid(batch_id)
        if (not isinstance(filename, str) or not 1 <= len(filename) <= 255
                or filename in ('.', '..') or any(ord(x) < 32 or x in '/\\:' for x in filename)):
            fail('invalid_import_filename')
        if role not in ('WORKBOOK', 'SAMPLES', 'TESTS'):
            fail('import_role_not_supported', 415)
        expected_type = XLSX_TYPE if role == 'WORKBOOK' else CSV_TYPE
        suffix = '.xlsx' if role == 'WORKBOOK' else '.csv'
        if not filename.lower().endswith(suffix):
            fail('invalid_import_filename')
        if content_type != expected_type:
            fail('import_content_type', 415)
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_FILE_BYTES:
            fail('import_file_size', 413)
        payload = dict(batch_id=str(batch_id), role=role, filename=filename,
                       content_type=content_type, byte_size=len(content), sha256=sha256(content).hexdigest())
        upload = False
        with o.engine.begin() as c:
            key, fingerprint, previous = o._intent(c, actor, idempotency_key, 'RECEIVE', payload)
            batch = o._locked(c, batch_id)
            required = ('WORKBOOK',) if batch['input_format'] == 'XLSX' else ('SAMPLES', 'TESTS')
            if role not in required:
                fail('import_role_not_supported', 415)
            if previous:
                file_id = previous['file_id']
                if previous['state'] != 'COMPLETED':
                    if previous['state'] == 'PENDING' and previous['lease_expires_at'] > o.clock():
                        return dict(operation=o._op_view(previous), file=o._file(c, batch_id, file_id),
                                    batch_revision=batch['revision'], in_flight=True)
                    token = uuid4()
                    c.execute(text('''UPDATE lab_import_operations SET state='PENDING',lease_token=:token,
                        lease_expires_at=:lease,error_code=NULL,updated_at=:now WHERE id=:id'''),
                        dict(id=previous['id'], token=token, lease=o.clock()+timedelta(seconds=60), now=o.clock()))
                    c.execute(text("UPDATE lab_import_files SET state='PENDING',failure_code=NULL WHERE id=:id"), {'id': file_id})
                    upload = True
            else:
                file_id, operation_id, token, now = uuid4(), uuid4(), uuid4(), o.clock()
                c.execute(text('''INSERT INTO lab_import_operations
                    (id,actor_id,operation_key,action,batch_id,request_digest,state,request_snapshot,
                     lease_token,lease_expires_at,created_at,updated_at)
                    VALUES (:id,:actor,:key,'RECEIVE',:batch,:digest,'PENDING',CAST(:payload AS jsonb),
                            :token,:lease,:now,:now)'''),
                    dict(id=operation_id, actor=actor.user_id, key=key, batch=batch_id, digest=fingerprint,
                         payload=dumped(payload), token=token, lease=now+timedelta(seconds=60), now=now))
                c.execute(text('''INSERT INTO lab_import_files
                    (id,batch_id,role,state,filename,content_type,byte_size,sha256,object_key,operation_id,received_by,reserved_at)
                    VALUES (:id,:batch,:role,'PENDING',:name,:type,:size,:sha,:object,:operation,:actor,:now)'''),
                    dict(id=file_id, batch=batch_id, role=role, name=filename, type=content_type, size=len(content),
                         sha=payload['sha256'], object=f'lab-imports/{batch_id}/{file_id}/source',
                         operation=operation_id, actor=actor.user_id, now=now))
                c.execute(text('UPDATE lab_import_operations SET file_id=:file WHERE id=:id'),
                          dict(id=operation_id, file=file_id))
                o.audit.append(c, actor, ImportAction.FILE_RESERVED, entity_id=batch_id,
                               details=dict(file_id=str(file_id), role=role, sha256=payload['sha256'], byte_size=len(content)))
                upload = True
            internal = c.execute(text('SELECT object_key FROM lab_import_files WHERE id=:id'),
                                 {'id': file_id}).scalar_one()
        # Reservation must have a known COMMIT before any external write.
        if upload:
            try:
                o.files.put(object_key=internal, content=content, content_type=content_type)
            except Exception as error:
                with o.engine.begin() as c:
                    _, _, current = o._intent(c, actor, key, 'RECEIVE', payload)
                    o._locked(c, batch_id)
                    if current['state'] == 'PENDING' and current['lease_token'] == token:
                        c.execute(text("""UPDATE lab_import_operations SET state='RETRYABLE',lease_token=NULL,
                            lease_expires_at=NULL,error_code='import_storage_unavailable',updated_at=:now WHERE id=:id"""),
                            dict(id=current['id'], now=o.clock()))
                        c.execute(text("""UPDATE lab_import_files SET state='RETRYABLE',
                            failure_code='import_storage_unavailable' WHERE id=:id"""), {'id': file_id})
                        o.audit.append(c, actor, ImportAction.FILE_FAILED, entity_id=batch_id, result='FAILURE',
                                       details=dict(file_id=str(file_id), code='import_storage_unavailable'))
                raise ObjectStorageError('import_storage_unavailable') from error
            with o.engine.begin() as c:
                _, _, current = o._intent(c, actor, key, 'RECEIVE', payload)
                batch = o._locked(c, batch_id)
                if (current['state'] != 'PENDING' or current['lease_token'] != token
                        or current['lease_expires_at'] <= o.clock()):
                    fail('import_receipt_claim_stale', 409)
                before = o._snapshot(c, batch)
                occupied = c.execute(text('SELECT id FROM lab_import_files WHERE batch_id=:batch AND role=:role AND active'),
                                     dict(batch=batch_id, role=role)).scalar()
                c.execute(text("""UPDATE lab_import_files SET state='RECEIVED',active=:active,
                    received_at=:now,failure_code=NULL WHERE id=:id"""),
                    dict(id=file_id, active=occupied is None, now=o.clock()))
                revision = o._changed(c, batch, actor, 'Original file receipt confirmed', before,
                                      o._snapshot(c, batch))
                result = dict(outcome='FILE_RECEIVED', batch_id=str(batch_id), file_id=str(file_id),
                              applied_revision=revision)
                c.execute(text("""UPDATE lab_import_operations SET state='COMPLETED',result=CAST(:result AS jsonb),
                    lease_token=NULL,lease_expires_at=NULL,error_code=NULL,updated_at=:now WHERE id=:id"""),
                    dict(id=current['id'], result=dumped(result), now=o.clock()))
                o.audit.append(c, actor, ImportAction.FILE_RECEIVED, entity_id=batch_id,
                               details=dict(file_id=str(file_id), revision=revision, active=occupied is None))
        with o.engine.begin() as c:
            o._authorize(c, actor)
            file = o._file(c, batch_id, file_id)
        operation = o.operation(actor, key)
        return dict(operation=operation, file=file,
                    batch_revision=operation['result']['applied_revision'], in_flight=False)

