import { test, expect } from '@playwright/test';

test('管理层可编辑现场，冲突保留输入，现场工程师无编辑入口', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const site = '20000000-0000-0000-0000-000000000001';
  const login = await page.request.post('/api/auth/login', { headers: { Origin: origin },
    data: { username: 'identity-management', password: 'Browser changed passphrase 84!' } });
  const csrf = (await login.json()).csrf_token;
  await page.goto('/assets/sites/' + site + '?product_line=PV');
  await page.getByRole('button', { name: '编辑现场资料', exact: true }).click();
  await page.getByLabel('现场名称', { exact: true }).fill('A3 browser site');
  await page.getByRole('button', { name: '保存现场资料', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '现场资料已保存' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'A3 browser site', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '编辑现场资料', exact: true }).click();
  await page.getByLabel('现场名称', { exact: true }).fill('Unsaved browser input');
  const current = (await (await page.request.get('/api/assets/sites/' + site)).json()).site;
  expect((await page.request.put('/api/assets/sites/' + site + '/basics', {
    headers: { Origin: origin, 'X-CSRF-Token': csrf },
    data: { expected_revision: current.revision, site_name: 'Concurrent update', product_line: 'PV', power_mw: 10 },
  })).ok()).toBeTruthy();
  await page.getByRole('button', { name: '保存现场资料', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('已被他人修改');
  await expect(page.getByLabel('现场名称', { exact: true })).toHaveValue('Unsaved browser input');
  await page.getByLabel('序列号筛选', { exact: true }).fill('no-match');
  await page.getByRole('button', { name: '应用筛选', exact: true }).click();
  await expect(page.getByText('没有符合条件的记录。')).toBeVisible();
  await expect(page.getByLabel('现场名称', { exact: true })).toHaveValue('Unsaved browser input');
  await page.request.post('/api/auth/login', { headers: { Origin: origin },
    data: { username: 'field-user', password: 'Browser changed passphrase 84!' } });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Concurrent update', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '编辑现场资料', exact: true })).toHaveCount(0);
});
