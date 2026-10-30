import { test, expect, type Page } from '@playwright/test';
import path from 'node:path';

// CI serves the production portal on ordinary http://frontend, where the
// secure-context-only APIs are absent. Model that browser boundary locally too.
test.beforeEach(async ({page})=>{
  await page.addInitScript(()=>{
    Object.defineProperty(crypto,'subtle',{value:undefined});
    Object.defineProperty(crypto,'randomUUID',{value:undefined});
  });
});

// Deliver the real post-review GET only after the user confirms warnings.
// This exercises the same-version response race without inventing server data.
async function deferValidatedRead(page:Page) {
  let release!:()=>void, arrived!:(value:any)=>void,held=false,url='';
  const gate=new Promise<void>(resolve=>release=resolve);
  const preview=new Promise<any>(resolve=>arrived=resolve);
  await page.route('**/api/assets/imports/*?page=*',async route=>{
    const response=await route.fetch();
    const value=await response.json();
    if(!held&&value.state==='VALIDATED'){
      held=true;url=route.request().url();arrived(value);await gate;
    }
    await route.fulfill({response});
  });
  return {preview,async deliver(){
    const delivered=page.waitForResponse(response=>response.request().method()==='GET'&&response.url()===url);
    release();await(await delivered).finished();
    // Observe a browser paint after the delivered response, including UI updates.
    await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  }};
}

test('仅现场导入：核对同名差异、来源备注、发布后零设备现场与原文件历史', async ({ page, baseURL }) => {
  const origin=new URL(baseURL!).origin;
  const login=await (await page.request.post('/api/auth/login', {headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}})).json();
  // Arrange the named candidate through its public command: another browser
  // test legitimately edits this shared fixture, so never assume its old name.
  const candidateId='20000000-0000-0000-0000-000000000001';
  const current=(await (await page.request.get(`/api/assets/sites/${candidateId}?product_line=PV`)).json()).site;
  const arranged=await page.request.put(`/api/assets/sites/${candidateId}/basics`,{headers:{Origin:origin,'X-CSRF-Token':login.csrf_token},data:{expected_revision:current.revision,site_name:'Prairie Sun',location_text:current.location_text,commissioning_date:current.commissioning_date,grid_status:current.grid_status,operation_status:current.operation_status,product_line:'PV',power_mw:current.power_mw,energy_mwh:null}});
  expect(arranged.status()).toBe(200);
  await page.goto('/assets/import?mode=SITES');
  await expect(page.getByRole('link',{name:'下载 v2 现场模板'})).toBeVisible();
  await page.getByLabel('选择现场 Excel 文件').setInputFiles(path.join(process.cwd(),'tests/fixtures/site-import.xlsx'));
  await page.getByRole('button',{name:'上传现场文件并校验'}).click();
  await expect(page.getByRole('table',{name:'现场导入问题'})).toContainText('同名',{timeout:15000});
  await expect(page.getByRole('button',{name:'发布客户与现场'})).toBeDisabled();
  await page.getByRole('button',{name:'核对 Sites 第2行'}).click();
  await expect(page.getByRole('region',{name:'候选资料与差异'})).toContainText('Prairie Sun');
  await page.getByLabel('来源备注', {exact:true}).fill('服务商报告提供现场位置，发货记录提供容量（验收假数据）');
  await page.getByLabel('本次核对原因', {exact:true}).fill('确认是同名的另一独立现场');
  const reread=await deferValidatedRead(page);
  const revised=page.waitForResponse(response=>response.request().method()==='POST'&&response.url().endsWith('/revisions'));
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  const saved=await(await revised).json();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  const warnings=page.getByRole('checkbox',{name:/^确认警告：/});
  await expect(warnings).toHaveCount(saved.summary.warning_count);
  for (const warning of await warnings.all()) await warning.check();
  const same=await reread.preview;
  expect(same.validation_revision).toBe(saved.validation_revision);
  expect(same.summary).toEqual(saved.summary);
  expect(same.issues).toEqual(saved.issues);
  expect(same.rows).toEqual(saved.rows);
  await reread.deliver();
  for (const warning of await warnings.all()) await expect(warning).toBeChecked({timeout:1500});
  await expect(page.getByRole('button',{name:'发布客户与现场'})).toBeEnabled({timeout:1500});
  await page.getByRole('button',{name:'发布客户与现场'}).click();
  await expect(page.getByRole('status').filter({hasText:'客户与现场已整批发布'})).toBeVisible();
  await page.getByRole('link',{name:'查看现场'}).click();
  await expect(page.getByRole('region',{name:'现场资料'})).toContainText('12.000001');
  await expect(page.getByText('暂无设备。',{exact:true})).toBeVisible();
  await expect(page.getByRole('region',{name:'现场导入来源'})).toContainText('服务商报告提供现场位置');
  await page.getByRole('region',{name:'现场导入来源'}).getByRole('link',{name:'查看导入批次'}).click();
  await expect(page.getByRole('link',{name:'下载原始上传文件'})).toBeVisible();
  await expect(page.getByRole('table',{name:'核对修订历史'})).toContainText('确认是同名的另一独立现场');
  await page.screenshot({path:'test-results/site-import-published.png',fullPage:true});
});

