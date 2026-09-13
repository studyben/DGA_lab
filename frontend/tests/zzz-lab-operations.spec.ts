import { test, expect } from '@playwright/test';

test('实验室首页四项指标、筛选台账并按条码继续检测', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', { headers: { Origin: new URL(baseURL!).origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  await page.goto('/lab');
  await expect(page.getByRole('region', { name: '实验室指标' })).toBeVisible();
  await expect(page.getByRole('region', { name: '实验室指标' }).getByRole('article')).toHaveCount(4);
  await page.getByRole('link', { name: '查看油样台账', exact: true }).click();
  await page.getByLabel('条码筛选', { exact: true }).fill('DGA-20260802-000001');
  await page.getByRole('button', { name: '应用筛选', exact: true }).click();
  await expect(page.getByRole('table', { name: '油样台账' }).locator('tbody tr')).toHaveCount(1);
  await page.reload();
  await expect(page.getByLabel('条码筛选', { exact: true })).toHaveValue('DGA-20260802-000001');
  await page.getByRole('table', { name: '油样台账' }).getByRole('link', { name: 'DGA-20260802-000001', exact: true }).click();
  await expect(page.getByLabel('扫描或输入油样条码')).toHaveValue('DGA-20260802-000001');
});

test('待确认油样关联整机下变压器，条码继续检测并记录容器状态', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const login = await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  const session = await login.json();
  const sampleResponse = await page.request.post('/api/laboratory/samples', { headers: { Origin: origin, 'X-CSRF-Token': session.csrf_token }, data: {
    sampled_at: '2025-06-01T12:00:00Z', received_at: '2025-06-02T12:00:00Z', site_name: 'raw site', equipment_serial: 'raw serial', container_count: 1, identity_status: 'IDENTITY_PENDING',
  } });
  expect(sampleResponse.status()).toBe(201);
  const sample = await sampleResponse.json();
  await page.goto('/lab/identity?barcode='+encodeURIComponent(sample.barcode_value));
  await page.getByRole('button', { name: '核实 '+sample.barcode_value, exact: true }).click();
  await expect(page.getByRole('region', { name: '油样运营信息' })).toContainText('raw serial');
  await page.getByLabel('整机或变压器序列号').fill('INV-UNIT-7788');
  await page.getByRole('button', { name: '搜索正式资产' }).click();
  await page.getByRole('group', { name: 'INV-UNIT-7788' }).getByRole('button', { name: '选择变压器 TX-CURRENT-2002' }).click();
  await page.getByLabel('身份确认原因').fill('核对铭牌和采样记录');
  await page.getByRole('button', { name: '确认关联正式资产', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '身份关联已保存' })).toBeVisible();
  await page.getByRole('link', { name: '按此条码继续检测', exact: true }).click();
  await page.getByRole('button', { name: '加载油样', exact: true }).click();
  const container = page.getByRole('group', { name: sample.containers[0].container_number, exact: true });
  await container.getByLabel('目标状态').selectOption('IN_USE');
  await container.getByLabel('容器变更原因').fill('开始检测使用');
  await container.getByRole('button', { name: '保存容器状态', exact: true }).click();
  await expect(container).toContainText('当前状态：使用中');
  await expect(page.getByRole('region', { name: '油样运营信息' })).toContainText('开始检测使用');
  await page.reload();
  await page.getByRole('button', { name: '加载油样', exact: true }).click();
  await expect(page.getByRole('group', { name: sample.containers[0].container_number, exact: true })).toContainText('当前状态：使用中');
});

test('只读用户可看指标台账但不能确认身份或变更容器', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const login = await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'operations-reader', password: 'Browser changed passphrase 84!' } });
  expect(login.ok()).toBeTruthy();
  const session = await login.json();
  await page.goto('/lab');
  await expect(page.getByRole('region', { name: '实验室指标' })).toBeVisible();
  await expect(page.getByRole('link', { name: '新建油样', exact: true })).toHaveCount(0);
  await page.goto('/lab/samples');
  await expect(page.getByRole('table', { name: '油样台账' })).toBeVisible();
  await expect(page.getByRole('table', { name: '油样台账' }).getByRole('link')).toHaveCount(0);
  await page.getByRole('button', { name: '查看运营信息 DGA-20260802-000001', exact: true }).click();
  await expect(page.getByRole('region', { name: '油样运营信息' })).toBeVisible();
  await page.getByText('操作历史（0 条）', { exact: true }).click();
  await expect(page.getByText('尚无油样操作记录。', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '保存容器状态', exact: true })).toHaveCount(0);
  const path = '/api/laboratory/operations/DGA-20260802-000001';
  const state = await (await page.request.get(path)).json();
  const write = await page.request.post(path+'/containers/'+state.containers[0].id, { headers: { Origin: origin, 'X-CSRF-Token': session.csrf_token }, data: { target: 'IN_USE', expected_revision: 0, reason: 'not authorized' } });
  expect(write.status()).toBe(403);
  await page.goto('/lab/identity');
  await expect(page.getByRole('heading', { name: '无权访问此页面' })).toBeVisible();
});

