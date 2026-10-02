import { test, expect } from '@playwright/test';

test('本地恢复入口独立可用，只有管理员可见 OIDC 配置', async ({ page, baseURL }) => {
  await page.goto('/login/local');
  await expect(page.getByRole('heading', { name: '本地恢复登录' })).toBeVisible();
  await page.getByLabel('用户名', { exact: true }).fill('browser-admin');
  await page.getByLabel('密码', { exact: true }).fill('Browser changed passphrase 84!');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page).toHaveURL(/\/assets$/);
  await page.goto('/settings/sso');
  await expect(page.getByRole('heading', { name: 'Okta OIDC 配置', exact: true })).toBeVisible();
  await expect(page.getByText('真实 Okta 验收需由 IT 配合完成，模拟测试不代表已验收。')).toBeVisible();
  const origin = new URL(baseURL!).origin;
  await page.request.post('/api/auth/login', { headers: { Origin: origin },
    data: { username: 'field-user', password: 'Browser changed passphrase 84!' } });
  await page.reload();
  await expect(page.getByRole('heading', { name: '无权访问此页面' })).toBeVisible();
});

test('隔离协议夹具：候选测试失败保留原配置，成功后启用并以最低权限登录', async ({ page, baseURL }) => {
  test.skip(process.env.OIDC_PROTOCOL_FIXTURE !== '1', 'Requires explicit isolated protocol overlay, not real Okta');
  let reject = false;
  // Docker uses an internal HTTP hostname; model the registered loopback origin
  // at the transport seam. This fixture is NOT real-origin/Okta acceptance.
  await page.route('**/api/auth/oidc/**', async route => {
    const request = route.request();
    if (request.method() === 'POST' && /\/(start|test)$/.test(new URL(request.url()).pathname)) {
      const response = await route.fetch({ headers: { ...request.headers(), origin: 'http://127.0.0.1:18118' } });
      await route.fulfill({ response });
    } else await route.continue();
  });
  await page.route('https://tenant.example/authorize?*', async route => {
    const url = new URL(route.request().url());
    const callback = new URL('/api/auth/oidc/callback', baseURL!);
    callback.searchParams.set('state', url.searchParams.get('state')!);
    callback.searchParams.set('code', reject ? 'rejected' : url.searchParams.get('nonce')!);
    await route.fulfill({ status: 302, headers: { location: callback.href }, body: '' });
  });
  await page.goto('/login/local');
  await page.getByLabel('用户名', { exact: true }).fill('browser-admin');
  await page.getByLabel('密码', { exact: true }).fill('Browser changed passphrase 84!');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page).toHaveURL(/\/assets$/);
  await page.goto('/settings/sso');
  await page.getByLabel('Issuer 地址').fill('https://tenant.example');
  await page.getByLabel('Client ID', { exact: true }).fill('browser-client');
  await page.getByLabel('Client Secret', { exact: true }).fill('isolated-browser-secret');
  await page.getByRole('button', { name: '保存候选配置', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '候选配置已保存' })).toBeVisible();
  await expect(page.getByLabel('Client Secret', { exact: true })).toHaveValue('');
  const first = page.getByRole('row').filter({ hasText: 'https://tenant.example' }).first();
  await expect(first.getByRole('button', { name: '明确启用' })).toBeDisabled();
  const [startResponse] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/test') && r.request().method() === 'POST'),
    first.getByRole('button', { name: '测试登录' }).click(),
  ]);
  expect(startResponse.status(), startResponse.ok() ? '' : await startResponse.text()).toBe(200);
  await expect(page).toHaveURL(/\/settings\/sso\?oidc=tested$/);
  await expect(page.getByRole('status').filter({ hasText: '尚未启用' })).toBeVisible();
  page.once('dialog', d => d.accept());
  await page.getByRole('row').filter({ hasText: 'https://tenant.example' }).first().getByRole('button', { name: '明确启用' }).click();
  await expect(page.getByRole('status').filter({ hasText: '配置已明确启用' })).toBeVisible();
  await expect(page.getByRole('cell', { name: '当前生效', exact: true })).toHaveCount(1);
  const active = (await (await page.request.get('/api/auth/oidc/configuration')).json()).active_id;
  reject = true;
  await page.getByRole('button', { name: '测试登录' }).first().click();
  await expect(page.getByRole('alert')).toContainText('公司登录验证失败');
  expect((await (await page.request.get('/api/auth/oidc/configuration')).json()).active_id).toBe(active);
  await page.getByRole('button', { name: '退出登录' }).click();
  reject = false;
  await page.getByRole('button', { name: '使用公司 Okta 登录' }).click();
  await expect(page).toHaveURL(/\/assets$/);
  const session = (await (await page.request.get('/api/auth/session')).json());
  expect(session.roles).toEqual(['field_engineer']);
  expect(session.local_password_available).toBe(false);
  await expect(page.getByRole('link', { name: '修改密码', exact: true })).toHaveCount(0);
  await page.goto('/settings/sso');
  await expect(page.getByRole('heading', { name: '无权访问此页面' })).toBeVisible();
});
