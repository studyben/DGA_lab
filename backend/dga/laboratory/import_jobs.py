"""Laboratory-owned durable validation job state; no external calls under batch locks."""
import re
from uuid import uuid4
from pydantic import ValidationError
from sqlalchemy import text
from dga.shared.auth.public import require_permission
from .errors import LaboratoryError
from .import_contracts import ValidationInput, MAX_FILE_BYTES
from .imports import dumped, digest, fail, ImportAction

JOB_COLUMNS = ('id','batch_id','input_revision','state','phase','progress_done','progress_total',
               'attempt','error_code','created_at','started_at','completed_at')


class ValidationJobs:
    def __init__(self, owner):
        self.o=owner

    @staticmethod
    def view(row):
        import json
        result=json.loads(dumped({k:row[k] for k in JOB_COLUMNS}))
        context=row['validation_context']
        result.update(validation_as_of=context.get('as_of'),catalog_fingerprint=context.get('catalog_fingerprint'),
                      file_issue_count=len(row['file_issues']))
        return result

    def snapshot(self,c,batch):
        files=c.execute(text("""SELECT id,role,byte_size,sha256,object_key,received_at
            FROM lab_import_files WHERE batch_id=:id AND active AND state='RECEIVED' ORDER BY role"""),
            {'id':batch['id']}).mappings().all()
        bindings=c.execute(text("""SELECT b.source_lab_key,b.source_lab_id,s.display_name,s.source_kind
            FROM lab_import_lab_bindings b JOIN laboratory_source_labs s ON s.id=b.source_lab_id
            WHERE batch_id=:id ORDER BY source_lab_key"""),{'id':batch['id']}).mappings().all()
        overrides=c.execute(text("""SELECT r.id,r.overrides FROM lab_import_rows r
            JOIN lab_import_files f ON f.id=r.file_id WHERE r.batch_id=:id AND f.active
            AND r.overrides<>'{}'::jsonb ORDER BY r.id"""),{'id':batch['id']}).mappings().all()
        import json
        return json.loads(dumped(dict(format_version=batch['format_version'],input_format=batch['input_format'],
            purpose=batch['purpose'],source_timezone=batch['source_timezone'],
            source_timezone_confirmed=batch['source_timezone_confirmed'],files=[dict(x) for x in files],
            bindings=[dict(x) for x in bindings],overrides={str(x['id']):x['overrides'] for x in overrides})))

    def status(self,c,batch):
        job=None
        if batch['current_job_id']:
            row=c.execute(text('SELECT * FROM lab_import_jobs WHERE id=:id'),
                          {'id':batch['current_job_id']}).mappings().first()
            job=self.view(row) if row else None
        current=bool(job and job['state']=='COMPLETE' and job['input_revision']==batch['revision']
            and batch['validated_revision']==batch['revision']
            and row['manifest_digest']==digest(self.snapshot(c,batch)))
        return dict(current_job=job,validation_current=current,
                    stale=bool(batch['summary'].get('last_job_id') and not current))

    def queue(self,actor,batch_id,*,idempotency_key,**values):
        o=self.o
        require_permission(actor,'laboratory.write')
        batch_id=o._uuid(batch_id)
        try: command=ValidationInput(**values)
        except ValidationError: fail('invalid_import_input')
        payload=dict(batch_id=str(batch_id),**command.model_dump(mode='json'))
        rejected=None
        with o.engine.begin() as c:
            key,fingerprint,old=o._intent(c,actor,idempotency_key,'VALIDATE',payload)
            if old:
                if old['state']=='REJECTED': rejected=old['result']
                else: job_id=old['result']['job_id']
            else:
                try:
                    with c.begin_nested():
                        batch=o._locked(c,batch_id)
                        if batch['revision']!=command.expected_revision:
                            fail('import_stale_revision',409,current_revision=batch['revision'])
                        snapshot=self.snapshot(c,batch)
                        required={'WORKBOOK'} if batch['input_format']=='XLSX' else {'SAMPLES','TESTS'}
                        files=snapshot['files']
                        if ({x['role'] for x in files}!=required or
                            any(not x['received_at'] or not re.fullmatch('[0-9a-f]{64}',x['sha256']) or
                                not 0<x['byte_size']<=MAX_FILE_BYTES for x in files) or
                            sum(x['byte_size'] for x in files)>2*MAX_FILE_BYTES):
                            fail('active_files_incomplete',409)
                        active=c.execute(text("""SELECT id FROM lab_import_jobs WHERE batch_id=:id
                            AND state IN('QUEUED','RUNNING')"""),{'id':batch_id}).scalar()
                        if active: fail('validation_in_progress',409)
                        job_id,now=uuid4(),o.clock()
                        c.execute(text("""INSERT INTO lab_import_jobs(id,batch_id,input_revision,manifest_digest,
                            input_snapshot,request_actor,requested_by,state,phase,created_at)
                            VALUES(:id,:batch,:revision,:digest,CAST(:snapshot AS jsonb),CAST(:actor AS jsonb),
                                   :user,'QUEUED','QUEUED',:now)"""),
                            dict(id=job_id,batch=batch_id,revision=batch['revision'],digest=digest(snapshot),
                                snapshot=dumped(snapshot),actor=dumped(dict(user_id=str(actor.user_id))),
                                user=actor.user_id,now=now))
                        c.execute(text("""UPDATE lab_import_batches SET current_job_id=:job,validation_state='QUEUED',
                            updated_by=:actor,updated_at=:now WHERE id=:id"""),
                            dict(id=batch_id,job=job_id,actor=actor.user_id,now=now))
                        o._complete(c,actor,key,'VALIDATE',payload,fingerprint,batch_id,
                            dict(outcome='QUEUED',batch_id=str(batch_id),job_id=str(job_id),applied_revision=batch['revision']))
                        o.audit.append(c,actor,ImportAction.QUEUED,entity_id=batch_id,
                            details=dict(job_id=str(job_id),revision=batch['revision']))
                except LaboratoryError as error:
                    rejected=dict(code=error.code,status=error.status,details=error.details)
                    op_id=o._complete(c,actor,key,'VALIDATE',payload,fingerprint,None,rejected,state='REJECTED')
                    o.audit.append(c,actor,ImportAction.QUEUED,entity_id=op_id,result='FAILURE',details=dict(code=error.code))
        if rejected: raise LaboratoryError(rejected['code'],rejected['status'],details=rejected['details'])
        with o.engine.begin() as c:
            o._authorize(c,actor)
            row=c.execute(text('SELECT * FROM lab_import_jobs WHERE id=:id'),{'id':job_id}).mappings().one()
            job=self.view(row)
        return dict(operation=o.operation(actor,key),job=job,batch=o.get(actor,batch_id))



    def requester(self,c,identifier):
        from uuid import UUID
        from dga.shared.auth.public import ActorContext
        actor=ActorContext(UUID(str(identifier)),'','',frozenset(),frozenset(),False)
        return self.o.identity.authorize_current(c,actor,'laboratory.write')

    def _failed(self,c,batch,job,actor,code):
        self.o.audit.append(c,actor,ImportAction.FAILED,entity_id=batch['id'],result='FAILURE',
            details=dict(job_id=str(job['id']),worker_id=job['worker_id'],code=code))
        c.execute(text("""UPDATE lab_import_jobs SET state='FAILED',error_code=:code,completed_at=:now,
            claim_token=NULL,lease_expires_at=NULL WHERE id=:id"""),dict(id=job['id'],code=code,now=self.o.clock()))
        c.execute(text("UPDATE lab_import_batches SET validation_state='FAILED',updated_at=:now WHERE id=:id"),
                  dict(id=batch['id'],now=self.o.clock()))

    def claim(self,worker_id,*,lease_seconds=120):
        from datetime import timedelta
        from dga.shared.auth.public import IdentityError,ActorContext
        from uuid import UUID
        if (not isinstance(worker_id,str) or not 1<=len(worker_id)<=100 or any(ord(x)<32 for x in worker_id)
                or type(lease_seconds) is not int or not 1<=lease_seconds<=3600):
            fail('invalid_import_input')
        o=self.o
        with o.engine.connect() as c:
            candidates=c.execute(text("""SELECT id,batch_id,request_actor,input_snapshot FROM lab_import_jobs
                WHERE state='QUEUED' OR (state='RUNNING' AND lease_expires_at<=:now)
                ORDER BY created_at,id LIMIT 20"""),{'now':o.clock()}).mappings().all()
        unsupported=False
        for candidate in candidates:
            if (candidate['input_snapshot'].get('format_version')!=1 or
                candidate['input_snapshot'].get('input_format') not in ('XLSX','CSV_PAIR')):
                unsupported=True
                continue
            with o.engine.begin() as c:
                authorized=True
                try: actor=self.requester(c,candidate['request_actor']['user_id'])
                except IdentityError:
                    authorized=False
                    actor=ActorContext(UUID(candidate['request_actor']['user_id']),'','',frozenset(),frozenset(),False)
                batch=o._locked(c,candidate['batch_id'])
                job=c.execute(text('SELECT * FROM lab_import_jobs WHERE id=:id FOR UPDATE SKIP LOCKED'),
                    {'id':candidate['id']}).mappings().first()
                if not job or (job['state']!='QUEUED' and not
                    (job['state']=='RUNNING' and job['lease_expires_at']<=o.clock())):
                    continue
                if (batch['current_job_id']!=job['id'] or batch['revision']!=job['input_revision']
                        or digest(self.snapshot(c,batch))!=job['manifest_digest']):
                    c.execute(text("UPDATE lab_import_jobs SET state='SUPERSEDED' WHERE id=:id"),{'id':job['id']})
                    continue
                if not authorized:
                    self._failed(c,batch,job,actor,'requester_not_authorized')
                    continue
                token,lease=uuid4(),o.clock()+timedelta(seconds=lease_seconds)
                c.execute(text("""UPDATE lab_import_jobs SET state='RUNNING',phase='READING',claim_token=:token,
                    worker_id=:worker,lease_expires_at=:lease,attempt=attempt+1,started_at=:now,error_code=NULL
                    WHERE id=:id"""),dict(id=job['id'],token=token,worker=worker_id,lease=lease,now=o.clock()))
                c.execute(text("UPDATE lab_import_batches SET validation_state='RUNNING' WHERE id=:id"),{'id':batch['id']})
                claim=dict(job_id=str(job['id']),batch_id=str(batch['id']),input_revision=job['input_revision'],
                    claim_token=str(token),manifest_digest=job['manifest_digest'],snapshot=job['input_snapshot'],
                    worker_id=worker_id,lease_seconds=lease_seconds)
            return claim
        if unsupported: fail('unsupported_validation_contract',409)
        return None

    def heartbeat(self,claim,*,phase,done,total):
        from datetime import timedelta
        if (phase not in ('READING','PARSING','VALIDATING','PERSISTING') or
            type(done) is not int or type(total) is not int or not 0<=done<=total<=52428800):
            fail('invalid_import_input')
        params=dict(id=self.o._uuid(claim['job_id']),token=self.o._uuid(claim['claim_token']),
            revision=claim['input_revision'],digest=claim['manifest_digest'],phase=phase,done=done,total=total,
            lease=self.o.clock()+timedelta(seconds=claim['lease_seconds']),now=self.o.clock())
        with self.o.engine.begin() as c:
            changed=c.execute(text("""UPDATE lab_import_jobs j SET phase=:phase,progress_done=:done,
                progress_total=:total,lease_expires_at=:lease WHERE j.id=:id AND j.claim_token=:token
                AND j.input_revision=:revision AND j.manifest_digest=:digest AND j.state='RUNNING'
                AND j.lease_expires_at>:now AND EXISTS(SELECT 1 FROM lab_import_batches b
                    WHERE b.id=j.batch_id AND b.current_job_id=j.id AND b.revision=j.input_revision)"""),params)
            if changed.rowcount!=1: fail('stale_validation_claim',409)

    def locked_claim(self,c,claim):
        from dga.shared.auth.public import IdentityError,ActorContext
        from uuid import UUID
        candidate=c.execute(text('SELECT request_actor,batch_id FROM lab_import_jobs WHERE id=:id'),
            {'id':self.o._uuid(claim['job_id'])}).mappings().first()
        if not candidate: fail('stale_validation_claim',409)
        authorized=True
        try: actor=self.requester(c,candidate['request_actor']['user_id'])
        except IdentityError:
            authorized=False
            actor=ActorContext(UUID(candidate['request_actor']['user_id']),'','',frozenset(),frozenset(),False)
        batch=self.o._locked(c,candidate['batch_id'])
        job=c.execute(text('SELECT * FROM lab_import_jobs WHERE id=:id FOR UPDATE'),
            {'id':self.o._uuid(claim['job_id'])}).mappings().one()
        if (job['state']!='RUNNING' or str(job['claim_token'])!=claim['claim_token']
            or job['lease_expires_at']<=self.o.clock() or batch['current_job_id']!=job['id']
            or batch['revision']!=job['input_revision'] or job['input_revision']!=claim['input_revision']
            or job['manifest_digest']!=claim['manifest_digest']
            or digest(self.snapshot(c,batch))!=job['manifest_digest']):
            fail('stale_validation_claim',409)
        return actor,authorized,batch,job

    def fail(self,claim,code):
        safe={'storage_unavailable','file_integrity_failed','validation_unavailable','requester_not_authorized'}
        if code not in safe: code='validation_unavailable'
        with self.o.engine.begin() as c:
            actor,authorized,batch,job=self.locked_claim(c,claim)
            if not authorized: code='requester_not_authorized'
            self._failed(c,batch,job,actor,code)
        return dict(outcome='FAILED',error_code=code)



    def complete(self,claim,result):
        import json
        rows=result.get('rows',[])
        if (not isinstance(rows,list) or len(rows)>2500 or
            sum(x['sheet']=='油样信息' for x in rows)>500 or sum(x['sheet']=='检测结果' for x in rows)>2000):
            fail('invalid_validation_result')
        with self.o.engine.begin() as c:
            actor,authorized,batch,job=self.locked_claim(c,claim)
            if not authorized:
                self._failed(c,batch,job,actor,'requester_not_authorized')
                return dict(outcome='FAILED',error_code='requester_not_authorized')
            allowed={x['id'] for x in job['input_snapshot']['files']}
            values=[]
            for row in sorted(rows,key=lambda r:(r['sheet']!='油样信息',r['row_number'],r['id'])):
                if row['file_id'] not in allowed: fail('invalid_validation_result')
                parsed=dict(row['parsed_values'],_validation_job_id=str(job['id']))
                values.append(dict(id=self.o._uuid(row['id']),file=self.o._uuid(row['file_id']),batch=batch['id'],
                    sheet=row['sheet'],number=row['row_number'],raw=dumped(row['raw_values']),
                    types=dumped(row['raw_cell_types']),parsed=dumped(parsed),issues=dumped(row['issues']),
                    revision=job['input_revision'],sample=self.o._uuid(row['sample_row_id']) if row['sample_row_id'] else None,
                    source=self.o._uuid(row['source_lab_id']) if row['source_lab_id'] else None,
                    sample_external=row['external_sample_id'],test_external=row['external_test_id']))
            for value in values:
                changed=c.execute(text("""INSERT INTO lab_import_rows(id,file_id,batch_id,sheet,row_number,
                    raw_values,raw_cell_types,parsed_values,issues,parsed_revision,sample_row_id,source_lab_id,
                    external_sample_id,external_test_id)
                    VALUES(:id,:file,:batch,:sheet,:number,CAST(:raw AS jsonb),CAST(:types AS jsonb),
                    CAST(:parsed AS jsonb),CAST(:issues AS jsonb),:revision,:sample,:source,:sample_external,:test_external)
                    ON CONFLICT(id) DO UPDATE SET parsed_values=EXCLUDED.parsed_values,issues=EXCLUDED.issues,
                        parsed_revision=EXCLUDED.parsed_revision,sample_row_id=EXCLUDED.sample_row_id,
                        source_lab_id=EXCLUDED.source_lab_id,external_sample_id=EXCLUDED.external_sample_id,
                        external_test_id=EXCLUDED.external_test_id
                    WHERE lab_import_rows.raw_values=EXCLUDED.raw_values AND
                          lab_import_rows.raw_cell_types=EXCLUDED.raw_cell_types"""),value)
                if changed.rowcount!=1: fail('raw_evidence_conflict',409)
            summary=dict(result.get('summary',{}),last_job_id=str(job['id']),input_revision=job['input_revision'])
            context=dict(result.get('context',{}),as_of=self.o.clock().isoformat(),manifest_digest=job['manifest_digest'])
            file_issues=result.get('file_issues',[])
            self.o.audit.append(c,actor,ImportAction.COMPLETED,entity_id=batch['id'],
                details=dict(job_id=str(job['id']),worker_id=job['worker_id'],revision=job['input_revision'],summary=summary))
            c.execute(text("""UPDATE lab_import_jobs SET state='COMPLETE',phase='DONE',progress_done=:count,
                progress_total=:count,file_issues=CAST(:issues AS jsonb),validation_context=CAST(:context AS jsonb),
                completed_at=:now,claim_token=NULL,lease_expires_at=NULL,error_code=NULL WHERE id=:id"""),
                dict(id=job['id'],count=len(rows),issues=dumped(file_issues),context=dumped(context),now=self.o.clock()))
            c.execute(text("""UPDATE lab_import_batches SET validated_revision=:revision,validation_state='COMPLETE',
                summary=CAST(:summary AS jsonb),updated_at=:now WHERE id=:id"""),
                dict(id=batch['id'],revision=job['input_revision'],summary=dumped(summary),now=self.o.clock()))
        return dict(outcome='COMPLETE',job_id=str(job['id']),applied_revision=job['input_revision'])

    def process(self,worker_id,*,lease_seconds=120):
        from hashlib import sha256
        from sqlalchemy.exc import SQLAlchemyError
        from dga.shared.auth.public import IdentityError
        from .import_tables import read_xlsx_tables,read_csv_pair,ImportFileError
        from .import_validation import validate_tables
        claim=self.claim(worker_id,lease_seconds=lease_seconds)
        if claim is None: return False
        snapshot=claim['snapshot']
        try:
            total=sum(x['byte_size'] for x in snapshot['files'])
            self.heartbeat(claim,phase='READING',done=0,total=total)
            content={}
            read=0
            for file in snapshot['files']:
                try: data=self.o.files.get(object_key=file['object_key'])
                except Exception:
                    self.fail(claim,'storage_unavailable')
                    return True
                if not isinstance(data,bytes) or len(data)!=file['byte_size'] or sha256(data).hexdigest()!=file['sha256']:
                    self.fail(claim,'file_integrity_failed')
                    return True
                content[file['role']]=(file['id'],data)
                read+=len(data)
                self.heartbeat(claim,phase='READING',done=read,total=total)
            self.heartbeat(claim,phase='PARSING',done=0,total=0)
            try:
                if snapshot['input_format']=='XLSX':
                    file_id,data=content['WORKBOOK']
                    tables=read_xlsx_tables(data,file_id=file_id)
                else:
                    sid,sdata=content['SAMPLES'];tid,tdata=content['TESTS']
                    tables=read_csv_pair(sdata,tdata,sample_file_id=sid,test_file_id=tid)
                if not any(table.rows for table in tables):
                    raise ImportFileError('no_business_rows',file_id=snapshot['files'][0]['id'])
            except ImportFileError as error:
                locator=dict(file_id=error.file_id,sheet=error.sheet,row_number=error.row_number,field=error.field)
                item=dict(id=digest(dict(code=error.code,**locator))[:24],version=1,code=error.code,severity='ERROR',
                    row_id=None,raw_value=None,message='文件内容无法校验：'+error.code,
                    suggestion='保留原件，核对文件格式或容量后上传更正原件并明确选择。',**locator)
                self.complete(claim,dict(rows=[],file_issues=[item],
                    summary=dict(sample_count=0,test_count=0,unassigned_test_count=0,error_count=1,warning_count=0,
                                 checked_sample_count=0),context=dict(format_version=1)))
                return True
            count=sum(len(x.rows) for x in tables)
            self.heartbeat(claim,phase='VALIDATING',done=0,total=count)
            # No staging batch/job lock crosses into upstream public owner reads.
            with self.o.engine.begin() as c:
                actor=self.requester(c,snapshot_actor_id(self.o,claim))
                catalog=self.o.configuration.import_catalog(actor,connection=c)
            result=validate_tables(tables,snapshot,catalog,self.o.assets,actor,
                progress=lambda done,total:self.heartbeat(claim,phase='VALIDATING',done=done,total=total))
            self.heartbeat(claim,phase='PERSISTING',done=0,total=count)
            self.complete(claim,result)
            return True
        except IdentityError:
            self.fail(claim,'requester_not_authorized')
            return True
        except (SQLAlchemyError,ConnectionError):
            # Serialization/deadlock/unknown COMMIT are not scientific data errors.
            raise
        except LaboratoryError:
            raise
        except Exception:
            self.fail(claim,'validation_unavailable')
            return True


def snapshot_actor_id(owner,claim):
    with owner.engine.connect() as c:
        value=c.execute(text('SELECT requested_by FROM lab_import_jobs WHERE id=:id'),
            {'id':owner._uuid(claim['job_id'])}).scalar_one()
        return value