test('上传响应丢失后重新进入并查询原操作，不重复建批次',async({page,baseURL})=>{
  await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  const filename='site-import-unknown-response.xlsx';
  const before=await (await page.request.get('/api/assets/imports?query='+filename)).json();
  let posts=0;
  await page.route('**/api/assets/imports?*',async route=>{
    if(route.request().method()==='POST'&&route.request().url().includes(filename)){
      posts++;const response=await route.fetch();expect(response.status()).toBe(201);await route.abort('failed');
    }else await route.continue();
  });
  await page.goto('/assets/import?mode=SITES');
  await page.getByLabel('选择现场 Excel 文件').setInputFiles({name:filename,mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:await (await import('node:fs/promises')).readFile(path.join(process.cwd(),'tests/fixtures/site-import.xlsx'))});
  await page.getByRole('button',{name:'上传现场文件并校验'}).click();
  await expect(page.getByRole('alert')).toContainText('结果尚未确认');
  await page.reload();
  await page.getByRole('button',{name:'查询未确认操作'}).click();
  await expect(page.getByRole('region',{name:'现场导入预览'})).toContainText(filename);
  const after=await (await page.request.get('/api/assets/imports?query='+filename)).json();
  expect(after.total).toBe(before.total+1);expect(posts).toBe(1);
});


test('真实新修订及新增警告仍清除确认，必须重新逐项核对',async({page,baseURL})=>{
  const origin=new URL(baseURL!).origin;
  expect((await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}})).ok()).toBeTruthy();
  await page.goto('/assets/import?mode=SITES');
  await page.getByLabel('选择现场 Excel 文件').setInputFiles(path.join(process.cwd(),'tests/fixtures/site-import.xlsx'));
  await page.getByRole('button',{name:'上传现场文件并校验'}).click();
  const warnings=page.getByRole('checkbox',{name:/^确认警告：/});
  await expect(warnings.first()).toBeVisible();
  const id=new URL(page.url()).searchParams.get('batch')!;
  const initial=await(await page.request.get(`/api/assets/imports/${id}`)).json();
  const initialWarnings=initial.issues.filter((issue:{severity:string})=>issue.severity==='WARNING').map((issue:{id:string})=>issue.id);
  expect(initial.issues.some((issue:{code:string})=>issue.code==='reference_difference')).toBeFalsy();
  for(const warning of await warnings.all())await warning.check();
  await expect(page.getByRole('button',{name:'发布客户与现场'})).toBeEnabled();
  await page.getByRole('button',{name:'核对 Sites 第2行'}).click();
  await page.getByRole('region',{name:'候选资料与差异'}).getByRole('button',{name:'引用这个候选'}).first().click();
  await page.getByLabel('现场名称',{exact:true}).fill('A supplied name different from the referenced site');
  await page.getByLabel('本次核对原因',{exact:true}).fill('Explicitly reference candidate while retaining source-name difference');
  const revised=page.waitForResponse(response=>response.request().method()==='POST'&&response.url().endsWith('/revisions'));
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  const result=await(await revised).json();
  expect(result.validation_revision).toBe(2);
  expect(result.issues.some((issue:{code:string})=>issue.code==='reference_difference')).toBeTruthy();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  await expect(warnings).toHaveCount(result.summary.warning_count);
  expect(result.issues.some((issue:{id:string;severity:string})=>issue.severity==='WARNING'&&!initialWarnings.includes(issue.id))).toBeTruthy();
  await expect(page.getByRole('checkbox',{name:/^确认警告：以下提供值与正式资料不同/})).not.toBeChecked();
  for(const warning of await warnings.all())await expect(warning).not.toBeChecked();
  await expect(page.getByRole('button',{name:'发布客户与现场'})).toBeDisabled();
});
