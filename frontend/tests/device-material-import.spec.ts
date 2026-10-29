import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import type {AddressInfo} from 'node:net';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {test,expect} from '@playwright/test';

test('默认设备物料v2模板保留显式旧版入口',async({page,baseURL})=>{
  await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  await page.goto('/assets/import');
  await expect(page.getByRole('link',{name:'下载 v2 设备物料模板'})).toBeVisible();
  await expect(page.getByRole('link',{name:'旧版设备（v1）'})).toHaveAttribute('href','/assets/import?format_version=1');
});


test('零设备现场到设备物料：编号名称核对、来源及原文件返回',async({page,baseURL})=>{
  test.setTimeout(90000);
  const origin=new URL(baseURL!).origin;
  await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  await page.goto('/assets/import?mode=SITES');
  const exported=page.waitForEvent('download');await page.getByRole('button',{name:'下载当前现场汇总'}).click();
  expect((await exported).suggestedFilename()).toMatch(/\.xlsx$/);
  await page.getByLabel('选择现场 Excel 文件').setInputFiles(path.join(process.cwd(),'tests/fixtures/site-import.xlsx'));
  await page.getByRole('button',{name:'上传现场文件并校验'}).click();
  await expect(page.getByRole('button',{name:'核对 Sites 第2行'})).toBeVisible({timeout:15000});
  await page.getByRole('button',{name:'核对 Sites 第2行'}).click();
  const siteName='S3 device intake '+Date.now();
  await page.getByLabel('现场名称',{exact:true}).fill(siteName);
  await page.getByLabel('本次核对原因',{exact:true}).fill('确认零设备现场用于后续设备资料');
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  for(const warning of await page.getByRole('checkbox',{name:/^确认警告：/}).all())await warning.check();
  await page.getByRole('button',{name:'发布客户与现场'}).click();
  await expect(page.getByRole('status').filter({hasText:'客户与现场已整批发布'})).toBeVisible();
  await page.getByRole('link',{name:'查看现场'}).click();
  await expect(page.getByText('暂无设备。',{exact:true})).toBeVisible();
  const siteId=new URL(page.url()).pathname.split('/').at(-1)!;
  await page.goto('/assets/import');
  await page.getByLabel('选择设备物料 Excel 文件').setInputFiles(path.join(process.cwd(),'tests/fixtures/device-material-import.xlsx'));
  await page.getByRole('button',{name:'上传设备物料文件并校验'}).click();
  await expect(page.getByRole('table',{name:'设备物料导入问题'})).toContainText('名称与编号不同',{timeout:15000});
  await expect(page.getByRole('button',{name:'发布设备与相关主数据'})).toBeDisabled();
  await page.getByRole('button',{name:'核对 Materials 第2行'}).click();
  await page.getByLabel('物料号',{exact:true}).fill('NEW:BROWSER/DEVICE-'+Date.now());
  await page.getByLabel('本次核对原因',{exact:true}).fill('核实本次独立物料主数据');
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  await expect(page.getByText('请逐项确认当前警告后发布。',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'核对 Assets 第2行'}).click();
  const editor=page.getByRole('region',{name:'核对编辑'});
  await expect(editor.getByLabel('现场位置',{exact:true})).toHaveCount(0);
  await expect(editor.getByLabel('已有客户编号',{exact:true})).toHaveCount(0);
  await editor.getByLabel('已有现场编号',{exact:true}).fill(siteId);
  await editor.getByLabel('本次核对原因',{exact:true}).fill('来源名称有误，明确采用已核实的现场编号');
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  await page.getByRole('checkbox',{name:/采用现场编号/}).check();
  for(const warning of await page.getByRole('checkbox',{name:/^确认警告：/}).all())await warning.check();
  const publication=page.waitForResponse(response=>response.url().endsWith('/publish')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'发布设备与相关主数据'}).click();
  const result=await (await publication).json();
  await expect(page.getByRole('status').filter({hasText:'设备与相关主数据已整批发布'})).toBeVisible();
  const target=result.operation_result.targets.find((t:{kind:string})=>t.kind==='ASSET');
  await page.getByRole('link',{name:'查看设备'}).click();
  await expect(page.getByRole('navigation',{name:'设备路径'})).toContainText(siteName);
  await expect(page.getByRole('region',{name:'设备导入来源'})).toContainText('Synthetic source note');
  await expect(page.getByRole('region',{name:'物料导入来源'})).toContainText('Synthetic material approval');
  await expect(page.getByRole('region',{name:'物料资料'})).toContainText('NEW:BROWSER/DEVICE-');
  await page.screenshot({path:'../.cache/issue50-browser/device-material-detail.png',fullPage:true});
  await page.getByRole('region',{name:'设备导入来源'}).scrollIntoViewIfNeeded();
  await page.screenshot({path:'../.cache/issue50-browser/device-source-1920.png'});
  await page.getByRole('region',{name:'设备导入来源'}).getByRole('link',{name:'查看导入批次'}).click();
  await expect(page.getByRole('region',{name:'设备物料导入预览'})).toContainText(target.system_asset_number);
  const original=page.waitForEvent('download');await page.getByRole('link',{name:'下载原始上传文件'}).click();
  expect((await original).suggestedFilename()).toContain('device-material-import');
});


