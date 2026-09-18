export type Rule = {
  id: string; name: string; test_type: string; analyte: string; method_version_id: string; unit: string;
  asset_id: string | null; priority: number; effective_from: string; effective_to: string | null;
  operator: string; threshold: string; severity: string; state: string; revision: number;
  approved_by: string | null; approved_at: string | null;
};
export type Method = { id: string; name: string; version_label: string; test_type: string;
  configured: boolean; is_active: boolean; fields: { code: string; unit_code: string | null }[] };
export const statusNames: Record<string,string> = { UNASSESSED:'未评估',NORMAL:'正常（已评估项）',ATTENTION:'关注',WARNING:'警示',CRITICAL:'严重',DRAFT:'草稿',ACTIVE:'已启用',RETIRED:'已停用' };
export const reasons: Record<string,string> = { no_finalized_results:'没有已定稿的检测结果',method_not_configured:'方法配置尚未完成',missing_unit:'缺少单位',qualified_result:'限定结果，不作精确数值判断',no_applicable_rule:'没有适用的已启用规则' };
const errors: Record<string,string> = { rule_scope_conflict:'同优先级规则的适用范围与生效时间重叠，请调整后重试。',rule_revision_conflict:'规则已被其他操作更新。请重新加载列表并核对，当前输入仍保留。',rule_not_draft:'已批准的规则不可直接修改，请复制为新草稿。',invalid_rule_transition:'规则状态已变化，请重新加载。',rule_method_not_configured:'请先在实验室配置中完成方法配置。',rule_method_unit_mismatch:'结果项或单位与方法不一致，请重新选择方法。',health_inputs_changed:'设备或检测结果正在变化，请稍后刷新。',ambiguous_asset_hierarchy:'设备安装历史存在时间冲突，暂不能评估。',invalid_input:'请检查必填项、数字范围和生效时间。',permission_denied:'当前账号没有此操作权限。',session_expired:'登录已失效，请重新登录。' };
export async function healthRequest<T>(path:string, init:RequestInit={}):Promise<T>{
  const response=await fetch('/api/condition-analysis'+path,{cache:'no-store',...init});
  const body=await response.json().catch(()=>null);
  if(!response.ok) throw new Error(errors[body?.code] ?? (response.status===401?'登录已失效，请重新登录。':'健康分析服务暂不可用，请重试。'));
  return body as T;
}
