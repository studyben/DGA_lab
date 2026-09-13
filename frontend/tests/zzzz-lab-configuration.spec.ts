import { test, expect } from '@playwright/test';

test('管理员可发布方法版本并在工作台使用配置', async ({ page, baseURL }) => {
  test.setTimeout(90000);
  const login = await page.request.post('/api/auth/login', { headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  expect(login.ok()).toBeTruthy();
  const session = await login.json();
  const headers = { Origin: new URL(baseURL!).origin, 'X-CSRF-Token': session.csrf_token };
  const suffix = String(Date.now());
  await page.goto('/lab/configuration');
  await expect(page.getByRole('heading', { name: '实验室配置', exact: true })).toBeVisible();
  await page.getByLabel('检测类型', { exact: true }).selectOption('MOISTURE');
  await page.getByLabel('方法名称', { exact: true }).fill('浏览器验收微水方法');
  await page.getByLabel('方法版本标识').fill(`BROWSER-${suffix}`);
  await page.getByLabel('MOISTURE 单位').fill('TEST-UNIT');
  await page.getByLabel('MOISTURE 小数位数').fill('1');
  await page.getByLabel('MOISTURE 录入下限').fill('0.05');
  for (const name of ['EQ','ND','GT']) await page.getByRole('checkbox', {name,exact:true}).uncheck();
  await page.getByRole('button', {name:'添加 QA/QC 检查项'}).click();
  await page.getByLabel('检查代码').fill('BLANK');
  await page.getByLabel('检查名称').fill('空白检查');
  await page.getByRole('button', { name: '发布新方法版本' }).click();
  await expect(page.getByRole('status').filter({ hasText: '配置已保存' })).toBeVisible();
  await expect(page.getByRole('table', { name: '方法版本列表' })).toContainText('浏览器验收微水方法');
  const catalog = await (await page.request.get('/api/laboratory/configuration')).json();
  const method = catalog.methods.find((m:{version_label:string})=>m.version_label===`BROWSER-${suffix}`);
  await page.getByRole('button',{name:'仪器与校准',exact:true}).click();
  await page.getByLabel('仪器编号').fill('I-'+suffix);
  await page.getByLabel('仪器名称').fill('验收仪器');
  await page.getByRole('button',{name:'新增仪器',exact:true}).click();
  await expect(page.getByRole('table',{name:'仪器台账'})).toContainText('I-'+suffix);
  await page.getByLabel(/^校准仪器/).selectOption({label:'I-'+suffix+' · 验收仪器'});
  await page.getByLabel('校准日期',{exact:true}).fill('2025-01-01');
  await page.getByLabel('有效截止日',{exact:true}).fill('2025-06-01');
  await page.getByRole('button',{name:'保存校准记录'}).click();
  await expect(page.getByRole('table',{name:'校准记录'})).toContainText('2025-06-01');
  const packageResponse = await page.request.post('/api/laboratory/configuration/packages',{headers,data:{code:'P-'+suffix,name:'验收检测包',items:[{test_type:'MOISTURE',method_version_id:method.id,required:true}]}});
  expect(packageResponse.status()).toBe(201);
  const pkg = await packageResponse.json();
  const received = await page.request.post('/api/laboratory/samples',{headers,data:{sampled_at:'2025-06-01T12:00:00Z',received_at:'2025-06-02T12:00:00Z',site_name:'fixture',equipment_serial:'fixture',container_count:1,identity_status:'ASSOCIATED',formal_asset_id:'40000000-0000-0000-0000-000000000002'}});
  expect(received.status()).toBe(201);
  const sample = await received.json();
  await page.goto('/lab/workbench?barcode='+sample.barcode_value);
  await page.getByRole('button',{name:'加载油样',exact:true}).click();
  await page.getByLabel('应用检测包',{exact:true}).selectOption(pkg.id);
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'应用到此油样'}).click();
  await expect(page.getByText('检测包必做项目尚未完成：微水')).toBeVisible();
  await page.getByRole('button',{name:'新增微水',exact:true}).click();
  await page.getByLabel(/^关联仪器/).selectOption({label:'I-'+suffix+' · 验收仪器'});
  await page.getByLabel('检测时间',{exact:true}).fill('2026-08-03T12:00');
  await page.getByLabel('MOISTURE结果',{exact:true}).fill('0.1');
  await expect(page.getByLabel('MOISTURE限定符')).toHaveValue('LT');
  await page.getByLabel('空白检查 检查结果').selectOption('FAIL');
  await page.getByRole('button',{name:'保存微水检测'}).click();
  await expect(page.getByRole('article',{name:'微水 检测 #1'})).toContainText('检测时校准：已过期');
  await expect(page.getByRole('article',{name:'微水 检测 #1'})).toContainText('空白检查：失败');
  page.once('dialog',d=>d.dismiss());
  await page.getByRole('button',{name:'整体检测定稿',exact:true}).click();
  await expect(page.getByRole('button',{name:'新增微水',exact:true})).toBeVisible();
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'整体检测定稿',exact:true}).click();
  await expect(page.getByText('检测已整体定稿，基础信息、检测记录和报告结果为只读。')).toBeVisible();
  await page.goto('/lab/reports');
  await page.getByLabel('油样条码').fill(sample.barcode_value);
  await page.getByRole('button',{name:'查询报告'}).click();
  await expect(page.getByText('报告已生成，可在线预览或下载。')).toBeVisible({timeout:30000});
  const file = await page.request.get(await page.getByRole('link',{name:'下载 PDF'}).getAttribute('href') ?? '');
  expect(file.status()).toBe(200);
  expect((await file.body()).subarray(0,4).toString()).toBe('%PDF');
});