async function preparedBatch(page:import('@playwright/test').Page,baseURL:string,filename:string){
  const origin=new URL(baseURL).origin;
  const login=await(await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}})).json();
  const content=await readFile(path.join(process.cwd(),'tests/fixtures/device-material-import.xlsx'));
  const uploaded=await page.request.post('/api/assets/imports?format_version=2&mode=ASSETS&filename='+filename,{headers:{Origin:origin,'X-CSRF-Token':login.csrf_token,'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','Idempotency-Key':crypto.randomUUID()},data:content});
  expect(uploaded.status()).toBe(201);
  const batch=await uploaded.json();
  await expect.poll(async()=>(await(await page.request.get('/api/assets/imports/'+batch.id)).json()).state).toBe('VALIDATED');
  const preview=await(await page.request.get('/api/assets/imports/'+batch.id)).json();
  const site=(await(await page.request.get('/api/assets/sites/20000000-0000-0000-0000-000000000001?product_line=PV')).json()).site;
  const changed=await page.request.post(`/api/assets/imports/${batch.id}/revisions`,{headers:{Origin:origin,'X-CSRF-Token':login.csrf_token},data:{expected_revision:preview.validation_revision,idempotency_key:crypto.randomUUID(),reason:'Isolated recovery preparation',changes:[{sheet:'Materials',row:2,values:{material_number:'NEW:RECOVERY/'+crypto.randomUUID()}},{sheet:'Assets',row:2,values:{serial_number:'RECOVERY-'+crypto.randomUUID(),site_name:site.site_name}}]}});
  expect(changed.status()).toBe(200);
  return changed.json();
}

test('真实发布提交后响应丢失：重载查询原意图恢复同一设备编号',async({page,baseURL})=>{
  const batch=await preparedBatch(page,baseURL!,'device-unknown-publish.xlsx');
  const before=await(await page.request.get('/api/assets/catalog')).json();
  let posts=0;let committed:{outcome:string;targets:{kind:string;target_id?:string}[]}|undefined;
  await page.route(`**/api/assets/imports/${batch.id}/publish`,async route=>{
    posts++;const response=await route.fetch();expect(response.status()).toBe(200);
    committed=(await response.json()).operation_result;expect(committed!.outcome).toBe('PUBLISHED');
    await route.abort('failed');
  });
  await page.goto('/assets/import?batch='+batch.id);
  await expect(page.getByRole('region',{name:'设备物料导入预览'})).toContainText('device-unknown-publish.xlsx');
  await expect(page.getByRole('checkbox',{name:/^确认警告：/}).first()).toBeVisible();
  for(const warning of await page.getByRole('checkbox',{name:/^确认警告：/}).all())await warning.check();
  await expect(page.getByRole('button',{name:'发布设备与相关主数据'})).toBeEnabled();
  await page.getByRole('button',{name:'发布设备与相关主数据'}).click();
  await expect(page.getByRole('alert')).toContainText('结果尚未确认');
  await page.reload();
  await page.getByRole('button',{name:'查询未确认操作'}).click();
  await expect(page.getByRole('status').filter({hasText:'设备与相关主数据已整批发布'})).toBeVisible();
  const after=await(await page.request.get('/api/assets/catalog')).json();
  expect(after.total).toBe(before.total+1);expect(posts).toBe(1);
  const current=await(await page.request.get('/api/assets/imports/'+batch.id)).json();
  expect(current.rows.find((r:{sheet:string})=>r.sheet==='Assets').target_id).toBe(committed!.targets.find(t=>t.kind==='ASSET')!.target_id);
  await page.screenshot({path:'../.cache/issue50-browser/device-recovered-publish.png',fullPage:true});
});

