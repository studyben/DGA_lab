import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

const mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const route='/api/laboratory/imports';
async function login(page:import('@playwright/test').Page,baseURL:string|undefined) {
  const response=await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},
    data:{username:process.env.LAB_IMPORT_BROWSER_USERNAME??'browser-admin',password:process.env.LAB_IMPORT_BROWSER_PASSWORD??'Browser changed passphrase 84!'}});
  expect(response.ok()).toBeTruthy();
}
test.beforeEach(async({page})=>{
  await page.addInitScript(()=>{
    Object.defineProperty(crypto,'subtle',{value:undefined});
    Object.defineProperty(crypto,'randomUUID',{value:undefined});
  });
});
test('保存暂存原件后关闭重开，下载完整原始字节',async({page,baseURL})=>{
  await login(page,baseURL);
  await page.goto('/lab/imports');
  await expect(page.getByRole('link',{name:'下载 v1 XLSX 模板'})).toBeVisible();
  await page.getByLabel('导入用途',{exact:true}).selectOption('HISTORICAL');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toBeVisible();
  const url=page.url();
  const content=Buffer.from('Saved original evidence, not yet parsed.\r\n');
  await page.getByLabel('选择工作簿原件').setInputFiles({name:'原始 laboratory.xlsx',mimeType:mime,buffer:content});
  await page.getByRole('button',{name:'保存工作簿原件',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'原件已确认保存'})).toBeVisible();
  await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText('原始 laboratory.xlsx');
  await page.goto('/lab');
  await page.goto(url);
  await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText('原始 laboratory.xlsx');
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'下载原件：原始 laboratory.xlsx',exact:true}).click();
  const download=await downloadPromise;
  expect(await readFile((await download.path())!)).toEqual(content);
  await expect(page.getByRole('button',{name:/发布|定稿/})).toHaveCount(0);
  await page.screenshot({path:'test-results/laboratory-import-reopened.png',fullPage:true});
});



test('创建响应丢失后按原操作恢复，不重复创建',async({page,baseURL})=>{
  await login(page,baseURL);
  const before=await (await page.request.get(route)).json();
  let writes=0;
  await page.route('**/api/laboratory/imports',async r=>{
    if(r.request().method()==='POST'){writes++;const response=await r.fetch();expect(response.status()).toBe(201);await r.abort('failed');}
    else await r.continue();
  });
  await page.goto('/lab/imports');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('尚未确认');
  await page.reload();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toBeVisible();
  expect(writes).toBe(1);
  const after=await (await page.request.get(route)).json();
  expect(after.total).toBe(before.total+1);
});
test('原件响应丢失后恢复 FILE_RECEIVED，不重复上传',async({page,baseURL})=>{
  await page.addInitScript(()=>{const original=File.prototype.arrayBuffer;File.prototype.arrayBuffer=async function(){await new Promise(resolve=>setTimeout(resolve,500));return original.call(this);};});
  await login(page,baseURL);
  await page.goto('/lab/imports');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toBeVisible();
  let uploads=0;
  await page.route('**/api/laboratory/imports/*/files?*',async r=>{
    if(r.request().method()==='POST'){uploads++;const response=await r.fetch();expect(response.status()).toBe(201);await r.abort('failed');}
    else await r.continue();
  });
  await page.getByLabel('选择工作簿原件').setInputFiles({name:'uncertain-original.xlsx',mimeType:mime,buffer:Buffer.from('received once')});
  await page.getByRole('button',{name:'保存工作簿原件',exact:true}).dblclick({delay:20});
  await expect(page.getByRole('alert')).toContainText('尚未确认');
  await page.reload();
  await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText('uncertain-original.xlsx');
  await expect(page.getByRole('region',{name:'未确认操作'})).toHaveCount(0);
  await expect(page.getByText(/已确认操作：FILE_RECEIVED/)).toBeVisible();
  expect(uploads).toBe(1);
  await expect(page.getByRole('region',{name:'保留的原件历史'}).getByRole('row')).toHaveCount(2);
});
test('会话存储写入失败保留输入且零保存请求',async({page,baseURL})=>{
  await login(page,baseURL);
  await page.addInitScript(()=>{
    Storage.prototype.setItem=function(){throw new DOMException('test write failure','QuotaExceededError');};
  });
  let writes=0;
  page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/api/laboratory/imports'))writes++;});
  await page.goto('/lab/imports');
  await page.getByLabel('来源时区（可留空，IANA）',{exact:true}).fill('America/Chicago');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('尚未发送');
  await expect(page.getByLabel('来源时区（可留空，IANA）',{exact:true})).toHaveValue('America/Chicago');
  expect(writes).toBe(0);
});
test('来源 NEW 明确确认后分配稳定 ID，其他批次 REFERENCE 复用该 ID',async({page,baseURL})=>{
  await login(page,baseURL);
  await page.goto('/lab/imports');
  const name='Source lab browser '+Date.now();
  await page.getByLabel('文件内来源键',{exact:true}).fill('LAB_A');
  await page.getByLabel('身份决定',{exact:true}).selectOption('NEW');
  await page.getByLabel('来源实验室名称',{exact:true}).fill(name);
  await page.getByRole('button',{name:'查询来源候选',exact:true}).click();
  await page.getByRole('checkbox',{name:'已核对全部同名候选数量，确认这是新的独立来源身份'}).check();
  await page.getByLabel('来源身份确认原因',{exact:true}).fill('Explicit separate source identity');
  await page.getByRole('button',{name:'加入本次来源确认',exact:true}).click();
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  const region=page.getByRole('region',{name:'当前暂存批次'});
  await expect(region).toContainText(name);
  const first=await (await page.request.get(route+'/sources?exact_name='+encodeURIComponent(name))).json();
  expect(first.total).toBe(1);
  const sourceId=first.items[0].id;
  await page.getByRole('button',{name:'准备另一批次',exact:true}).click();
  await page.getByLabel('文件内来源键',{exact:true}).fill('LAB_B');
  await page.getByLabel('身份决定',{exact:true}).selectOption('REFERENCE');
  await page.getByLabel('来源实验室名称',{exact:true}).fill(name);
  await page.getByRole('button',{name:'查询来源候选',exact:true}).click();
  await page.getByRole('radio').first().check();
  await page.getByLabel('来源身份确认原因',{exact:true}).fill('Confirmed existing stable identity');
  await page.getByRole('button',{name:'加入本次来源确认',exact:true}).click();
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toContainText(sourceId);
});




