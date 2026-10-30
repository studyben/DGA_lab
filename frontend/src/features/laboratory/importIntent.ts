import {sha256} from '@noble/hashes/sha2.js';
import {bytesToHex} from '@noble/hashes/utils.js';
import type {CreateInput,RevisionInput,UploadMetadata,FileRole} from './importTypes';

type JsonIntent={action:'CREATE';payload:CreateInput;batch_id:null}|{action:'REVISE';payload:RevisionInput;batch_id:string};
type FileIntent={action:'RECEIVE';payload:UploadMetadata;batch_id:string};
export type ImportIntent=(JsonIntent|FileIntent)&{version:1;key:string;digest:string};
const MAX_JSON_BYTES=32*1024*1024;
function slot(actor:string){return 'dga:lab-import:v1:'+actor;}
export function hashBytes(bytes:Uint8Array){return bytesToHex(sha256(bytes));}
function fingerprint(value:{action:string;batch_id:string|null;payload:unknown}){return hashBytes(new TextEncoder().encode(JSON.stringify([value.action,value.batch_id,value.payload])));}
function uuid(){
  if(!globalThis.crypto?.getRandomValues)throw new Error('浏览器缺少安全随机数能力。');
  const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const h=bytesToHex(bytes);return [h.slice(0,8),h.slice(8,12),h.slice(12,16),h.slice(16,20),h.slice(20)].join('-');
}
export function prepareIntent(value:JsonIntent|FileIntent):ImportIntent {
  return {...value,version:1,key:uuid(),digest:fingerprint(value)} as ImportIntent;
}
export function retainIntent(actor:string,intent:ImportIntent){
  const raw=JSON.stringify(intent);
  if(new TextEncoder().encode(raw).byteLength>MAX_JSON_BYTES)throw new Error('请求过大，请拆分批次。');
  try{
    sessionStorage.setItem(slot(actor),raw);
    if(sessionStorage.getItem(slot(actor))!==raw)throw new Error('storage readback mismatch');
  }catch{throw new Error('无法保存恢复请求；尚未发送，请保留输入并允许此页面使用会话存储。');}
}
export function loadIntent(actor:string):ImportIntent|null {
  let raw:string|null;
  try{raw=sessionStorage.getItem(slot(actor));}catch{throw new Error('无法读取恢复请求，请允许会话存储后重试。');}
  if(!raw)return null;
  try{
    if(raw.length>MAX_JSON_BYTES)throw new Error();
    const v=JSON.parse(raw) as ImportIntent;
    if(v.version!==1||!['CREATE','RECEIVE','REVISE'].includes(v.action)||!/^[0-9a-f-]{36}$/.test(v.key))throw new Error();
    const value={action:v.action,payload:v.payload,batch_id:v.batch_id};
    if(v.digest!==fingerprint(value))throw new Error();
    return v;
  }catch{throw new Error('已保存的恢复请求不可读取。请保留此页并联系管理员，勿重复创建。');}
}
export function forgetIntent(actor:string){
  try{sessionStorage.removeItem(slot(actor));if(sessionStorage.getItem(slot(actor))!==null)throw new Error();}
  catch{throw new Error('无法清除已确认的恢复请求，请检查会话存储后重试。');}
}
export async function fileMetadata(file:File,batch:string,role:FileRole):Promise<UploadMetadata>{
  if(!file.size||file.size>10*1024*1024)throw new Error('原件须为非空文件，且每份不超过 10 MiB。');
  const content_type=role==='WORKBOOK'?'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':'text/csv';
  const suffix=role==='WORKBOOK'?'.xlsx':'.csv';
  if(!file.name.toLowerCase().endsWith(suffix)||/[\\/:<\u0000-\u001f]/.test(file.name)||[...file.name].length>255)
    throw new Error('请选择不含路径或控制字符的 '+suffix+' 原件。');
  if(file.type&&file.type!==content_type)throw new Error('文件 MIME 与所选角色不一致，请选择正确的原件。');
  return {batch_id:batch,role,filename:file.name,content_type,byte_size:file.size,
    sha256:hashBytes(new Uint8Array(await file.arrayBuffer()))};
}
export function sameOriginal(a:UploadMetadata,b:UploadMetadata){
  return ['batch_id','role','filename','content_type','byte_size','sha256'].every(k=>a[k as keyof UploadMetadata]===b[k as keyof UploadMetadata]);
}