test('重复已发布文件先查看已有结果并明确确认另一台物理设备',async({page,baseURL})=>{
  await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  const history=await(await page.request.get('/api/assets/imports?query=device-material-import.xlsx')).json();
  const previous=history.batches.find((b:{state:string})=>b.state==='PUBLISHED');expect(previous).toBeTruthy();
  const original=await(await page.request.get('/api/assets/imports/'+previous.id)).json();
  const material=original.rows.find((r:{sheet:string})=>r.sheet==='Materials').target_key;
  const oldAsset=original.rows.find((r:{sheet:string})=>r.sheet==='Assets').target_id;
  await page.goto('/assets/import');
  await page.getByLabel('选择设备物料 Excel 文件').setInputFiles(path.join(process.cwd(),'tests/fixtures/device-material-import.xlsx'));
  await page.getByRole('button',{name:'上传设备物料文件并校验'}).click();
  const prior=page.getByRole('region',{name:'相同文件已有结果'});
  await expect(prior.getByRole('link').first()).toContainText('已整批发布',{timeout:15000});
  await page.getByRole('button',{name:'核对 Materials 第2行'}).click();
  await page.getByLabel('处理决定',{exact:true}).selectOption('REFERENCE');
  await page.getByLabel('物料号',{exact:true}).fill(material);
  await page.getByLabel('本次核对原因',{exact:true}).fill('明确复用已核实物料，另一个物理设备');
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  await page.getByRole('button',{name:'核对 Assets 第2行'}).click();
  await expect(page.getByRole('region',{name:'候选资料与差异'}).getByRole('link',{name:/查看已有设备/}).first()).toBeVisible();
  await expect(page.getByRole('checkbox',{name:/确认另一台物理设备/})).not.toBeChecked();
  await page.getByRole('button',{name:'取消编辑',exact:true}).click();
  await expect(page.getByRole('button',{name:'发布设备与相关主数据'})).toBeDisabled();
  for(const warning of await page.getByRole('checkbox',{name:/^确认警告：/}).all())await warning.check();
  const published=page.waitForResponse(response=>response.url().endsWith('/publish')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'发布设备与相关主数据'}).click();
  const result=await(await published).json();
  expect(result.operation_result.outcome).toBe('PUBLISHED');
  expect(result.operation_result.targets.find((t:{kind:string})=>t.kind==='ASSET').target_id).not.toBe(oldAsset);
});


test('旧REFRESHED操作恢复不会将后来发布误报为原操作成功',async({page,baseURL})=>{
  const origin=new URL(baseURL!).origin;
  const batch=await preparedBatch(page,baseURL!,'device-refreshed-outcome.xlsx');
  await page.goto('/assets/import?mode=SITES&batch='+batch.id);
  await expect(page.getByRole('region',{name:'设备物料导入预览'})).toContainText('device-refreshed-outcome.xlsx');
  await expect(page.getByRole('checkbox',{name:/^确认警告：/}).first()).toBeVisible();
  const login=await(await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}})).json();
  const id='20000000-0000-0000-0000-000000000001';
  const site=(await(await page.request.get(`/api/assets/sites/${id}?product_line=PV`)).json()).site;
  const changed=await page.request.put(`/api/assets/sites/${id}/basics`,{headers:{Origin:origin,'X-CSRF-Token':login.csrf_token},data:{expected_revision:site.revision,site_name:site.site_name,location_text:'Current reviewed context '+Date.now(),commissioning_date:site.commissioning_date,grid_status:site.grid_status,operation_status:site.operation_status,product_line:'PV',power_mw:site.power_mw,energy_mwh:null}});
  expect(changed.status()).toBe(200);
  // The browser's existing session token remains valid; only its cached CSRF may differ after explicit login.
  await page.reload();
  await expect(page.getByRole('checkbox',{name:/^确认警告：/}).first()).toBeVisible();
  for(const warning of await page.getByRole('checkbox',{name:/^确认警告：/}).all())await warning.check();
  let refreshed:typeof batch|undefined;
  await page.route(`**/api/assets/imports/${batch.id}/publish`,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);refreshed=await response.json();expect(refreshed.operation_result.outcome).toBe('REFRESHED');await route.abort('failed');});
  await page.getByRole('button',{name:'发布设备与相关主数据'}).click();
  await expect(page.getByRole('alert')).toContainText('结果尚未确认');
  const later=await page.request.post(`/api/assets/imports/${batch.id}/publish`,{headers:{Origin:origin,'X-CSRF-Token':login.csrf_token},data:{validation_revision:refreshed.validation_revision,idempotency_key:crypto.randomUUID(),acknowledged_warning_ids:refreshed.issues.filter((i:{severity:string})=>i.severity==='WARNING').map((i:{id:string})=>i.id)}});
  expect(later.status()).toBe(200);expect((await later.json()).operation_result.outcome).toBe('PUBLISHED');
  await page.reload();await page.getByRole('button',{name:'查询未确认操作'}).click();
  await expect(page.getByRole('status').filter({hasText:'原操作已刷新预览，请重新核对'})).toBeVisible();
  await expect(page.getByRole('status').filter({hasText:'设备与相关主数据已整批发布'})).toHaveCount(0);
  const latest=(await(await page.request.get(`/api/assets/sites/${id}?product_line=PV`)).json()).site;
  const restored=await page.request.put(`/api/assets/sites/${id}/basics`,{headers:{Origin:origin,'X-CSRF-Token':login.csrf_token},data:{expected_revision:latest.revision,site_name:site.site_name,location_text:site.location_text,commissioning_date:site.commissioning_date,grid_status:site.grid_status,operation_status:site.operation_status,product_line:'PV',power_mw:site.power_mw,energy_mwh:null}});
  expect(restored.status()).toBe(200);
});


