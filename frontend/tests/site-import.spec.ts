import { test, expect } from '@playwright/test';
import path from 'node:path';

// CI serves the production portal on ordinary http://frontend, where the
// secure-context-only APIs are absent. Model that browser boundary locally too.
test.beforeEach(async ({page})=>{
  await page.addInitScript(()=>{
    Object.defineProperty(crypto,'subtle',{value:undefined});
    Object.defineProperty(crypto,'randomUUID',{value:undefined});
  });
});

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
  await page.getByRole('button',{name:'保存核对并重新校验'}).click();
  await expect(page.getByRole('status').filter({hasText:'核对已保存'})).toBeVisible();
  for (const warning of await page.getByRole('checkbox',{name:/^确认警告：/}).all()) await warning.check();
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
