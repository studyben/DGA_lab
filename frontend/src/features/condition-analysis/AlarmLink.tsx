import { useAuth } from '../../Auth';
import { useAlarms, type AlarmList } from './alarmApi';
import './health.css';

export function AlarmLink({filters={},description='当前设备及其当前子设备'}:{filters?:Record<string,string>;description?:string}){
  const {can}=useAuth();
  return can('analysis.read')?<ScopedAlarmLink filters={filters} description={description}/>:null;
}
function ScopedAlarmLink({filters,description}:{filters:Record<string,string>;description:string}){
  const query=new URLSearchParams({...filters,scope:'current',page_size:'1'});
  const {data,error,retry}=useAlarms<AlarmList>('?'+query);
  const target=new URLSearchParams({...filters,scope:'current',return_to:location.pathname+location.search});
  return <section className="health-panel" aria-label="未解除报警入口">
    {error?<p role="alert">{error} <button onClick={retry}>重试报警</button></p>:!data?<p role="status">正在读取报警…</p>:<a className={data.unresolved_count?'health-abnormal':''} href={'/assets/analysis/alarms?'+target}>未解除报警 {data.unresolved_count} 条</a>}
    <p className="health-help">{description}。按物理设备报警去重；确认不代表解除。当前健康状态与未解除报警可能不同，停用规则不会自动解除报警。</p>
  </section>;
}