async function suspendedMetadata(value:unknown,phase:'headers'|'body',origin:string){
  let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve;});
  let cancelled=false;
  const server=createServer(async(_request,response)=>{
    response.on('close',()=>{if(!response.writableEnded)cancelled=true;});
    const json=JSON.stringify(value);
    const headers={'Content-Type':'application/json','Access-Control-Allow-Origin':origin,'Access-Control-Allow-Credentials':'true'};
    if(phase==='body'){response.writeHead(200,headers);response.write(json.slice(0,1));response.flushHeaders();}
    await gate;
    if(!response.destroyed){if(phase==='headers')response.writeHead(200,headers);response.end(phase==='body'?json.slice(1):json);}
  });
  await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {url:`http://127.0.0.1:${(server.address() as AddressInfo).port}/metadata`,release,
    cancelled:()=>cancelled,close:async()=>{release();await new Promise<void>(resolve=>server.close(()=>resolve()));}};
}

for(const phase of ['headers','body'] as const)test(`批次metadata ${phase}挂起有界报错后重试同一实际模式`,async({page,baseURL})=>{
  test.setTimeout(50000);
  const batch=await preparedBatch(page,baseURL!,`metadata-${phase}.xlsx`);
  const stalled=await suspendedMetadata(batch,phase,new URL(baseURL!).origin);
  let reads=0;
  await page.route(`**/api/assets/imports/${batch.id}`,async route=>{
    reads++;if(reads===1)await route.fulfill({status:307,headers:{Location:stalled.url}});else await route.continue();
  });
  try{
    await page.goto('/assets/import?mode=SITES&batch='+batch.id);
    await expect(page.getByText('正在读取批次格式…',{exact:true})).toBeVisible();
    await expect(page.getByRole('alert')).toContainText('批次',{timeout:20000});
    await expect.poll(stalled.cancelled).toBe(true);
    await page.getByRole('button',{name:'重新读取批次',exact:true}).click();
    await expect(page.getByRole('region',{name:'设备物料导入预览'})).toContainText(`metadata-${phase}.xlsx`);
    await expect(page).toHaveURL(/mode=ASSETS/);
    stalled.release();
    await expect(page.getByRole('region',{name:'设备物料导入预览'})).toBeVisible();
    expect(reads).toBe(2);
  }finally{await stalled.close();}
});

test('离开挂起metadata时取消旧请求且迟到响应不覆盖新页面',async({page,baseURL})=>{
  const batch=await preparedBatch(page,baseURL!,'metadata-cancel.xlsx');
  const stalled=await suspendedMetadata(batch,'body',new URL(baseURL!).origin);
  await page.route(`**/api/assets/imports/${batch.id}`,route=>route.fulfill({status:307,headers:{Location:stalled.url}}));
  try{
    await page.goto('/assets/import?batch='+batch.id);
    await expect(page.getByText('正在读取批次格式…',{exact:true})).toBeVisible();
    await page.getByRole('link',{name:'仅现场信息（v2）',exact:true}).click();
    await expect(page.getByRole('region',{name:'仅现场导入'})).toBeVisible();
    await expect.poll(stalled.cancelled).toBe(true);
    stalled.release();
    await expect(page.getByRole('region',{name:'仅现场导入'})).toBeVisible();
    await expect(page.getByRole('region',{name:'设备物料导入预览'})).toHaveCount(0);
  }finally{await stalled.close();}
});