test('核对元数据并明确改用历史原件，保留两个独立下载',async({page,baseURL})=>{
  await login(page,baseURL);
  await page.goto('/lab/imports');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toBeVisible();
  for(const name of ['first.xlsx','corrected.xlsx']){
    await page.getByLabel('选择工作簿原件').setInputFiles({name,mimeType:mime,buffer:Buffer.from('evidence '+name)});
    const receipt=page.waitForResponse(r=>r.url().includes('/files?')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'保存工作簿原件',exact:true}).click();
    expect((await receipt).status()).toBe(201);
    await expect(page.getByRole('region',{name:'未确认操作'})).toHaveCount(0);
  }
  const working=page.getByRole('region',{name:'当前采用的原件'});
  await expect(working).toContainText('first.xlsx');
  await expect(working).not.toContainText('corrected.xlsx');
  await page.getByText('核对用途、来源时区与身份',{exact:true}).click();
  await page.getByLabel('核对导入用途',{exact:true}).selectOption('DAILY');
  await page.getByLabel('核对来源时区（可留空，IANA）',{exact:true}).fill('America/Chicago');
  await page.getByRole('checkbox',{name:'已核实本次来源时区',exact:true}).check();
  await page.getByLabel('本次核对原因',{exact:true}).fill('Confirmed source metadata');
  const meta=page.waitForResponse(r=>r.url().endsWith('/revisions')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'保存元数据与来源核对',exact:true}).click();
  expect((await meta).status()).toBe(200);
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toContainText('日常检测资料');
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toContainText('America/Chicago');
  await page.getByLabel('本次核对原因',{exact:true}).fill('Use corrected retained original');
  const changed=page.waitForResponse(r=>r.url().endsWith('/revisions')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'改用此工作簿原件',exact:true}).click();
  expect((await changed).status()).toBe(200);
  await expect(working).toContainText('corrected.xlsx');
  await expect(working).not.toContainText('first.xlsx');
  await expect(page.getByRole('region',{name:'暂存修订历史'})).toContainText('Use corrected retained original');
  for(const name of ['first.xlsx','corrected.xlsx']){
    const downloadPromise=page.waitForEvent('download');
    await page.getByRole('link',{name:'下载原件：'+name,exact:true}).click();
    expect(await readFile((await (await downloadPromise).path())!)).toEqual(Buffer.from('evidence '+name));
  }
});


