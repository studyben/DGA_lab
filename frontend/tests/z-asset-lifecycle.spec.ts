import { test, expect } from '@playwright/test';

test('授权用户更换变压器，旧设备进入维修中心且保留时间线；只读用户无写入口', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const login = await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  const session = await login.json();
  const spare = '40000000-0000-0000-0000-000000000099';
  const prepared = await page.request.post(`/api/assets/equipment/${spare}/move`, {
    headers: { Origin: origin, 'X-CSRF-Token': session.csrf_token },
    data: { destination: 'REPAIR_CENTER', effective_at: '2025-01-01T00:00:00Z', reason: 'Prepare test spare', expected_revision: 0 },
  });
  expect(prepared.status()).toBe(200);
  await page.goto('/assets/equipment/40000000-0000-0000-0000-000000000002');
  await page.getByLabel('资产操作').selectOption('replace');
  await page.getByLabel('候选设备搜索').fill('TX-SPARE-0099');
  await page.getByRole('button', { name: '搜索候选设备', exact: true }).click();
  await page.getByLabel('目标设备').selectOption(spare);
  await page.getByLabel('生效日期（UTC）').fill('2026-09-01');
  await page.getByLabel('操作原因').fill('Browser replacement acceptance');
  await page.getByRole('button', { name: '提交资产变更', exact: true }).click();
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('维修中心');
  await expect(page.getByRole('region', { name: '资产时间线' })).toContainText('Browser replacement acceptance');
  await expect(page.getByRole('table', { name: '油样检测历史' })).toContainText('DGA-20260802-000001');
  await page.goto('/assets/repair-center');
  await page.getByLabel('资产搜索').fill('TX-CURRENT-2002');
  await page.getByRole('button', { name: '筛选资产', exact: true }).click();
  await page.getByRole('link', { name: 'TX-CURRENT-2002', exact: true }).click();
  await expect(page.getByRole('region', { name: '资产时间线' })).toBeVisible();
  await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'field-user', password: 'Browser changed passphrase 84!' } });
  await page.reload();
  await expect(page.getByLabel('资产操作')).toHaveCount(0);
});