for(const transport of ['abort','503','401','403','409'] as const)test(`原修订${transport}未提交后重载恢复精确输入并同键重试`,async({page,baseURL})=>{
  const batch=await preparedBatch(page,baseURL!,`revision-${transport}-recovery.xlsx`);
  const note='Exact retained recovery note 7124\n'+'中文依据。'.repeat(220);
  const reason='保留原修订原因与精确输入 7421';
  let operationReads=0;const requests:string[]=[];
  page.on('request',request=>{if(request.url().includes('/api/assets/imports/operations/'))operationReads++;});
  await page.route(`**/api/assets/imports/${batch.id}/revisions`,async route=>{
    if(route.request().method()!=='POST'){await route.continue();return;}
    requests.push(route.request().postData()!);
    if(requests.length===1){if(transport==='abort')await route.abort('failed');else await route.fulfill({status:Number(transport),json:{code:transport==='401'?'session_expired':transport==='403'?'permission_denied':transport==='409'?'unknown_gateway_conflict':'import_revision_unavailable'}});}
    else await route.continue();
  });
  await page.goto('/assets/import?batch='+batch.id);
  await page.getByRole('button',{name:'核对 Assets 第2行'}).click();
  await page.getByLabel('来源备注',{exact:true}).fill(note);
  await page.getByLabel('本次核对原因',{exact:true}).fill(reason);
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('alert')).toContainText(/未确认|连接中断|没有此操作权限|登录已失效|操作未成功/);
  const unchanged=await(await page.request.get('/api/assets/imports/'+batch.id)).json();
  expect(unchanged.validation_revision).toBe(batch.validation_revision);
  if(transport!=='abort'){
    await page.getByRole('button',{name:'退出登录',exact:true}).click();
    await page.getByLabel('用户名',{exact:true}).fill('browser-admin');
    await page.getByLabel('密码',{exact:true}).fill('Browser changed passphrase 84!');
    await page.getByRole('button',{name:'登录',exact:true}).click();
    await expect(page.getByRole('button',{name:'退出登录',exact:true})).toBeVisible();
  }
  await page.goto('/assets/import?batch='+batch.id);
  await expect(page.getByRole('region',{name:'设备物料导入预览'})).toBeVisible();
  await page.getByRole('button',{name:'查询未确认操作'}).click();
  const restored=page.getByRole('region',{name:'未确认原修订'});
  await expect(restored.getByLabel('恢复的来源备注',{exact:true})).toHaveValue(note);
  await expect(restored.getByLabel('恢复的核对原因',{exact:true})).toHaveValue(reason);
  await expect(restored).toContainText('原核对修订 '+batch.validation_revision);
  await restored.getByRole('button',{name:'使用原操作重试修订',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  expect(requests).toHaveLength(2);expect(requests[1]).toBe(requests[0]);
  const applied=await(await page.request.get('/api/assets/imports/'+batch.id)).json();
  expect(applied.validation_revision).toBe(batch.validation_revision+1);
  expect(applied.rows.find((row:{sheet:string})=>row.sheet==='Assets').values.source_note).toBe(note);
  await expect(restored).toHaveCount(0);
  expect(operationReads).toBe(2);
  await page.getByRole('button',{name:'查询未确认操作'}).click();
  await expect(page.getByRole('status').filter({hasText:'未找到已完成的未确认操作'})).toBeVisible();
  expect(operationReads).toBe(2);
});


test('保存原修订存储失败时保留编辑输入并阻止请求',async({page,baseURL})=>{
  const batch=await preparedBatch(page,baseURL!,'revision-storage-failure.xlsx');
  await page.addInitScript(()=>{
    const original=Storage.prototype.setItem;let failed=false;
    Storage.prototype.setItem=function(key,value){if(!failed&&key.startsWith('dga-asset-import-pending:')&&JSON.parse(value).kind==='revise'){failed=true;throw new DOMException('Isolated storage outage','QuotaExceededError');}return original.call(this,key,value);};
  });
  let posts=0;page.on('request',request=>{if(request.method()==='POST'&&request.url().endsWith(`/imports/${batch.id}/revisions`))posts++;});
  await page.goto('/assets/import?batch='+batch.id);
  await page.getByRole('button',{name:'核对 Assets 第2行'}).click();
  await page.getByLabel('来源备注',{exact:true}).fill('Storage failure must preserve this exact note');
  await page.getByLabel('本次核对原因',{exact:true}).fill('Storage outage must not dispatch');
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('alert')).toContainText('无法安全保存原操作及修订输入');
  expect(posts).toBe(0);
  await expect(page.getByLabel('来源备注',{exact:true})).toHaveValue('Storage failure must preserve this exact note');
  await expect(page.getByLabel('本次核对原因',{exact:true})).toHaveValue('Storage outage must not dispatch');
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  expect(posts).toBe(1);
});

