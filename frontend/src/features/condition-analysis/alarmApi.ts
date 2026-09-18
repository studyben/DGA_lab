import { useEffect, useState } from 'react';
import type { Rule } from './healthApi';

export type Evidence={status:string;reason:string|null;rule:Rule|null;measurement:{
  barcode:string;sampled_at:string;measured_at:string;test_id:string;sample_id:string;
  analyte:string;test_type:string;method_version_id:string;method_name:string;version_label:string;
  qualifier:string;value:string|null;unit:string|null;finalization_token:string;
  sampling_context:{site_name?:string;customer_name?:string;location_kind?:string}|null;
}};
export type Alarm={id:string;asset_id:string;test_type:string;analyte:string;state:string;severity:string;
  revision:number;opened_at:string;superseded_by:string|null;trigger:Evidence;latest_abnormal:Evidence[];
  trigger_currently_finalized:boolean;observation:{reason:string;sources:Evidence[]};
  acknowledgement:{actor_id:string;actor_name:string;at:string;note:string}|null;
  recovery:{at:string;sources:Evidence[]}|null;
  current_asset:{serial_number:string;system_asset_number:string;site_name:string|null;customer_name:string|null;product_line:string|null;location_kind:string}|null;
};
export type AlarmList={items:Alarm[];total:number;unresolved_count:number;page:number;page_size:number;checked_at:string};
export type AlarmDetail=Alarm&{checked_at:string;events:{action:string;occurred_at:string;actor_id:string|null;data:Alarm}[]};
export const alarmStates:Record<string,string>={UNACKNOWLEDGED:'待确认',ACKNOWLEDGED:'已确认',RESOLVED:'已解除'};
export const alarmStatus=(alarm:Alarm)=>alarm.superseded_by?'已并入原报警':alarmStates[alarm.state];
export const time=(value:string)=>new Date(value).toLocaleString('zh-CN');
const errors:Record<string,string>={alarm_revision_conflict:'报警已更新，请刷新详情后核对再确认。确认说明已保留。',alarm_not_open:'报警已解除或并入其他报警，请刷新详情。',alarm_note_required:'请填写确认说明。',alarm_inputs_changed:'检测或资产信息正在变化，请稍后刷新。',health_inputs_changed:'检测或资产信息正在变化，请稍后刷新。',invalid_input:'筛选条件无效，请检查日期、分页和筛选值。',alarm_not_found:'未找到该报警。',permission_denied:'当前账号无此操作权限。',session_expired:'登录已失效，请重新登录。',csrf_rejected:'会话已更新，请刷新页面后重试。'};
export async function alarmRequest<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch('/api/condition-analysis/alarms'+path,{cache:'no-store',...init});
  const body=await response.json().catch(()=>null);
  if(!response.ok)throw new Error(errors[body?.code]??'报警服务暂不可用，请重试。');
  return body as T;
}
export function useAlarms<T>(path:string){
  const [attempt,retry]=useState(0);
  const [state,setState]=useState<{path:string;data?:T;error?:string}>({path:''});
  useEffect(()=>{
    let active=true;let timer:number|undefined;
    const controller=new AbortController();setState({path});
    async function load(){
      try{const data=await alarmRequest<T>(path,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});if(active)setState({path,data});}
      catch(error){if(active)setState({path,error:error instanceof Error?error.message:'读取失败'});}
      finally{if(active)timer=window.setTimeout(()=>void load(),30000);}
    }
    void load();return()=>{active=false;controller.abort();clearTimeout(timer);};
  },[path,attempt]);
  return {data:state.path===path?state.data:undefined,error:state.path===path?state.error:undefined,retry:()=>retry(n=>n+1)};
}
