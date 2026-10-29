import { test, expect } from '@playwright/test';

test('管理员在用户页面修改角色，现有会话立即获得权限', async ({ page, browser, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const admin = await page.request.post('/api/auth/login', { headers: { Origin: origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  const csrf = (await admin.json()).csrf_token;
  const users = await (await page.request.get('/api/auth/users?query=field-user')).json();
  const user = users.items[0];
  if (user.roles.includes('analyst')) await page.request.put('/api/auth/users/' + user.id + '/roles', {
    headers: { Origin: origin, 'X-CSRF-Token': csrf }, data: { add: [], remove: ['analyst'], expected_revision: user.revision },
  });
  const employee = await browser.newContext();
  try {
    await employee.request.post(baseURL + '/api/auth/login', { headers: { Origin: origin },
      data: { username: 'field-user', password: 'Browser changed passphrase 84!' } });
    await page.goto('/settings/users');
    await expect(page.getByRole('heading', { name: '用户与角色', exact: true })).toBeVisible();
    await page.getByLabel('用户关键词').fill('field-user');
    await page.getByRole('button', { name: '筛选用户', exact: true }).click();
    await page.getByRole('button', { name: '查看 field-user' }).click();
    await page.getByLabel('分析员', { exact: true }).check();
    await page.getByRole('button', { name: '保存角色变更' }).click();
    await expect(page.getByRole('status').filter({ hasText: '角色已更新。' })).toBeVisible();
    const current = await employee.request.get(baseURL + '/api/auth/session');
    expect((await current.json()).permissions).toContain('laboratory.write');
    await page.getByLabel('分析员', { exact: true }).uncheck();
    await page.getByRole('button', { name: '保存角色变更' }).click();
    await expect(page.getByRole('status').filter({ hasText: '角色已更新。' })).toBeVisible();
    expect((await (await employee.request.get(baseURL + '/api/auth/session')).json()).permissions).not.toContain('laboratory.write');
  } finally { await employee.close(); }
});

test('管理层不能修改受保护账号，实验室经理不能恢复停用账号', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const admin = await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  const csrf = (await admin.json()).csrf_token;
  const users = await (await page.request.get('/api/auth/users?query=field-user')).json();
  const user = users.items[0];
  await page.request.put('/api/auth/users/' + user.id + '/status', { headers: { Origin: origin, 'X-CSRF-Token': csrf }, data: { status: 'DISABLED', expected_revision: user.revision } });
  await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'identity-lab-manager', password: 'Browser changed passphrase 84!' } });
  await page.goto('/settings/users');
  await page.getByLabel('用户关键词').fill('field-user');
  await page.getByRole('button', { name: '筛选用户', exact: true }).click();
  await page.getByRole('button', { name: '查看 field-user' }).click();
  await expect(page.getByRole('button', { name: '恢复账号' })).toHaveCount(0);
  await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'identity-management', password: 'Browser changed passphrase 84!' } });
  await page.reload();
  await page.getByLabel('用户关键词').fill('browser-admin');
  await page.getByRole('button', { name: '筛选用户', exact: true }).click();
  await page.getByRole('button', { name: '查看 browser-admin' }).click();
  await expect(page.getByRole('button', { name: '保存角色变更' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '停用账号' })).toHaveCount(0);
  // Restore the isolated employee fixture through the authorized application endpoint.
  const login = await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  const current = await (await page.request.get('/api/auth/users/' + user.id)).json();
  await page.request.put('/api/auth/users/' + user.id + '/status', { headers: { Origin: origin, 'X-CSRF-Token': (await login.json()).csrf_token }, data: { status: 'ACTIVE', expected_revision: current.revision } });
});

test('单角色可一次替换，提交后的刷新故障不会掩盖已保存状态', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  await page.goto('/settings/users');
  await page.getByLabel('用户关键词').fill('field-user');
  await page.getByRole('button', { name: '筛选用户', exact: true }).click();
  await page.getByRole('button', { name: '查看 field-user' }).click();
  await page.getByLabel('Asset Manager', { exact: true }).check();
  await page.getByLabel('现场工程师', { exact: true }).uncheck();
  await page.route(/\/api\/auth\/users\/[0-9a-f-]+$/, route => route.fulfill({ status: 503, json: { code: 'unavailable' } }), { times: 1 });
  await page.getByRole('button', { name: '保存角色变更' }).click();
  await expect(page.getByRole('status').filter({ hasText: '角色已更新。' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('变更已保存');
  await page.getByRole('button', { name: '重新加载详情' }).click();
  await expect(page.getByLabel('现场工程师', { exact: true })).not.toBeChecked();
  await expect(page.getByLabel('Asset Manager', { exact: true })).toBeChecked();
  await page.getByLabel('现场工程师', { exact: true }).check();
  await page.getByLabel('Asset Manager', { exact: true }).uncheck();
  await page.getByRole('button', { name: '保存角色变更' }).click();
  await expect(page.getByRole('status').filter({ hasText: '角色已更新。' })).toBeVisible();
});