for(const outcome of ['missing','committed'] as const)test(`旧SITES无payload修订${outcome}只按已存在事实恢复`,async({page,baseURL})=>{
  const origin=new URL(baseURL!).origin;
  const login=await(await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}})).json();
  const uploaded=await page.request.post('/api/assets/imports?format_version=2&mode=SITES&filename=legacy-sites-pending.xlsx',{headers:{Origin:origin,'X-CSRF-Token':login.csrf_token,'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','Idempotency-Key':crypto.randomUUID()},data:await readFile(path.join(process.cwd(),'tests/fixtures/site-import.xlsx'))});
  expect(uploaded.status()).toBe(201);const batch=await uploaded.json();
  await expect.poll(async()=>(await(await page.request.get('/api/assets/imports/'+batch.id)).json()).state).toBe('VALIDATED');
  let wire='';let posts=0;const operationKeys:string[]=[];
  page.on('request',request=>{if(request.url().includes('/api/assets/imports/operations/'))operationKeys.push(request.url().split('/').at(-1)!);});
  await page.route(`**/api/assets/imports/${batch.id}/revisions`,async route=>{
    if(route.request().method()!=='POST'){await route.continue();return;}
    posts++;wire=route.request().postData()!;
    if(outcome==='committed'){const response=await route.fetch();expect(response.status()).toBe(200);}
    await route.abort('failed');
  });
  await page.goto('/assets/import?mode=SITES&batch='+batch.id);
  await page.getByRole('button',{name:'核对 Sites 第2行'}).click();
  await page.getByLabel('来源备注',{exact:true}).fill('Legacy exact note never fabricated');
  await page.getByLabel('本次核对原因',{exact:true}).fill('Legacy pending revision reason');
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('alert')).toContainText('结果尚未确认');
  const {idempotency_key,...payload}=JSON.parse(wire);
  const pending={key:idempotency_key,kind:'revise',digest:createHash('sha256').update(JSON.stringify(payload)).digest('hex'),batch:batch.id};
  // Arrange a documented old browser storage format, never React component state.
  await page.evaluate(({key,pending})=>sessionStorage.setItem(key,JSON.stringify(pending)),{key:'dga-site-import-pending:'+login.actor.id,pending});
  await page.reload();await page.getByRole('button',{name:'查询未确认操作'}).click();
  if(outcome==='committed'){
    await expect(page.getByRole('status').filter({hasText:'已找到原操作结果'})).toBeVisible();
    await expect(page.getByRole('region',{name:'现场导入预览'})).toContainText('Legacy exact note never fabricated');
  }else{
    await expect(page.getByRole('status').filter({hasText:'旧版本只保存了修订摘要'})).toContainText('旧版本只保存了修订摘要');
    await expect(page.getByRole('status').filter({hasText:'旧版本只保存了修订摘要'})).toContainText('原操作键仍保留');
    await expect(page.getByRole('region',{name:'未确认原修订'})).toHaveCount(0);
    await page.getByRole('button',{name:'核对 Sites 第2行'}).click();
    await expect(page.getByLabel('来源备注',{exact:true})).not.toHaveValue('Legacy exact note never fabricated');
    await page.getByLabel('来源备注',{exact:true}).fill('Different input cannot replace the old intent');
    await page.getByLabel('本次核对原因',{exact:true}).fill('Different request');
    await page.getByRole('button',{name:'保存核对并重新校验'}).click();
    await expect(page.getByRole('alert')).toContainText('仍有未确认操作');
  }
  expect(posts).toBe(1);expect(operationKeys.length).toBeGreaterThan(0);
  expect(operationKeys.every(key=>key===idempotency_key)).toBe(true);
});


