import {test,expect,type Page} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test.describe.configure({timeout:90000});
const root='/api/laboratory/imports';
const samples='source_lab_key,source_lab_name,external_sample_id,source_site_name,source_whole_unit_serial,source_transformer_serial,formal_asset_id,system_asset_number,sampled_at,sampled_timezone,sampling_context,physical_received,received_at,received_timezone,container_count,report_filenames,notes,source_note'.split(',');
const tests='source_lab_key,external_sample_id,external_test_id,test_type,measured_at,measured_timezone,source_method,source_method_version,method_version_id,report_selected,source_instrument,source_analyst,source_qa,h2_value,h2_qualifier,h2_unit,ch4_value,ch4_qualifier,ch4_unit,c2h2_value,c2h2_qualifier,c2h2_unit,c2h4_value,c2h4_qualifier,c2h4_unit,c2h6_value,c2h6_qualifier,c2h6_unit,co_value,co_qualifier,co_unit,co2_value,co2_qualifier,co2_unit,result_value,result_qualifier,result_unit,notes,source_note'.split(',');
function csv(columns:string[],rows:Record<string,string>[]){
  return Buffer.from([columns,...rows.map(r=>columns.map(k=>r[k]??''))].map(row=>row.map(v=>'"'+v.replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n');
}
function evidence(sourceNote='Source note is independent'){
  const sample=csv(samples,[{source_lab_key:'LAB_A',source_lab_name:'Unconfirmed source evidence',external_sample_id:'00017',
    sampled_at:'2026-10-25',physical_received:'FALSE',container_count:'0',report_filenames:'["third-party.pdf"]',
    notes:'Business note,\nsecond line',source_note:sourceNote}]);
  const values:Record<string,string>[]=[];
  for(let n=1;n<=22;n++){
    const row:Record<string,string>={source_lab_key:'LAB_A',external_sample_id:n===22?'00099':'00017',
      external_test_id:'DGA-'+String(n).padStart(2,'0'),test_type:'DGA',measured_at:'2026-11-01T01:30:00',
      measured_timezone:'America/Chicago',source_method:'Unapproved third-party method',source_analyst:'Original detector',
      source_instrument:'Source instrument',source_qa:'Source QA evidence',notes:'Complete test '+n,source_note:'External report evidence '+n};
    for(const gas of ['h2','ch4','c2h2','c2h4','c2h6','co','co2']){
      row[gas+'_value']=gas==='ch4'?'':gas==='h2'?'0':'1.000';
      row[gas+'_qualifier']=gas==='ch4'?'ND':'EQ';row[gas+'_unit']='';
    }
    values.push(row);
  }
  return {sample,tests:csv(tests,values)};
}
async function login(page:Page,baseURL:string|undefined){
  const r=await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},
    data:{username:process.env.LAB_IMPORT_BROWSER_USERNAME??'browser-admin',password:process.env.LAB_IMPORT_BROWSER_PASSWORD??'Browser changed passphrase 84!'}});
  expect(r.ok()).toBeTruthy();
}
async function uploadPair(page:Page){
  const data=evidence();
  await page.goto('/lab/imports');await page.getByLabel('原件格式',{exact:true}).selectOption('CSV_PAIR');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toBeVisible();
  for(const [label,name,buffer] of [['油样信息 CSV','samples-staging.csv',data.sample],['检测结果 CSV','tests-staging.csv',data.tests]] as const){
    await page.getByLabel('选择'+label+'原件').setInputFiles({name,mimeType:'text/csv',buffer});
    await page.getByRole('button',{name:'保存'+label+'原件',exact:true}).click();
    await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText(name);
  }
  return data;
}
test.beforeEach(async({page})=>{await page.addInitScript(()=>{
  Object.defineProperty(crypto,'subtle',{value:undefined});Object.defineProperty(crypto,'randomUUID',{value:undefined});
});});
test('双表原件显式后台校验后查看问题、完整检测分页并重开保留原件',async({page,baseURL})=>{
  await login(page,baseURL);const data=await uploadPair(page);
  await expect(page.getByRole('button',{name:'校验暂存资料',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
  await expect(page.getByRole('region',{name:'校验问题'})).toContainText('ambiguous_local_time');
  await page.getByLabel('问题业务表',{exact:true}).selectOption('油样信息');
  await page.getByRole('button',{name:/^定位 油样信息 第2行/}).first().click();
  const sample=page.getByRole('region',{name:'油样与关联检测预览'});
  await expect(sample).toContainText('00017');
  await expect(sample).toContainText('日期（未补造时刻）');
  await expect(sample).toContainText('third-party.pdf');
  await expect(sample).toContainText('已声明，未提供文件');
  await expect(sample.getByRole('table',{name:'关联检测'})).toContainText('DGA-20');
  await page.getByRole('button',{name:'下一页关联检测',exact:true}).click();
  await expect(sample.getByRole('table',{name:'关联检测'})).toContainText('DGA-21');
  await page.getByRole('button',{name:'查看检测 DGA-21',exact:true}).click();
  await expect(page.getByRole('region',{name:'检测原始与解析证据'})).toContainText('Original detector');
  await expect(page.getByRole('region',{name:'检测原始与解析证据'})).toContainText('ND');
  await page.getByRole('button',{name:'查看未关联检测',exact:true}).click();
  await expect(page.getByRole('region',{name:'未关联检测'})).toContainText('DGA-22');
  const reopen=page.url();await page.goto('/lab');await page.goto(reopen);
  await expect(page.getByRole('region',{name:'未关联检测'})).toContainText('DGA-22');
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'下载原件：tests-staging.csv',exact:true}).click();
  expect(await readFile((await (await downloadPromise).path())!)).toEqual(data.tests);
  await expect(page.getByRole('button',{name:/发布|定稿/})).toHaveCount(0);
  await page.screenshot({path:'test-results/laboratory-import-staging-preview.png',fullPage:true});
});


test('第21个检测问题准确定位页2；同版本重新校验的丢失响应恢复原操作，修改后旧结果明确过期',async({page,baseURL})=>{
  await login(page,baseURL);await uploadPair(page);
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
  await page.getByLabel('问题代码',{exact:true}).fill('ambiguous_local_time');
  await page.getByRole('button',{name:'定位 检测结果 第22行 measured_at',exact:true}).click();
  const detail=page.getByRole('region',{name:'检测原始与解析证据'});
  await expect(detail).toContainText('DGA-21');
  await expect(page.getByRole('cell',{name:'measured_at 原始值',exact:true})).toBeFocused();
  expect(new URL(page.url()).searchParams.get('test_page')).toBe('2');
  const sourceUrl=page.url();await page.goto('/lab');await page.goto(sourceUrl);
  await expect(page.getByRole('region',{name:'检测原始与解析证据'})).toContainText('DGA-21');
  await expect(page.getByRole('cell',{name:'measured_at 原始值',exact:true})).toBeFocused();
  const issueCode=page.getByLabel('问题代码',{exact:true});
  await issueCode.fill('unit_required');
  await expect(page.getByRole('region',{name:'校验问题'})).toContainText('unit_required');
  await expect(issueCode).toBeFocused();
  let posts=0,key='';
  await page.route('**/api/laboratory/imports/*/validations',async r=>{
    if(r.request().method()==='POST'){
      posts++;key=r.request().headers()['idempotency-key'];
      const response=await r.fetch();expect(response.status()).toBe(202);await r.abort('failed');
    }else await r.continue();
  });
  await page.getByRole('button',{name:'重新校验暂存资料',exact:true}).dblclick({delay:20});
  await expect(page.getByRole('alert')).toContainText('尚未确认');
  await page.reload();
  await expect(page.getByText(/已确认操作：QUEUED/)).toBeVisible();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
  expect(posts).toBe(1);
  const operation=await (await page.request.get(root+'/operations/'+key)).json();
  expect(operation.result.outcome).toBe('QUEUED');
  const id=new URL(page.url()).searchParams.get('batch');
  const current=await (await page.request.get(root+'/'+id)).json();
  expect(operation.result.applied_revision).toBe(current.revision);
  expect(operation.result.job_id).toBe(current.current_job.id);
  expect(current.current_job.state).toBe('COMPLETE');
  await page.unroute('**/api/laboratory/imports/*/validations');
  await page.getByText('核对用途、来源时区与身份',{exact:true}).click();
  await page.getByLabel('核对导入用途',{exact:true}).selectOption('DAILY');
  await page.getByLabel('本次核对原因',{exact:true}).fill('Changed purpose requires fresh validation');
  await page.getByRole('button',{name:'保存元数据与来源核对',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('已过期');
  await expect(page.getByRole('region',{name:'暂存校验状态'}).getByText(/^当前校验结果：/)).toHaveCount(0);
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
});
test('文件级编码错误保留原件并显示问题，不显示部分油样',async({page,baseURL})=>{
  await login(page,baseURL);const data=evidence();
  await page.goto('/lab/imports');await page.getByLabel('原件格式',{exact:true}).selectOption('CSV_PAIR');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  for(const [label,name,buffer] of [['油样信息 CSV','valid-samples.csv',data.sample],['检测结果 CSV','invalid-tests.csv',Buffer.from([255])]] as const){
    await page.getByLabel('选择'+label+'原件').setInputFiles({name,mimeType:'text/csv',buffer});
    await page.getByRole('button',{name:'保存'+label+'原件',exact:true}).click();
    await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText(name);
  }
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'校验问题'})).toContainText('invalid_utf8',{timeout:45000});
  await expect(page.getByRole('table',{name:'暂存油样'}).getByRole('row')).toHaveCount(1);
  await page.getByRole('button',{name:'查看文件问题',exact:true}).click();
  await expect(page.getByRole('heading',{name:'校验问题',exact:true})).toBeFocused();
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'下载原件：invalid-tests.csv',exact:true}).click();
  expect(await readFile((await (await downloadPromise).path())!)).toEqual(Buffer.from([255]));
});