test('操作查询 404 保留原 key 与原始元数据，再原样重试',async({page,baseURL})=>{
  await login(page,baseURL);
  const writes:{key:string|null;body:string|null}[]=[];
  await page.route('**/api/laboratory/imports',async r=>{
    if(r.request().method()!=='POST'){await r.continue();return;}
    writes.push({key:r.request().headers()['idempotency-key']??null,body:r.request().postData()});
    if(writes.length===1)await r.abort('failed');else await r.continue();
  });
  await page.goto('/lab/imports');
  await page.getByLabel('导入用途',{exact:true}).selectOption('DAILY');
  await page.getByLabel('来源时区（可留空，IANA）',{exact:true}).fill('America/Chicago');
  await page.getByRole('checkbox',{name:'已核实此来源时区，不使用浏览器默认时区'}).check();
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('尚未确认');
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('不代表原请求失败');
  await expect(page.getByRole('button',{name:'创建暂存批次',exact:true})).toBeDisabled();
  await expect(page.getByLabel('导入用途',{exact:true})).toHaveValue('DAILY');
  await expect(page.getByLabel('来源时区（可留空，IANA）',{exact:true})).toHaveValue('America/Chicago');
  await page.getByRole('button',{name:'原样重试请求',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toContainText('日常检测资料');
  expect(writes).toHaveLength(2);
  expect(writes[1]).toEqual(writes[0]);
});


test('上传未到达时核对同一原件才重试，传输状态不宣称已确认',async({page,baseURL})=>{
  await login(page,baseURL);
  await page.goto('/lab/imports');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toBeVisible();
  const writes:{key:string|null;url:string;content:Buffer|null}[]=[];
  let release:()=>void=()=>{};
  const waiting=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/api/laboratory/imports/*/files?*',async r=>{
    if(r.request().method()!=='POST'){await r.continue();return;}
    writes.push({key:r.request().headers()['idempotency-key']??null,url:r.request().url(),content:r.request().postDataBuffer()});
    if(writes.length===1){await r.abort('failed');return;}
    const response=await r.fetch();expect(response.status()).toBe(201);
    await waiting;await r.fulfill({response});
  });
  const original={name:'retry-exact.xlsx',mimeType:mime,buffer:Buffer.from('the exact original')};
  await page.getByLabel('选择工作簿原件').setInputFiles(original);
  await page.getByRole('button',{name:'保存工作簿原件',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('尚未确认');
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('不代表原请求失败');
  await page.getByLabel('选择工作簿原件').setInputFiles({...original,buffer:Buffer.from('changed evidence')});
  await page.getByRole('button',{name:'原样重试请求',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('不一致，尚未发送');
  expect(writes).toHaveLength(1);
  await page.getByLabel('选择工作簿原件').setInputFiles(original);
  await page.getByRole('button',{name:'原样重试请求',exact:true}).click();
  // A paused intercepted request has not sent browser bytes; show honest 0% rather than inventing 100%.
  await expect(page.getByRole('status').filter({hasText:'此进度不代表已保存'})).toBeVisible();
  await expect(page.getByRole('region',{name:'当前采用的原件'})).not.toContainText(original.name);
  release();
  await expect(page.getByRole('status').filter({hasText:'原件已确认保存'})).toBeVisible();
  expect(writes).toHaveLength(2);
  expect(writes[1]).toEqual(writes[0]);
});
test('CSV 双表按角色分别保存，已确认清单包括两份独立原件',async({page,baseURL})=>{
  await login(page,baseURL);
  await page.goto('/lab/imports');
  await page.getByLabel('原件格式',{exact:true}).selectOption('CSV_PAIR');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toBeVisible();
  for(const [label,name] of [['油样信息 CSV','samples.csv'],['检测结果 CSV','tests.csv']]){
    await page.getByLabel('选择'+label+'原件').setInputFiles({name,mimeType:'text/csv',buffer:Buffer.from('source_lab_key,external_sample_id\r\nLAB_A,00017\r\n')});
    await page.getByRole('button',{name:'保存'+label+'原件',exact:true}).click();
    await expect(page.getByRole('region',{name:'当前采用的原件'})).toContainText(name);
  }
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toContainText('当前采用的原件已齐备');
  await expect(page.getByRole('region',{name:'保留的原件历史'}).getByRole('link',{name:/下载原件：/})).toHaveCount(2);
});




test('无效来源时区在创建前保留可编辑输入且零保存请求',async({page,baseURL})=>{
  await login(page,baseURL);
  let writes=0;
  page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname===route)writes++;});
  await page.goto('/lab/imports');
  const zone=page.getByLabel('来源时区（可留空，IANA）',{exact:true});
  await zone.fill('Not/A_Real_Zone');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('时区');
  expect(writes).toBe(0);
  await expect(zone).toBeEditable();
  await expect(zone).toHaveValue('Not/A_Real_Zone');
  await zone.fill('America/Chicago');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toContainText('America/Chicago');
  expect(writes).toBe(1);
});



test('文件摘要读取期间双击只占用一个上传意图，成功后释放提交保护',async({page,baseURL})=>{
  await page.addInitScript(()=>{
    const original=File.prototype.arrayBuffer;
    File.prototype.arrayBuffer=async function(){await new Promise(resolve=>setTimeout(resolve,500));return original.call(this);};
  });
  await login(page,baseURL);await page.goto('/lab/imports');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toBeVisible();
  const id=new URL(page.url()).searchParams.get('batch')!;
  const keys:string[]=[];
  page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/files?'))keys.push(r.headers()['idempotency-key']);});
  await page.getByLabel('选择工作簿原件').setInputFiles({name:'double-click.xlsx',mimeType:mime,buffer:Buffer.from('single owner evidence')});
  await page.getByRole('button',{name:'保存工作簿原件',exact:true}).dblclick({delay:20});
  await expect(page.getByRole('status').filter({hasText:'原件已确认保存'})).toBeVisible();
  await expect.poll(async()=> (await (await page.request.get(route+'/'+id+'/files')).json()).total).toBe(1);
  expect(keys).toHaveLength(1);
  expect((await (await page.request.get(route+'/'+id)).json()).revision).toBe(1);
  await page.getByLabel('选择工作簿原件').setInputFiles({name:'next-upload.xlsx',mimeType:mime,buffer:Buffer.from('next explicit operation')});
  await page.getByRole('button',{name:'保存工作簿原件',exact:true}).click();
  await expect.poll(async()=> (await (await page.request.get(route+'/'+id+'/files')).json()).total).toBe(2);
  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe(keys[1]);
});
test('服务端持久输入拒绝后显式纠正时区，使用新意图成功创建',async({page,baseURL})=>{
  await login(page,baseURL);await page.goto('/lab/imports');
  const keys:string[]=[];
  page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname===route)keys.push(r.headers()['idempotency-key']);});
  await page.getByLabel('来源时区（可留空，IANA）',{exact:true}).fill('america/chicago');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('拒绝');
  await expect(page.getByRole('button',{name:'加载最新批次并准备新的核对',exact:true})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button',{name:'加载最新批次并准备新的核对',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'加载最新批次并准备新的核对',exact:true}).click();
  await expect(page.getByLabel('来源时区（可留空，IANA）',{exact:true})).toBeEditable();
  await page.getByLabel('来源时区（可留空，IANA）',{exact:true}).fill('America/Chicago');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  await expect(page.getByRole('region',{name:'当前暂存批次'})).toContainText('America/Chicago');
  expect(keys).toHaveLength(2);expect(keys[0]).not.toBe(keys[1]);
});



test('无持久拒绝证明的 422、404 和 503 保留同一意图，不能显式清除',async({page,baseURL})=>{
  await login(page,baseURL);
  const writes:{key:string;body:string|null}[]=[];
  const operation={state:'REJECTED',action:'CREATE',batch_id:null,
    result:{code:'invalid_import_input',status:422,details:null},error_code:null};
  await page.route('**/api/laboratory/imports',async r=>{
    if(r.request().method()!=='POST'){await r.continue();return;}
    writes.push({key:r.request().headers()['idempotency-key'],body:r.request().postData()});
    const body=writes.length===1?{code:'invalid_import_input',operation}
      :writes.length===2?{code:'import_write_unknown',disposition:'DURABLE_REJECTED',operation}
      :{code:'invalid_import_input',disposition:'DURABLE_REJECTED',operation:{...operation,result:{...operation.result,details:'not the proof contract'}}};
    await r.fulfill({status:writes.length===2?503:422,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('/lab/imports');
  await page.getByRole('button',{name:'创建暂存批次',exact:true}).click();
  for(let attempt=1;attempt<=3;attempt++){
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByRole('button',{name:'加载最新批次并准备新的核对',exact:true})).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole('alert')).toContainText('不代表原请求失败');
    await expect(page.getByRole('button',{name:'创建暂存批次',exact:true})).toBeDisabled();
    await expect(page.getByRole('button',{name:'加载最新批次并准备新的核对',exact:true})).toHaveCount(0);
    if(attempt<3)await page.getByRole('button',{name:'原样重试请求',exact:true}).click();
  }
  expect(writes).toHaveLength(3);
  expect(writes[1]).toEqual(writes[0]);expect(writes[2]).toEqual(writes[0]);
});

