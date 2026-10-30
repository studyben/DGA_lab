import type {CreateInput,RevisionInput,UploadMetadata,Receipt,MutationResult,DurableInputRejection} from './importTypes';
export const importRoot='/api/laboratory/imports';
const messages:Record<string,string>={
  import_stale_revision:'批次已被修改。原请求已拒绝；请加载最新批次后重新核对。',
  source_candidates_changed:'同名来源实验室候选已变化。请重新查询并明确选择。',
  files_pending:'所选文件尚未确认保存，当前采用的原件保持不变。',
  import_operation_conflict:'此操作与原请求不一致，请查询原操作并保留其内容。',
  import_receipt_claim_stale:'此上传已失去收件资格，请查询原操作状态后恢复。',
  import_file_size:'原件须为非空文件，且每份不超过 10 MiB。',
  import_request_size:'提交内容超过限制，请拆分批次。',
  import_content_type:'原件格式不正确：工作簿使用 XLSX，两份表格使用 UTF-8 CSV。',
  invalid_import_filename:'请使用不含路径或控制字符的 .xlsx 或 .csv 文件名。',
  import_role_not_supported:'文件角色与批次格式不一致。',
  invalid_import_input:'请核对输入、来源选择和时区；系统未猜测缺失资料。',
  invalid_input:'请核对输入格式。',
  object_storage_unavailable:'原件存储暂不可用，结果尚未确认；请查询原操作。',
  import_write_unknown:'保存结果尚未确认，请保留原请求并查询原操作。',
  import_read_unavailable:'读取暂不可用，请稍后重试。',
  forbidden:'当前账号无权执行此操作。',
  csrf_rejected:'会话已更新，请刷新登录状态后查询原操作。',
  origin_rejected:'当前访问地址未获授权。',
  session_expired:'登录已失效，请重新登录后查询原操作。',
};
function object(value:unknown):Record<string,unknown>|null{
  return value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:null;
}
export function parseImportError(value:unknown,status:number):ImportError {
  const body=object(value),op=object(body?.operation),result=object(op?.result);
  const code=typeof body?.code==='string'?body.code:'request_failed';
  const proven=status===422&&code==='invalid_import_input'&&body?.disposition==='DURABLE_REJECTED'
    &&op?.state==='REJECTED'&&(op.action==='CREATE'||op.action==='REVISE')&&op.batch_id===null
    &&op.error_code===null&&result?.code==='invalid_import_input'&&result.status===422&&result.details===null;
  return new ImportError(code,status,proven?op as unknown as DurableInputRejection:undefined);
}
export class ImportError extends Error {
  readonly disposition?:'DURABLE_REJECTED';
  constructor(public code:string,public status:number,public operation?:DurableInputRejection) {
    super(messages[code]??(status===401?'登录已失效，请重新登录。':status===403?'当前账号无权访问暂存资料。':'请求暂未完成，请稍后重试。'));
    if(operation)this.disposition='DURABLE_REJECTED';
  }
}
async function response<T>(r:Response):Promise<T> {
  if(!r.ok)throw parseImportError(await r.json().catch(()=>null),r.status);
  return r.json() as Promise<T>;
}
export async function readImport<T>(suffix:string):Promise<T>{
  return response<T>(await fetch(importRoot+suffix,{cache:'no-store',credentials:'same-origin',signal:AbortSignal.timeout(45000)}));
}
export async function sendImport(action:'CREATE'|'REVISE',key:string,payload:CreateInput|RevisionInput,batch:string|null,csrf:string):Promise<MutationResult>{
  return response<MutationResult>(await fetch(importRoot+(action==='REVISE'?'/'+batch+'/revisions':''),{
    method:'POST',credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(45000),
    headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,'Idempotency-Key':key},body:JSON.stringify(payload)}));
}
export function uploadOriginal(meta:UploadMetadata,key:string,file:File,csrf:string,onProgress:(value:number|null)=>void):Promise<Receipt>{
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();
    const query=new URLSearchParams({role:meta.role,filename:meta.filename});
    xhr.open('POST',importRoot+'/'+meta.batch_id+'/files?'+query);
    xhr.timeout=45000;
    xhr.setRequestHeader('Content-Type',meta.content_type);
    xhr.setRequestHeader('X-CSRF-Token',csrf);
    xhr.setRequestHeader('Idempotency-Key',key);
    xhr.upload.onprogress=e=>onProgress(e.lengthComputable?Math.min(100,Math.floor(e.loaded/e.total*100)):null);
    xhr.upload.onload=()=>onProgress(100);
    xhr.onerror=xhr.ontimeout=()=>reject(new Error('保存结果尚未确认，请保留原请求并查询原操作。'));
    xhr.onload=()=>{
      let data;
      try{data=JSON.parse(xhr.responseText);}catch{reject(new Error('收件响应无效，结果尚未确认，请查询原操作。'));return;}
      if(xhr.status<200||xhr.status>=300){reject(parseImportError(data,xhr.status));return;}
      resolve(data as Receipt);
    };
    onProgress(0);
    xhr.send(file);
  });
}



