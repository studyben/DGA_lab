import {sha256} from '@noble/hashes/sha2.js';
import {bytesToHex} from '@noble/hashes/utils.js';

/** Intent digests are also needed on the ordinary-HTTP local deployment. */
export function importPayloadDigest(bytes:ArrayBuffer|Uint8Array):string {
  return bytesToHex(sha256(bytes instanceof Uint8Array?bytes:new Uint8Array(bytes)));
}

/** CSPRNG UUIDv4; getRandomValues is available without a secure-context origin. */
export function newImportIntentKey():string {
  if(!globalThis.crypto?.getRandomValues)throw new Error('浏览器缺少安全随机数能力，请使用受支持的浏览器。');
  const bytes=crypto.getRandomValues(new Uint8Array(16));
  bytes[6]=(bytes[6]&15)|64;
  bytes[8]=(bytes[8]&63)|128;
  const hex=bytesToHex(bytes);
  return [hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join('-');
}


/** Stored batch metadata selects the route, including historical batch-only links. */
export function importBatchHref(batch:{id:string;format_version?:number;mode?:string}):string {
  const query=new URLSearchParams(batch.format_version===2?{mode:batch.mode??'ASSETS'}:{format_version:'1'});
  query.set('batch',batch.id);
  return '/assets/import?'+query.toString();
}
