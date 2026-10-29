"""Asset-owned v2 workflow. Public callers enter through AssetImports."""
import json
import hashlib
from math import isfinite
from enum import StrEnum
from uuid import uuid4, UUID
from sqlalchemy import text
from dga.shared.auth.public import IdentityService, AuditTrail, require_permission
from dga.shared.files import ObjectStorageError
from .lifecycle import fail
from .import_workbook import WorkbookError
from . import v2_import_workbook as workbook
from .site_import_validation import validate, digest

class SiteImportAction(StrEnum):
    ASSET_UPLOAD='ASSET_IMPORT_SUBMIT'
    ASSET_REVISE='ASSET_IMPORT_REVISE'
    ASSET_SOURCE='ASSET_IMPORT_SOURCE_DOWNLOAD'
    UPLOAD='SITE_IMPORT_UPLOAD'
    PUBLISH='SITE_IMPORT_PUBLISH'
    REVISE='SITE_IMPORT_REVISE'
    SOURCE='SITE_IMPORT_SOURCE_DOWNLOAD'


def dumped(value): return json.dumps(value,ensure_ascii=False,default=str)

class V2Imports:
    def __init__(self,engine,files,clock):
        self.engine,self.files,self.clock=engine,files,clock
        self.identity=IdentityService(engine); self.audit=AuditTrail(clock=clock)

    def supported(self,batch):
        if batch['format_version']!=2 or batch['mode'] not in ('SITES','ASSETS'): fail('unsupported_import_format',503)

    def authorize(self,c,actor):
        return self.identity.authorize_current(c,actor,'assets.import')

    def lock(self,c,actor,key,action,payload):
        self.authorize(c,actor)
        try: key=str(UUID(key))
        except (ValueError,TypeError,AttributeError): fail('invalid_idempotency_key',422)
        c.execute(text('SELECT pg_advisory_xact_lock(110011)'))
        previous=c.execute(text('SELECT * FROM asset_import_operations WHERE actor_id=:actor AND operation_key=:key'),dict(actor=actor.user_id,key=key)).mappings().first()
        request_digest=digest([action,payload])
        if previous and (previous['action']!=action or previous['request_digest']!=request_digest): fail('import_operation_conflict',409)
        return key,request_digest,previous

    def complete(self,c,actor,key,action,request_digest,batch_id,result):
        c.execute(text("""INSERT INTO asset_import_operations(actor_id,operation_key,action,request_digest,batch_id,result)
            VALUES (:actor,:key,:action,:digest,:batch,CAST(:result AS jsonb))"""),dict(actor=actor.user_id,key=key,action=action,digest=request_digest,batch=batch_id,result=dumped(result)))

    def submit(self,actor,*,filename,content,idempotency_key,mode='SITES'):
        require_permission(actor,'assets.import')
        if not isinstance(filename,str) or not filename.lower().endswith('.xlsx') or not 1<=len(filename)<=200 or any(ord(ch)<32 or ch in '/\\' for ch in filename): fail('invalid_import_filename',422)
        if not isinstance(content,bytes) or not 0<len(content)<=workbook.MAX_BYTES: fail('import_file_size',413)
        sha=hashlib.sha256(content).hexdigest()
        with self.engine.begin() as c:
            key,request_digest,old=self.lock(c,actor,idempotency_key,'UPLOAD',[filename,sha,2,mode])
            if old: batch_id=old['batch_id']
            else:
                batch_id=uuid4(); state='STAGED'; issues=[]
                try: rows=workbook.parse(content,mode=mode)
                except WorkbookError as error: rows=[]; issues=error.issues; state='FAILED'
                object_key=f'asset-imports/{batch_id}/source.xlsx'
                # No deletion after uncertain COMMIT: retained evidence wins over cleanup.
                self.files.put(object_key=object_key,content=content,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                c.execute(text("""INSERT INTO asset_import_batches
                    (id,filename,sha256,object_key,byte_size,state,source_rows,issues,summary,created_by,created_at,format_version,mode)
                    VALUES (:id,:name,:sha,:object,:size,:state,CAST(:rows AS jsonb),CAST(:issues AS jsonb),CAST(:summary AS jsonb),:actor,:at,2,:mode)"""),
                    dict(mode=mode,id=batch_id,name=filename,sha=sha,object=object_key,size=len(content),state=state,rows=dumped(rows),issues=dumped(issues),summary=dumped(dict(total_rows=len(rows),error_count=len(issues),warning_count=0,valid_rows=0,error_rows=len(issues),warning_rows=0)),actor=actor.user_id,at=self.clock()))
                self.complete(c,actor,key,'UPLOAD',request_digest,batch_id,dict(outcome='STAGED' if state=='STAGED' else 'FAILED',batch_id=str(batch_id)))
                self.audit.append(c,actor,SiteImportAction.ASSET_UPLOAD if mode=='ASSETS' else SiteImportAction.UPLOAD,entity_id=batch_id)
        result=self.get(actor,batch_id)
        result['operation_result']=self.operation(actor,key)
        return result

    def duplicates(self,c,batch):
        if batch['mode']=='ASSETS':
            return [dict(r) for r in c.execute(text("""SELECT id::text AS id,filename,state,format_version,mode,published_at
                FROM asset_import_batches WHERE sha256=:sha AND id<>:id
                ORDER BY (state='PUBLISHED') DESC,created_at,id"""),dict(sha=batch['sha256'],id=batch['id'])).mappings()]
        return [dict(r) for r in c.execute(text("""SELECT id::text AS id,filename,state FROM asset_import_batches
            WHERE sha256=:sha AND format_version=2 AND id<>:id ORDER BY created_at,id LIMIT 20"""),dict(sha=batch['sha256'],id=batch['id'])).mappings()]

    def preview(self,c,batch):
        self.supported(batch)
        source=batch['working_rows'] if batch['working_rows'] is not None else batch['source_rows']
        if batch['mode']=='ASSETS':
            from .asset_import_validation_v2 import validate as validate_assets
            rows,issues,counts,fingerprint=validate_assets(c,source,self.clock())
        else:
            rows,issues,counts,fingerprint=validate(c,source)
        duplicates=self.duplicates(c,batch)
        if duplicates:
            warning=dict(id=digest(['duplicate_file',duplicates])[:24],code='duplicate_file',severity='WARNING',sheet='Format',row=0,field='file',message='相同原文件已上传；请先查看已有批次结果，确属另一个批次才确认继续。')
            issues.append(warning); counts['warning_count']+=1
        return rows,issues,counts,digest([fingerprint,duplicates])

    def validate_batch(self,c,batch):
        rows,issues,counts,fingerprint=self.preview(c,batch)
        c.execute(text("""UPDATE asset_import_batches SET rows=CAST(:rows AS jsonb),issues=CAST(:issues AS jsonb),
            summary=CAST(:summary AS jsonb),catalog_digest=:digest,state='VALIDATED',failure_code=NULL,validation_revision=validation_revision+1 WHERE id=:id"""),
            dict(id=batch['id'],rows=dumped(rows),issues=dumped(issues),summary=dumped(counts),digest=fingerprint))
        return rows,issues,counts,fingerprint

    def get(self,actor,batch_id,page=1,duplicate_page=1):
        if any(type(n) is not int or not 1<=n<=100000 for n in (page,duplicate_page)): fail('invalid_import_search',422)
        with self.engine.begin() as c:
            self.authorize(c,actor)
            batch=c.execute(text('SELECT * FROM asset_import_batches WHERE id=:id'),{'id':batch_id}).mappings().first()
            if not batch: fail('import_not_found',404)
            self.supported(batch)
            result={k:v for k,v in batch.items() if k not in ('source_rows','working_rows','object_key','catalog_digest')}
            originals={(r['sheet'],r['row']):r['values'] for r in batch['source_rows']} if batch['format_version']==2 else {}
            all_rows=batch['rows']; result['total_rows']=len(all_rows); result['page']=page
            duplicates=self.duplicates(c,batch)
            result['duplicate_total']=len(duplicates); result['duplicate_page']=duplicate_page
            result['duplicate_batches']=duplicates[(duplicate_page-1)*20:duplicate_page*20]
            result['rows']=[dict(r,original_values=originals.get((r['sheet'],r['row']))) for r in all_rows[(page-1)*20:page*20]] if batch['format_version']==2 else all_rows
            visible={(r['sheet'],r['row']) for r in result['rows']}
            result['issues']=[i for i in batch['issues'] if batch['state']=='FAILED' or i.get('row',0)==0 or (i.get('sheet'),i['row']) in visible]
            return result

    def revise(self,actor,batch_id,*,expected_revision,changes,reason,idempotency_key):
        if type(expected_revision) is not int or expected_revision<0 or not isinstance(changes,list) or not 1<=len(changes)<=2000 or not isinstance(reason,str) or not 1<=len(reason.strip())<=1000:
            fail('invalid_import_revision',422)
        with self.engine.begin() as c:
            key,request_digest,old=self.lock(c,actor,idempotency_key,'REVISE',[str(batch_id),expected_revision,changes,reason])
            if not old:
                batch=c.execute(text('SELECT * FROM asset_import_batches WHERE id=:id FOR UPDATE'),{'id':batch_id}).mappings().first()
                if not batch or batch['format_version']!=2: fail('import_not_found',404)
                self.supported(batch)
                if batch['state']=='PUBLISHED': fail('import_already_published',409)
                if batch['validation_revision']!=expected_revision: fail('import_stale_validation',409)
                working=json.loads(dumped(batch['working_rows'] if batch['working_rows'] is not None else batch['source_rows']))
                indexed={(r['sheet'],r['row']):r for r in working}
                touched=set()
                for change in changes:
                    if not isinstance(change,dict) or set(change)!={'sheet','row','values'} or type(change['row']) is not int or not isinstance(change['sheet'],str) or not isinstance(change['values'],dict): fail('invalid_import_revision',422)
                    entry_key=(change['sheet'],change['row'])
                    row=indexed.get(entry_key)
                    if row is None or entry_key in touched or set(change['values'])-set(workbook.COLUMNS[row['sheet']]): fail('invalid_import_revision',422)
                    touched.add(entry_key)
                    if any(v is not None and (type(v) not in (str,int,float,bool) or isinstance(v,float) and not isfinite(v) or isinstance(v,str) and len(v)>2000) for v in change['values'].values()): fail('invalid_import_revision',422)
                    row['values'].update(change['values'])
                c.execute(text('UPDATE asset_import_batches SET working_rows=CAST(:rows AS jsonb) WHERE id=:id'),dict(id=batch_id,rows=dumped(working)))
                updated=dict(batch,working_rows=working)
                self.validate_batch(c,updated)
                revision=batch['validation_revision']+1
                c.execute(text("""INSERT INTO asset_import_revisions(id,batch_id,revision,actor_id,occurred_at,reason,before_value,after_value)
                    VALUES (:id,:batch,:revision,:actor,:at,:reason,CAST(:before AS jsonb),CAST(:after AS jsonb))"""),dict(id=uuid4(),batch=batch_id,revision=revision,actor=actor.user_id,at=self.clock(),reason=reason,before=dumped(batch['working_rows'] if batch['working_rows'] is not None else batch['source_rows']),after=dumped(working)))
                self.audit.append(c,actor,SiteImportAction.ASSET_REVISE if batch['mode']=='ASSETS' else SiteImportAction.REVISE,entity_id=batch_id,details=dict(revision=revision,reason=reason))
                self.complete(c,actor,key,'REVISE',request_digest,batch_id,dict(outcome='REVISED',batch_id=str(batch_id),revision=revision))
        result=self.get(actor,batch_id)
        result['operation_result']=self.operation(actor,key)
        return result

    def publish(self,actor,batch_id,*,validation_revision,idempotency_key,acknowledged_warning_ids):
        if type(validation_revision) is not int or validation_revision<1 or not isinstance(acknowledged_warning_ids,list) or any(not isinstance(i,str) for i in acknowledged_warning_ids): fail('invalid_import_request',422)
        with self.engine.begin() as c:
            key,request_digest,old=self.lock(c,actor,idempotency_key,'PUBLISH',[str(batch_id),validation_revision,sorted(acknowledged_warning_ids)])
            if not old:
                batch=c.execute(text('SELECT * FROM asset_import_batches WHERE id=:id FOR UPDATE'),{'id':batch_id}).mappings().first()
                if not batch or batch['format_version']!=2: fail('import_not_found',404)
                self.supported(batch)
                if batch['mode']=='ASSETS': fail('import_mode_not_publishable',409)
                if batch['state']=='PUBLISHED': outcome='PUBLISHED'
                else:
                    if batch['state']!='VALIDATED': fail('import_not_validated',409)
                    if validation_revision!=batch['validation_revision']: fail('import_stale_validation',409)
                    self._content(batch)
                    c.execute(text('LOCK TABLE customers,sites,site_product_lines IN SHARE ROW EXCLUSIVE MODE'))
                    rows,issues,counts,fingerprint=self.preview(c,batch)
                    if fingerprint!=batch['catalog_digest'] or rows!=batch['rows'] or issues!=batch['issues']:
                        self.validate_batch(c,batch); outcome='REFRESHED'
                    else:
                        if counts['error_count']: fail('import_has_errors',409)
                        if not {i['id'] for i in issues if i['severity']=='WARNING'}<=set(acknowledged_warning_ids): fail('import_warnings_unacknowledged',409)
                        self._create(c,actor,batch,rows)
                        outcome='PUBLISHED'
                saved=c.execute(text('SELECT rows,validation_revision FROM asset_import_batches WHERE id=:id'),{'id':batch_id}).mappings().one()
                result=dict(outcome=outcome,batch_id=str(batch_id),revision=saved['validation_revision'],target_ids=[r['target_id'] for r in saved['rows'] if r.get('target_id')] if outcome=='PUBLISHED' else [])
                self.complete(c,actor,key,'PUBLISH',request_digest,batch_id,result)
        return self.get(actor,batch_id)

    def _create(self,c,actor,batch,rows):
        customer_ids={}
        originals={(r['sheet'],r['row']):r['values'] for r in batch['source_rows']}
        for row in sorted(rows,key=lambda r:r['sheet']):
            v=row['values']; kind='CUSTOMER' if row['sheet']=='Customers' else 'SITE'
            target=UUID(row['target_id']) if v['decision']=='REFERENCE' else uuid4()
            row['target_id']=str(target)
            if kind=='CUSTOMER':
                customer_ids[v['record_key']]=target
                if v['decision']=='NEW': c.execute(text('INSERT INTO customers(id,customer_name) VALUES (:id,:name)'),dict(id=target,name=v['customer_name']))
            elif v['decision']=='NEW':
                ref=v['customer_ref']; customer=customer_ids[ref[4:]] if ref.startswith('NEW:') else UUID(ref)
                c.execute(text("""INSERT INTO sites(id,customer_id,site_name,location_text,commissioning_date,grid_status,operation_status,source_note)
                    VALUES (:id,:customer,:name,:location,:date,:grid,:operation,:note)"""),
                    dict(id=target,customer=customer,name=v['site_name'],location=v.get('location_text') or None,date=v.get('commissioning_date') or None,grid=v.get('grid_status') or None,operation=v.get('operation_status') or None,note=v.get('source_note') or None))
                for line in v['product_lines'].split(';'):
                    c.execute(text('INSERT INTO site_product_lines(site_id,product_line,power_mw,energy_mwh) VALUES (:id,:line,:power,:energy)'),dict(id=target,line=line,power=v.get('pv_power_mw' if line=='PV' else 'ess_power_mw'),energy=v.get('ess_energy_mwh') if line=='ESS' else None))
            original=originals[(row['sheet'],row['row'])]
            c.execute(text("""INSERT INTO asset_import_sources(id,batch_id,kind,target_id,sheet,row_number,source_note,original_values,reviewed_values,actor_id,occurred_at,revision,reason)
                VALUES (:id,:batch,:kind,:target,:sheet,:row,:note,CAST(:original AS jsonb),CAST(:reviewed AS jsonb),:actor,:at,:revision,:reason)"""),
                dict(id=uuid4(),batch=batch['id'],kind=kind,target=target,sheet=row['sheet'],row=row['row'],note=v.get('source_note'),original=dumped(original),reviewed=dumped(v),actor=actor.user_id,at=self.clock(),revision=batch['validation_revision'],reason=v['reason']))
        c.execute(text("""UPDATE asset_import_batches SET state='PUBLISHED',rows=CAST(:rows AS jsonb),published_by=:actor,published_at=:at WHERE id=:id"""),dict(id=batch['id'],rows=dumped(rows),actor=actor.user_id,at=self.clock()))
        self.audit.append(c,actor,SiteImportAction.PUBLISH,entity_id=batch['id'])

    def revision_history(self,actor,batch_id,page=1):
        if type(page) is not int or not 1<=page<=100000: fail('invalid_import_search',422)
        with self.engine.begin() as c:
            self.authorize(c,actor)
            if c.execute(text('SELECT id FROM asset_import_batches WHERE id=:id'),{'id':batch_id}).scalar() is None: fail('import_not_found',404)
            query="""WITH changes AS (SELECT r.revision,r.reason,r.occurred_at,u.display_name,
                a.value->>'sheet' AS sheet,(a.value->>'row')::int AS row,
                (r.before_value->(a.ordinality::int-1))->'values' AS before_value,a.value->'values' AS after_value
                FROM asset_import_revisions r JOIN users u ON u.id=r.actor_id
                CROSS JOIN LATERAL jsonb_array_elements(r.after_value) WITH ORDINALITY AS a(value,ordinality)
                WHERE r.batch_id=:id AND r.before_value->(a.ordinality::int-1) IS DISTINCT FROM a.value)
            """
            params=dict(id=batch_id,offset=(page-1)*20)
            total=c.execute(text(query+' SELECT count(*) FROM changes'),params).scalar_one()
            entries=c.execute(text(query+' SELECT * FROM changes ORDER BY revision DESC,sheet,row LIMIT 20 OFFSET :offset'),params).mappings()
            return dict(changes=[dict(revision=r['revision'],reason=r['reason'],occurred_at=r['occurred_at'],display_name=r['display_name'],sheet=r['sheet'],row=r['row'],before=r['before_value'],after=r['after_value']) for r in entries],total=total,page=page)

    def operation(self,actor,key):
        try: key=str(UUID(key))
        except (ValueError,TypeError,AttributeError): fail('invalid_idempotency_key',422)
        with self.engine.begin() as c:
            self.authorize(c,actor)
            result=c.execute(text('SELECT result FROM asset_import_operations WHERE actor_id=:actor AND operation_key=:key'),dict(actor=actor.user_id,key=key)).scalar()
            if result is None: fail('import_operation_not_found',404)
            return result

    def _content(self,batch):
        try: content=self.files.get(object_key=batch['object_key'])
        except Exception as error: raise ObjectStorageError('import_source_unavailable') from error
        if len(content)!=batch['byte_size'] or hashlib.sha256(content).hexdigest()!=batch['sha256']: raise ObjectStorageError('import_source_integrity')
        return content

    def source(self,actor,batch_id):
        with self.engine.begin() as c:
            self.authorize(c,actor)
            batch=c.execute(text('SELECT * FROM asset_import_batches WHERE id=:id'),{'id':batch_id}).mappings().first()
            if not batch: fail('import_not_found',404)
            content=self._content(batch)
            self.audit.append(c,actor,SiteImportAction.ASSET_SOURCE if batch['format_version']==2 and batch['mode']=='ASSETS' else SiteImportAction.SOURCE,entity_id=batch_id)
            return dict(content=content,filename=batch['filename'])