test('合法2000码点非BMP来源备注在修改其他字段和恢复原修订时保持完整',async({page,baseURL})=>{
  const batch=await preparedBatch(page,baseURL!,'revision-unicode-bound.xlsx');
  const origin=new URL(baseURL!).origin;
  const login=await(await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}})).json();
  const note='🙂'.repeat(2000);
  // Arrange server-accepted current provenance through the public revision API.
  const accepted=await page.request.post(`/api/assets/imports/${batch.id}/revisions`,{headers:{Origin:origin,'X-CSRF-Token':login.csrf_token},data:{expected_revision:batch.validation_revision,idempotency_key:crypto.randomUUID(),reason:'Accepted 2000 Unicode codepoints',changes:[{sheet:'Assets',row:2,values:{source_note:note}}]}});
  expect(accepted.status()).toBe(200);const original=await accepted.json();
  expect(original.rows.find((row:{sheet:string})=>row.sheet==='Assets').values.source_note).toBe(note);
  const wires:string[]=[];
  await page.route(`**/api/assets/imports/${batch.id}/revisions`,async route=>{
    if(route.request().method()!=='POST'){await route.continue();return;}
    wires.push(route.request().postData()!);if(wires.length===1)await route.abort('failed');else await route.continue();
  });
  await page.goto('/assets/import?batch='+batch.id);
  await page.getByRole('button',{name:'核对 Assets 第2行'}).click();
  await expect(page.getByLabel('来源备注',{exact:true})).toHaveValue(note);
  await page.getByLabel('设备名称',{exact:true}).fill('Review another field without truncating provenance');
  await page.getByLabel('本次核对原因',{exact:true}).fill('Preserve the exact approved Unicode note');
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('alert')).toContainText('结果尚未确认');
  expect(wires).toHaveLength(1);
  await page.reload();await page.getByRole('button',{name:'查询未确认操作'}).click();
  const restored=page.getByRole('region',{name:'未确认原修订'});
  await expect(restored.getByLabel('恢复的来源备注',{exact:true})).toHaveValue(note);
  await restored.getByRole('button',{name:'使用原操作重试修订'}).click();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  expect(wires).toHaveLength(2);expect(wires[1]).toBe(wires[0]);
  const after=await(await page.request.get('/api/assets/imports/'+batch.id)).json();
  expect(after.rows.find((row:{sheet:string})=>row.sheet==='Assets').values.source_note).toBe(note);
  expect(after.validation_revision).toBe(original.validation_revision+1);
});


test('服务器明确拒绝过期修订后保留输入并允许重读复核的新意图',async({page,baseURL,playwright})=>{
  const batch=await preparedBatch(page,baseURL!,'revision-definitive-stale.xlsx');
  const desired='Desired editor note survives a known stale rejection';
  const wires:string[]=[];
  page.on('request',request=>{if(request.method()==='POST'&&request.url().endsWith(`/imports/${batch.id}/revisions`))wires.push(request.postData()!);});
  await page.goto('/assets/import?batch='+batch.id);
  await page.getByRole('button',{name:'核对 Assets 第2行'}).click();
  await page.getByLabel('来源备注',{exact:true}).fill(desired);
  await page.getByLabel('本次核对原因',{exact:true}).fill('Original desired review');
  const other=await playwright.request.newContext({baseURL});
  try{
    const origin=new URL(baseURL!).origin;
    const login=await other.post('/api/auth/login',{headers:{Origin:origin},data:{username:'identity-lab-manager',password:'Browser changed passphrase 84!'}});
    expect(login.status()).toBe(200);const session=await login.json();
    const advanced=await other.post(`/api/assets/imports/${batch.id}/revisions`,{headers:{Origin:origin,'X-CSRF-Token':session.csrf_token},data:{expected_revision:batch.validation_revision,idempotency_key:crypto.randomUUID(),reason:'Another actor reviewed this row',changes:[{sheet:'Assets',row:2,values:{source_note:'Concurrent actor reviewed note'}}]}});
    expect(advanced.status()).toBe(200);const current=await advanced.json();
    const rejected=page.waitForResponse(response=>response.url().endsWith(`/imports/${batch.id}/revisions`)&&response.request().method()==='POST');
    await page.getByRole('button',{name:'保存核对并重新校验'}).click();
    const failure=await rejected;expect(failure.status()).toBe(409);expect((await failure.json()).code).toBe('import_stale_validation');
    await expect(page.getByRole('alert')).toContainText('预览已变化');
    await expect(page.getByLabel('来源备注',{exact:true})).toHaveValue(desired);
    const oldKey=JSON.parse(wires[0]).idempotency_key;
    expect((await page.request.get('/api/assets/imports/operations/'+oldKey)).status()).toBe(404);
    await page.getByRole('button',{name:'重新读取批次',exact:true}).click();
    await expect(page.getByRole('region',{name:'设备物料导入预览'})).toContainText('核对修订 '+current.validation_revision);
    await expect(page.getByRole('region',{name:'设备物料导入预览'})).toContainText('Concurrent actor reviewed note');
    await expect(page.getByLabel('来源备注',{exact:true})).toHaveValue(desired);
    await page.getByLabel('本次核对原因',{exact:true}).fill('Reviewed the current revision and reaffirmed my desired note');
    await page.getByRole('button',{name:'保存核对并重新校验'}).click();
    await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
    expect(wires).toHaveLength(2);
    const next=JSON.parse(wires[1]);expect(next.idempotency_key).not.toBe(oldKey);
    expect(next.expected_revision).toBe(current.validation_revision);
    expect(next.changes[0].values.source_note).toBe(desired);
    const applied=await(await page.request.get('/api/assets/imports/'+batch.id)).json();
    expect(applied.validation_revision).toBe(current.validation_revision+1);
    expect(applied.rows.find((row:{sheet:string})=>row.sheet==='Assets').values.source_note).toBe(desired);
  }finally{await other.dispose();}
});