test('单行核对保留2000个非BMP来源备注、纠正DST问题并显式重验，原始值与原件不变',async({page,baseURL})=>{
  await login(page,baseURL);const data=await uploadPair(page);
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
  await page.getByRole('button',{name:'查看油样 00017',exact:true}).click();
  await page.getByRole('button',{name:'下一页关联检测',exact:true}).click();
  await page.getByRole('button',{name:'查看检测 DGA-21',exact:true}).click();
  await expect(page.getByRole('button',{name:'核对检测 DGA-21',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'核对检测 DGA-21',exact:true}).click();
  const sourceNote=page.getByLabel('核对 source_note',{exact:true});
  let revisions=0;
  page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/revisions'))revisions++;});
  await sourceNote.fill('😀'.repeat(2001));
  await expect(page.getByRole('region',{name:'本行核对'})).toContainText('2001/2000');
  expect(Array.from(await sourceNote.inputValue())).toHaveLength(2001);
  await expect(page.getByRole('button',{name:'保存本行核对',exact:true})).toBeDisabled();
  expect(revisions).toBe(0);
  await sourceNote.fill('😀'.repeat(2000));
  await page.getByLabel('核对 measured_at',{exact:true}).fill('2026-11-01T01:30:00-05:00');
  await page.getByLabel('本行核对原因',{exact:true}).fill('Correct explicit source instant and preserve source note');
  await sourceNote.scrollIntoViewIfNeeded();
  await page.screenshot({path:'test-results/laboratory-import-row-note-boundary.png'});
  await page.evaluate(()=>{const original=Storage.prototype.setItem;let failed=false;Storage.prototype.setItem=function(key,value){if(!failed&&key.startsWith('dga:lab-import:v1:')){failed=true;throw new DOMException('test quota','QuotaExceededError');}return original.call(this,key,value);};});
  await page.getByRole('button',{name:'保存本行核对',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('尚未发送');
  expect(revisions).toBe(0);
  await expect(sourceNote).toHaveValue('😀'.repeat(2000));
  const saved=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/revisions'));
  await page.getByRole('button',{name:'保存本行核对',exact:true}).click();
  expect((await saved).status()).toBe(200);expect(revisions).toBe(1);
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('已过期');
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
  const detail=page.getByRole('region',{name:'检测原始与解析证据'});
  await expect(detail.getByRole('cell',{name:'source_note 原始值',exact:true})).toContainText('External report evidence 21');
  await expect(detail.getByRole('cell',{name:'source_note 核对值',exact:true})).toHaveText('😀'.repeat(2000));
  await expect(detail).toContainText('2026-11-01T06:30:00Z');
  const rowId=new URL(page.url()).searchParams.get('row')!;
  await page.getByLabel('问题代码',{exact:true}).fill('ambiguous_local_time');
  await page.getByLabel('问题行 ID',{exact:true}).fill(rowId);
  await expect(page.getByRole('table',{name:'暂存校验问题'}).getByRole('row')).toHaveCount(1);
  const url=page.url();await page.goto('/lab');await page.goto(url);
  await expect(page.getByRole('region',{name:'检测原始与解析证据'})).toContainText('2026-11-01T06:30:00Z');
  const history=page.getByRole('region',{name:'暂存修订历史'});
  await expect(history).toContainText('Correct explicit source instant');
  const rowHistory=history.getByRole('row').filter({hasText:'检测结果 第22行'}).first();
  await rowHistory.getByText('查看此修订的前后资料',{exact:true}).click();
  const changes=rowHistory.getByRole('table',{name:'行字段修订前后'});
  await expect(changes).toContainText('source_note');
  await expect(changes).toContainText('External report evidence 21');
  await expect(changes).toContainText('😀'.repeat(2000));
  const download=page.waitForEvent('download');
  await page.getByRole('link',{name:'下载原件：tests-staging.csv',exact:true}).click();
  expect(await readFile((await (await download).path())!)).toEqual(data.tests);
});




test('未知行修订跨404和503/403仍重放原请求；明确过期拒绝后才准备新版本',async({page,baseURL})=>{
  await login(page,baseURL);await uploadPair(page);
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
  await page.getByRole('button',{name:'查看油样 00017',exact:true}).click();
  await page.getByRole('button',{name:'核对油样 00017',exact:true}).click();
  const source='Exact original request, "quoted"\nSecond line 😀';
  await page.getByLabel('核对 source_note',{exact:true}).fill(source);
  await page.getByLabel('本行核对原因',{exact:true}).fill('Source-note-only exact recovery');
  const writes:{key:string;body:string|null}[]=[];
  await page.route('**/api/laboratory/imports/*/revisions',async r=>{
    if(r.request().method()!=='POST'){await r.continue();return;}
    writes.push({key:r.request().headers()['idempotency-key'],body:r.request().postData()});
    if(writes.length===1)await r.abort('failed');
    else if(writes.length===2)await r.fulfill({status:503,contentType:'application/json',body:'{"code":"import_write_unknown"}'});
    else if(writes.length===3)await r.fulfill({status:403,contentType:'application/json',body:'{"code":"forbidden"}'});
    else await r.continue();
  });
  await page.getByRole('button',{name:'保存本行核对',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('尚未确认');
  const id=new URL(page.url()).searchParams.get('batch')!;
  const current=await (await page.request.get(root+'/'+id)).json();
  const session=await (await page.request.get('/api/auth/session')).json();
  const concurrent=await page.request.post(root+'/'+id+'/revisions',{
    headers:{Origin:new URL(baseURL!).origin,'X-CSRF-Token':session.csrf_token,'Idempotency-Key':(await import('node:crypto')).randomUUID()},
    data:{expected_revision:current.revision,reason:'Other client changed purpose',metadata:{purpose:'DAILY'}}});
  expect(concurrent.status()).toBe(200);
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('不代表原请求失败');
  await expect(page.getByLabel('核对 source_note',{exact:true})).toHaveValue(source);
  await expect(page.getByRole('region',{name:'本行核对'})).toContainText('本请求基于版本 2');
  for(const status of [503,403]){
    const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/revisions'));
    await page.getByRole('button',{name:'原样重试请求',exact:true}).click();
    expect((await response).status()).toBe(status);
    await page.reload();
    await expect(page.getByRole('alert')).toContainText('不代表原请求失败');
    await expect(page.getByRole('button',{name:'加载最新批次并准备新的核对',exact:true})).toHaveCount(0);
    await expect(page.getByLabel('核对 source_note',{exact:true})).toHaveValue(source);
  }
  await page.getByRole('button',{name:'原样重试请求',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('已被修改');
  await page.getByRole('button',{name:'查询未确认操作',exact:true}).click();
  await page.getByRole('button',{name:'加载最新批次并准备新的核对',exact:true}).click();
  await expect(page.getByLabel('核对 source_note',{exact:true})).toBeEditable();
  await expect(page.getByLabel('核对 source_note',{exact:true})).toHaveValue(source);
  await expect(page.getByRole('region',{name:'本行核对'})).toContainText('本请求基于版本 3');
  const saved=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/revisions'));
  await page.getByRole('button',{name:'保存本行核对',exact:true}).click();
  expect((await saved).status()).toBe(200);
  expect(writes).toHaveLength(5);
  for(const repeat of writes.slice(1,4))expect(repeat).toEqual(writes[0]);
  expect(writes[4].key).not.toBe(writes[0].key);
  expect(JSON.parse(writes[4].body!).changes).toEqual(JSON.parse(writes[0].body!).changes);
  expect(JSON.parse(writes[4].body!).expected_revision).toBe(3);
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
  const sample=await (await page.request.get(root+'/'+id+'/samples')).json();
  expect(sample.total).toBe(1);expect(sample.items[0].related_test_count).toBe(21);
});



test('另一核对者在同批选择自己的完整原件并校验，原上传者未确认历史持续保留且私有',async({page,baseURL})=>{
  const fixturePath=process.env.LAB_IMPORT_TWO_WRITER_FIXTURE??(await import('node:path')).resolve(process.cwd(),'../.cache/issue52-tests/s3-browser-actors.json');
  const fixture=JSON.parse(await readFile(fixturePath,'utf-8')) as {batch_url:string;b:{username:string;password:string};a_username:string;a_key:string};
  const login=await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:fixture.b});
  expect(login.ok()).toBeTruthy();
  await page.goto(fixture.batch_url);
  const history=page.getByRole('region',{name:'保留的原件历史'});
  await expect(history).toContainText('尚未确认保存');
  const stamp='writer-b-'+Date.now(),data=evidence();
  for(const [label,name,buffer] of [['油样信息 CSV',stamp+'-samples.csv',data.sample],['检测结果 CSV',stamp+'-tests.csv',data.tests]] as const){
    await page.getByLabel('选择'+label+'原件').setInputFiles({name,mimeType:'text/csv',buffer});
    await page.getByRole('button',{name:'保存'+label+'原件',exact:true}).click();
    await expect(history).toContainText(name);
    const row=history.getByRole('row').filter({hasText:name});
    if(await row.getByRole('button',{name:'改用此'+label+'原件',exact:true}).count()){
      await page.getByLabel('本次核对原因',{exact:true}).fill('B selects independently received original');
      await row.getByRole('button',{name:'改用此'+label+'原件',exact:true}).click();
      await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText(name);
    }
  }
  const corrected=evidence('B selected corrected original').sample,correctedName=stamp+'-samples-corrected.csv';
  await page.getByLabel('选择油样信息 CSV原件').setInputFiles({name:correctedName,mimeType:'text/csv',buffer:corrected});
  await page.getByRole('button',{name:'保存油样信息 CSV原件',exact:true}).click();
  await expect(history).toContainText(correctedName);
  await expect(page.getByRole('region',{name:'当前采用的原件'})).not.toContainText(correctedName);
  await page.getByLabel('本次核对原因',{exact:true}).fill('B explicitly selects corrected evidence; A history remains');
  await history.getByRole('row').filter({hasText:correctedName}).getByRole('button',{name:'改用此油样信息 CSV原件',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText(correctedName);
  await expect(history).toContainText('尚未确认保存');
  const id=new URL(page.url()).searchParams.get('batch')!;
  expect((await page.request.get(root+'/operations/'+fixture.a_key)).status()).toBe(404);
  expect((await page.content()).includes(fixture.a_key)).toBe(false);
  await expect(page.getByRole('button',{name:'校验暂存资料',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'校验暂存资料',exact:true}).click();
  await expect(page.getByRole('region',{name:'暂存校验状态'})).toContainText('待核对',{timeout:45000});
  await page.getByRole('button',{name:'查看油样 00017',exact:true}).click();
  await expect(page.getByRole('region',{name:'油样原始与解析证据'})).toContainText('B selected corrected original');
  const reopen=page.url();await page.goto('/lab');await page.goto(reopen);
  await expect(page.getByRole('region',{name:'保留的原件历史'})).toContainText('尚未确认保存');
  await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText(correctedName);
  const download=page.waitForEvent('download');
  await page.getByRole('link',{name:'下载原件：'+correctedName,exact:true}).click();
  expect(await readFile((await (await download).path())!)).toEqual(corrected);
  await expect(page.getByRole('button',{name:/取消|删除|发布|定稿/})).toHaveCount(0);
  await page.getByRole('region',{name:'保留的原件历史'}).screenshot({path:'test-results/laboratory-import-two-writer-history.png'});
});