test('只读用户能查看配置但不能维护', async ({page,baseURL})=>{
  const origin = new URL(baseURL!).origin;
  const login=await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'operations-reader',password:'Browser changed passphrase 84!'}});
  const session=await login.json();
  await page.goto('/lab/configuration');
  await expect(page.getByRole('button',{name:'发布新方法版本'})).toBeDisabled();
  const response=await page.request.post('/api/laboratory/configuration/instruments',{headers:{Origin:origin,'X-CSRF-Token':session.csrf_token},data:{code:'FORBIDDEN',name:'Forbidden'}});
  expect(response.status()).toBe(403);
});

test('配置提交返回非 JSON 网关错误时先核对结果而非重复提交',async({page,baseURL})=>{
  await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  await page.goto('/lab/configuration');
  await page.getByRole('button',{name:'仪器与校准',exact:true}).click();
  await page.getByLabel('仪器编号').fill('UNCERTAIN');
  await page.getByLabel('仪器名称').fill('超时测试');
  await page.route('**/api/laboratory/configuration/instruments',route=>route.fulfill({status:502,contentType:'text/html',body:'Gateway error'}));
  await page.getByRole('button',{name:'新增仪器',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'保存结果尚未确认'})).toBeVisible();
  await expect(page.getByRole('button',{name:'新增仪器',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'重新读取配置'}).click();
  await expect(page.getByRole('button',{name:'新增仪器',exact:true})).toBeEnabled();
});

test('重新读取检测类型配置后显示最新名称和启用状态',async({page,baseURL})=>{
  const origin=new URL(baseURL!).origin;
  const login=await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  const headers={Origin:origin,'X-CSRF-Token':(await login.json()).csrf_token};
  const catalog=await (await page.request.get('/api/laboratory/configuration')).json();
  const original=catalog.types.find((t:{code:string})=>t.code==='MOISTURE');
  await page.goto('/lab/configuration');
  await page.getByRole('button',{name:'检测类型',exact:true}).click();
  await page.getByLabel('筛选当前列表').fill('MOISTURE');
  await expect(page.getByLabel('显示名称',{exact:true})).toHaveValue(original.display_name);
  try {
    expect((await page.request.put('/api/laboratory/configuration/types/MOISTURE',{headers,data:{display_name:'更新的微水名称',is_active:false}})).status()).toBe(204);
    await page.getByRole('button',{name:'重新读取配置'}).click();
    await expect(page.getByLabel('显示名称',{exact:true})).toHaveValue('更新的微水名称');
    await expect(page.getByRole('checkbox',{name:'启用类型'})).not.toBeChecked();
  } finally {
    await page.request.put('/api/laboratory/configuration/types/MOISTURE',{headers,data:{display_name:original.display_name,is_active:original.is_active}});
  }
});
