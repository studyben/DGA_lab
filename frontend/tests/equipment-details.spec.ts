import { expect, test } from '@playwright/test';

test('储能系统逐级进入电池柜和 PCS 子设备，按类型展示属性', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', { headers: { Origin: new URL(baseURL!).origin }, data: { username: 'field-user', password: 'Browser changed passphrase 84!' } });
  await page.goto('/assets/sites/20000000-0000-0000-0000-000000000001?product_line=ESS');
  await page.getByRole('table', { name: '一级设备清单' }).getByRole('link', { name: 'ESS-01', exact: true }).click();
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('未评估');
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('20 MWh');
  await page.getByRole('table', { name: '子设备清单' }).getByRole('link', { name: 'BAT-01', exact: true }).click();
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('示例电芯厂');
  await expect(page.getByRole('region', { name: '设备属性' })).not.toContainText('额定电压');
  await page.getByRole('navigation', { name: '设备路径' }).getByRole('link', { name: 'ESS-01', exact: true }).click();
  await page.getByRole('table', { name: '子设备清单' }).getByRole('link', { name: 'PCS-01', exact: true }).click();
  await expect(page.getByRole('region', { name: '设备属性' })).not.toContainText('电池生产厂商');
  await expect(page.getByRole('table', { name: '子设备清单' })).toContainText('PCS-BODY-01');
  await page.getByRole('table', { name: '子设备清单' }).getByRole('link', { name: 'MVT-01', exact: true }).click();
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('变压器');
  await expect(page.getByRole('navigation', { name: '设备路径' })).toContainText('PCS-01');
  await page.goto('/assets/equipment/40000000-0000-0000-0000-000000000002');
  await expect(page.getByRole('table', { name: '油样检测历史' })).toContainText('DGA-20260802-000001');
  await expect(page.getByRole('link', { name: 'DGA-20260802-000001', exact: true })).toHaveCount(0);
  const denied = await page.request.get('/api/laboratory/workbench/DGA-20260802-000001');
  expect(denied.status()).toBe(403);
});

test('设备检测历史按条码跳转工作台', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', { headers: { Origin: new URL(baseURL!).origin }, data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  await page.goto('/assets/equipment/40000000-0000-0000-0000-000000000002');
  await page.getByRole('link', { name: 'DGA-20260802-000001', exact: true }).click();
  await expect(page.getByLabel('扫描或输入油样条码')).toHaveValue('DGA-20260802-000001');
  await page.getByRole('button', { name: '加载油样', exact: true }).click();
  await expect(page.getByLabel('设备序列号', { exact: true })).toHaveValue('TX-CURRENT-2002');
});
