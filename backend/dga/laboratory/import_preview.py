"""Paged read model for current or explicitly stale staged validation evidence."""
import json
from sqlalchemy import text
from .imports import dumped,fail
from .import_jobs import ValidationJobs


class ImportPreview:
    def __init__(self,owner): self.o=owner

    def context(self,c,actor,batch_id):
        self.o._authorize(c,actor)
        batch=c.execute(text('SELECT * FROM lab_import_batches WHERE id=:id FOR SHARE'),
            {'id':self.o._uuid(batch_id)}).mappings().first()
        if not batch: fail('import_not_found',404)
        state=ValidationJobs(self.o).status(c,batch)
        result_id=str(batch['current_job_id']) if state['validation_current'] else batch['summary'].get('last_job_id')
        result=None
        if result_id:
            result=c.execute(text('SELECT * FROM lab_import_jobs WHERE id=:id AND batch_id=:batch'),
                dict(id=self.o._uuid(result_id),batch=batch['id'])).mappings().first()
        return batch,state,result

    @staticmethod
    def page(value):
        if type(value) is not int or not 1<=value<=100000: fail('invalid_import_input')
        return value

    @staticmethod
    def row(row,stale):
        result=json.loads(dumped(dict(row)))
        parsed=result['parsed_values'] or {}
        parsed.pop('_validation_job_id',None)
        result['parsed_values']=parsed
        result['reviewed_values']={**result['raw_values'],**result['overrides']}
        result['stale']=stale
        result['related_test_count']=parsed.get('related_test_count',0)
        counts={key:sum(x['severity']==key for x in result['issues']) for key in ('ERROR','WARNING','INFO')}
        counts['ERROR']+=parsed.get('related_error_count',0)
        counts['WARNING']+=parsed.get('related_warning_count',0)
        result['issue_counts']=counts
        return result

    def rows(self,c,batch,result,*,sheet,page=1,sample_id=None,unassigned=False,severity=None):
        if result is None: return dict(items=[],total=0,page=page,page_size=20)
        if severity not in (None,'ERROR','WARNING','INFO'): fail('invalid_import_input')
        params=dict(batch=batch['id'],job=str(result['id']),sheet=sheet,offset=(page-1)*20,
            parent=sample_id,unassigned=unassigned,severity=severity)
        where="""r.batch_id=:batch AND r.sheet=:sheet AND r.parsed_values->>'_validation_job_id'=:job
            AND (CAST(:parent AS uuid) IS NULL OR r.sample_row_id=:parent)
            AND (NOT :unassigned OR r.sample_row_id IS NULL)
            AND (CAST(:severity AS text) IS NULL OR EXISTS(SELECT 1 FROM jsonb_array_elements(r.issues) i
                WHERE i->>'severity'=:severity) OR
                (:severity='ERROR' AND COALESCE((r.parsed_values->>'related_error_count')::int,0)>0) OR
                (:severity='WARNING' AND COALESCE((r.parsed_values->>'related_warning_count')::int,0)>0))"""
        value=c.execute(text("""WITH matching AS (SELECT r.* FROM lab_import_rows r WHERE """+where+""")
            SELECT (SELECT count(*) FROM matching) total,
                (SELECT jsonb_agg(to_jsonb(p)) FROM(SELECT * FROM matching ORDER BY row_number,id
                 LIMIT 20 OFFSET :offset)p) items"""),params).mappings().one()
        return dict(items=value['items'] or [],total=value['total'],page=page,page_size=20)

    def samples(self,actor,batch_id,*,page=1,severity=None):
        page=self.page(page)
        with self.o.engine.begin() as c:
            batch,state,result=self.context(c,actor,batch_id)
            value=self.rows(c,batch,result,sheet='油样信息',page=page,severity=severity)
            value['items']=[self.row(x,state['stale']) for x in value['items']]
            missing=self.rows(c,batch,result,sheet='检测结果',unassigned=True)
            issues=result['file_issues'] if result else []
            return dict(**value,unassigned_test_total=missing['total'],
                file_issues_summary={key:sum(x['severity']==key for x in issues) for key in ('ERROR','WARNING','INFO')},
                validation_current=state['validation_current'],stale=state['stale'],
                result_job_id=str(result['id']) if result else None)

    def sample(self,actor,batch_id,row_id,*,test_page=1):
        test_page=self.page(test_page)
        with self.o.engine.begin() as c:
            batch,state,result=self.context(c,actor,batch_id)
            row=c.execute(text("""SELECT * FROM lab_import_rows WHERE id=:id AND batch_id=:batch
                AND sheet='油样信息' AND parsed_values->>'_validation_job_id'=:job"""),
                dict(id=self.o._uuid(row_id),batch=batch['id'],job=str(result['id']) if result else '')).mappings().first()
            if row is None: fail('import_row_not_found',404)
            tests=self.rows(c,batch,result,sheet='检测结果',page=test_page,sample_id=self.o._uuid(row_id))
            tests['items']=[self.row(x,state['stale']) for x in tests['items']]
            return dict(sample=self.row(row,state['stale']),tests=tests,
                validation_current=state['validation_current'],stale=state['stale'])

    def unassigned(self,actor,batch_id,*,page=1):
        page=self.page(page)
        with self.o.engine.begin() as c:
            batch,state,result=self.context(c,actor,batch_id)
            value=self.rows(c,batch,result,sheet='检测结果',page=page,unassigned=True)
            value['items']=[self.row(x,state['stale']) for x in value['items']]
            return dict(**value,validation_current=state['validation_current'],stale=state['stale'])

    def issues(self,actor,batch_id,*,page=1,severity=None,code=None,sheet=None,row_id=None):
        page=self.page(page)
        if severity not in (None,'ERROR','WARNING','INFO') or sheet not in (None,'油样信息','检测结果'):
            fail('invalid_import_input')
        if code is not None and (not isinstance(code,str) or not 1<=len(code)<=80): fail('invalid_import_input')
        with self.o.engine.begin() as c:
            batch,state,result=self.context(c,actor,batch_id)
            if not result: return dict(items=[],total=0,page=page,page_size=50,severity_counts=dict(ERROR=0,WARNING=0,INFO=0),stale=False)
            params=dict(batch=batch['id'],job=str(result['id']),severity=severity,code=code,sheet=sheet,
                        row=str(self.o._uuid(row_id)) if row_id else None,offset=(page-1)*50,file_issues=dumped(result['file_issues']))
            data=c.execute(text("""WITH all_issues AS (
                SELECT i FROM jsonb_array_elements(CAST(:file_issues AS jsonb)) i
                UNION ALL SELECT i FROM lab_import_rows r,jsonb_array_elements(r.issues) i
                    WHERE r.batch_id=:batch AND r.parsed_values->>'_validation_job_id'=:job),
                matching AS(SELECT i FROM all_issues WHERE (CAST(:severity AS text) IS NULL OR i->>'severity'=:severity)
                    AND (CAST(:code AS text) IS NULL OR i->>'code'=:code)
                    AND (CAST(:sheet AS text) IS NULL OR i->>'sheet'=:sheet)
                    AND (CAST(:row AS text) IS NULL OR i->>'row_id'=:row))
                SELECT count(*) total,count(*) FILTER(WHERE i->>'severity'='ERROR') errors,
                    count(*) FILTER(WHERE i->>'severity'='WARNING') warnings,count(*) FILTER(WHERE i->>'severity'='INFO') infos,
                    (SELECT jsonb_agg(p.i) FROM(SELECT i FROM matching ORDER BY i->>'file_id',
                        i->>'sheet',(i->>'row_number')::int NULLS FIRST,i->>'field',i->>'id' LIMIT 50 OFFSET :offset)p) items
                FROM matching"""),params).mappings().one()
            return dict(items=data['items'] or [],total=data['total'],page=page,page_size=50,
                severity_counts=dict(ERROR=data['errors'],WARNING=data['warnings'],INFO=data['infos']),stale=state['stale'])