test('并发基础信息变更后身份确认保留输入并要求重新读取', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const session = await (await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } })).json();
  const headers = { Origin: origin, 'X-CSRF-Token': session.csrf_token };
  const basics = { sampled_at: '2025-06-01T12:00:00Z', received_at: '2025-06-02T12:00:00Z', site_name: 'pending concurrent', equipment_serial: 'raw serial', notes: '' };
  const sample = await (await page.request.post('/api/laboratory/samples', { headers, data: { ...basics, container_count: 1, identity_status: 'IDENTITY_PENDING' } })).json();
  await page.goto('/lab/identity?barcode='+encodeURIComponent(sample.barcode_value));
  await page.getByRole('button', { name: '核实 '+sample.barcode_value, exact: true }).click();
  await page.getByLabel('整机或变压器序列号').fill('INV-UNIT-7788');
  await page.getByRole('button', { name: '搜索正式资产' }).click();
  await page.getByRole('group', { name: 'INV-UNIT-7788' }).getByRole('button', { name: '选择变压器 TX-CURRENT-2002' }).click();
  await page.getByLabel('身份确认原因').fill('保留此输入');
  const update = await page.request.patch('/api/laboratory/samples/'+sample.barcode_value, { headers, data: { ...basics, site_name: 'changed by colleague' } });
  expect(update.ok()).toBeTruthy();
  await page.getByRole('button', { name: '确认关联正式资产', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('油样基础信息已被更新');
  await expect(page.getByLabel('身份确认原因')).toHaveValue('保留此输入');
  await expect(page.getByRole('button', { name: '确认关联正式资产', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '重新读取状态', exact: true }).click();
  await expect(page.getByRole('region', { name: '油样运营信息' })).toContainText('changed by colleague');
  await expect(page.getByRole('button', { name: '确认关联正式资产', exact: true })).toBeDisabled();
});

test('重新读取油样时忽略旧选择器迟到的资产选择', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const session = await (await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } })).json();
  const headers = { Origin: origin, 'X-CSRF-Token': session.csrf_token };
  const basics = { sampled_at: '2025-06-01T12:00:00Z', received_at: '2025-06-02T12:00:00Z', site_name: 'old selection site', equipment_serial: 'raw serial', notes: '' };
  const sample = await (await page.request.post('/api/laboratory/samples', { headers, data: { ...basics, container_count: 1, identity_status: 'IDENTITY_PENDING' } })).json();
  let release!: () => void;
  let fetched!: () => void;
  const held = new Promise<void>(resolve => { release=resolve; });
  const requested = new Promise<void>(resolve => { fetched=resolve; });
  await page.route('**/api/assets/*/sampling-context?*', async route => { const response=await route.fetch(); fetched(); await held; await route.fulfill({ response }); });
  await page.goto('/lab/identity?barcode='+encodeURIComponent(sample.barcode_value));
  await page.getByRole('button', { name: '核实 '+sample.barcode_value, exact: true }).click();
  await page.getByLabel('整机或变压器序列号').fill('INV-UNIT-7788');
  await page.getByRole('button', { name: '搜索正式资产' }).click();
  await page.getByRole('group', { name: 'INV-UNIT-7788' }).getByRole('button', { name: '选择变压器 TX-CURRENT-2002' }).click();
  await requested;
  expect((await page.request.patch('/api/laboratory/samples/'+sample.barcode_value, { headers, data: { ...basics, sampled_at: '2026-06-01T12:00:00Z', received_at: '2026-06-02T12:00:00Z', site_name: 'new selection site' } })).ok()).toBeTruthy();
  await page.getByRole('button', { name: '重新读取状态', exact: true }).click();
  await expect(page.getByRole('region', { name: '油样运营信息' })).toContainText('new selection site');
  await page.getByLabel('身份确认原因').fill('必须重新选择');
  const delivered = page.waitForResponse(response => response.url().includes('/sampling-context?'));
  release(); await (await delivered).finished();
  await page.waitForTimeout(300); // Allow the deliberately late JSON/callback to reach React.
  await expect(page.getByRole('button', { name: '确认关联正式资产', exact: true })).toBeDisabled();
  await expect(page.getByText(/^待关联：/)).toHaveCount(0);
});

test('容器提交响应丢失时先读取结果而不是重复提交', async ({ page, baseURL }) => {
  const origin=new URL(baseURL!).origin;
  const session=await (await page.request.post('/api/auth/login',{ headers:{Origin:origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'} })).json();
  const headers={Origin:origin,'X-CSRF-Token':session.csrf_token};
  const sample=await (await page.request.post('/api/laboratory/samples',{headers,data:{sampled_at:'2025-06-01T12:00:00Z',received_at:'2025-06-02T12:00:00Z',site_name:'recovery',equipment_serial:'recovery',container_count:1,identity_status:'IDENTITY_PENDING'}})).json();
  let submissions=0;
  await page.route('**/api/laboratory/operations/*/containers/*',async route=>{ submissions++; const response=await route.fetch(); expect(response.status()).toBe(200); await route.abort(); });
  await page.goto('/lab/workbench?barcode='+encodeURIComponent(sample.barcode_value));
  await page.getByRole('button',{name:'加载油样',exact:true}).click();
  const container=page.getByRole('group',{name:sample.containers[0].container_number,exact:true});
  await container.getByLabel('目标状态').selectOption('IN_USE');
  await container.getByLabel('容器变更原因').fill('一次提交');
  await container.getByRole('button',{name:'保存容器状态',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('未能确认提交结果');
  await expect(container.getByLabel('容器变更原因')).toHaveValue('一次提交');
  await expect(container.getByRole('button',{name:'保存容器状态',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'重新读取状态',exact:true}).click();
  await expect(container).toContainText('当前状态：使用中');
  expect(submissions).toBe(1);
  const current=await (await page.request.get('/api/laboratory/operations/'+sample.barcode_value)).json();
  expect(current.history).toHaveLength(1);
});