test('另一经理发布后明确拒绝修订仍保留输入并允许新批次工作',async({page,baseURL,playwright})=>{
  const batch=await preparedBatch(page,baseURL!,'revision-terminal-published.xlsx');
  const desired='Keep this desired draft after another manager publishes';
  let revisionPosts=0,uploadPosts=0;const uploadName='after-published-rejection-'+crypto.randomUUID()+'.xlsx';
  page.on('request',request=>{
    if(request.method()==='POST'&&request.url().endsWith(`/imports/${batch.id}/revisions`))revisionPosts++;
    if(request.method()==='POST'&&request.url().includes('filename='+uploadName))uploadPosts++;
  });
  await page.goto('/assets/import?batch='+batch.id);
  await page.getByRole('button',{name:'核对 Assets 第2行'}).click();
  await page.getByLabel('来源备注',{exact:true}).fill(desired);
  await page.getByLabel('本次核对原因',{exact:true}).fill('Desired draft during publication race');
  const other=await playwright.request.newContext({baseURL});
  try{
    const origin=new URL(baseURL!).origin;
    const login=await other.post('/api/auth/login',{headers:{Origin:origin},data:{username:'identity-lab-manager',password:'Browser changed passphrase 84!'}});
    expect(login.status()).toBe(200);const session=await login.json();
    const publication=await other.post(`/api/assets/imports/${batch.id}/publish`,{headers:{Origin:origin,'X-CSRF-Token':session.csrf_token},data:{validation_revision:batch.validation_revision,idempotency_key:crypto.randomUUID(),acknowledged_warning_ids:batch.issues.filter((issue:{severity:string})=>issue.severity==='WARNING').map((issue:{id:string})=>issue.id)}});
    expect(publication.status()).toBe(200);expect((await publication.json()).operation_result.outcome).toBe('PUBLISHED');
    const rejected=page.waitForResponse(response=>response.url().endsWith(`/imports/${batch.id}/revisions`)&&response.request().method()==='POST');
    await page.getByRole('button',{name:'保存核对并重新校验'}).click();
    const failure=await rejected;expect(failure.status()).toBe(409);expect((await failure.json()).code).toBe('import_already_published');
    await expect(page.getByRole('alert')).toContainText('批次已发布');
    await expect(page.getByLabel('来源备注',{exact:true})).toHaveValue(desired);
    await page.getByRole('button',{name:'重新读取批次',exact:true}).click();
    await expect(page.getByRole('region',{name:'设备物料导入预览'})).toContainText('已整批发布');
    await expect(page.getByLabel('来源备注',{exact:true})).toHaveValue(desired);
    await expect(page.getByRole('button',{name:'保存核对并重新校验'})).toBeDisabled();
    await page.getByLabel('选择设备物料 Excel 文件').setInputFiles({name:uploadName,mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:await readFile(path.join(process.cwd(),'tests/fixtures/device-material-import.xlsx'))});
    await page.getByRole('button',{name:'上传设备物料文件并校验'}).click();
    await expect.poll(()=>uploadPosts).toBe(1);
    await expect(page.getByRole('region',{name:'设备物料导入预览'})).toContainText(uploadName);
    expect(revisionPosts).toBe(1);
    const original=await(await page.request.get('/api/assets/imports/'+batch.id)).json();
    expect(original.state).toBe('PUBLISHED');
    expect(original.rows.find((row:{sheet:string})=>row.sheet==='Assets').values.source_note).not.toBe(desired);
  }finally{await other.dispose();}
});
