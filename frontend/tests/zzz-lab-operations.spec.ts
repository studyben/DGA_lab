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
