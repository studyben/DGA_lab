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
  const picker = page.getByRole('combobox', { name: '目标设备', exact: true });
  await picker.click();
  const options = page.getByRole('listbox', { name: '目标设备搜索结果' }).getByRole('option');
  await expect(options).not.toHaveCount(0);
  const count = await options.count();
  for (let i = 0; i < count; i++) await picker.press('ArrowDown');
  await expect.poll(() => page.getByRole('listbox', { name: '目标设备搜索结果' }).evaluate(list => {
    const active = list.querySelector('.active-option')!;
    const item = active.getBoundingClientRect(), box = list.getBoundingClientRect();
    return item.top >= box.top - 1 && item.bottom <= box.bottom + 1;
  })).toBe(true);
  await picker.fill('NO-SUCH-DEVICE');
  await expect(page.getByText('本页没有匹配设备，请修改搜索条件或翻页。')).toBeVisible();
  await picker.fill('TX-SPARE-0099');
  await expect(page.getByRole('option', { name: /TX-SPARE-0099.*SYS-TX-099/ })).toBeVisible();
  await page.getByLabel('生效日期和时间（UTC）', { exact: true }).fill('2026-09-01T08:00');
  await page.getByLabel('操作原因').fill('Browser replacement acceptance');
  await page.getByRole('button', { name: '提交资产变更', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('仅输入文字不能提交');
  await picker.click();
  await picker.press('ArrowDown');
  await picker.press('Enter');
  await expect(picker).toHaveValue(/TX-SPARE-0099.*SYS-TX-099/);
  await page.getByRole('button', { name: '清空目标设备', exact: true }).click();
  await expect(picker).toHaveValue('');
  await picker.fill('TX-SPARE-0099');
  await page.getByRole('option', { name: /TX-SPARE-0099.*SYS-TX-099/ }).click();
  await page.getByLabel('生效日期和时间（UTC）', { exact: true }).fill('2026-09-01T08:00');
  await page.getByLabel('操作原因').fill('Browser replacement acceptance');
  await page.getByRole('button', { name: '提交资产变更', exact: true }).click();
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('维修中心');
  await expect(page.getByRole('region', { name: '资产时间线' })).toContainText('Browser replacement acceptance');
  await expect(page.getByRole('table', { name: '油样检测历史' })).toContainText('DGA-20260802-000001');
  await page.getByLabel('资产操作').selectOption('status');
  await page.getByLabel('目标状态').selectOption('SPARE');
  await page.getByLabel('生效日期和时间（UTC）', { exact: true }).fill('2026-09-01T08:00');
  await page.getByLabel('操作原因').fill('Same day repair complete');
  await page.getByRole('button', { name: '提交资产变更', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('必须晚于该设备已有的最新变更时间');
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('维修中');
  await page.getByLabel('生效日期和时间（UTC）', { exact: true }).fill('2026-09-01T09:00');
  await page.getByRole('button', { name: '提交资产变更', exact: true }).click();
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('备用');
  await expect(page.getByRole('region', { name: '资产时间线' })).toContainText('2026-09-01 09:00:00 UTC');
  await page.goto('/assets/repair-center');
  const repairTable = page.getByRole('table', { name: '维修中心清单' });
  await expect(repairTable).toBeVisible();
  const layout = await repairTable.evaluate(table => ({
    width: table.getBoundingClientRect().width,
    containerWidth: table.parentElement!.getBoundingClientRect().width,
    cellPadding: parseFloat(getComputedStyle(table.querySelector('td')!).paddingLeft),
  }));
  expect(layout.width).toBeGreaterThanOrEqual(layout.containerWidth * 0.95);
  expect(layout.cellPadding).toBeGreaterThanOrEqual(8);
  await expect(page.getByRole('button', { name: '筛选资产', exact: true })).toHaveCSS('border-radius', '6px');
  await page.getByLabel('资产搜索').fill('TX-CURRENT-2002');
  await page.getByRole('button', { name: '筛选资产', exact: true }).click();
  await page.getByRole('link', { name: 'TX-CURRENT-2002', exact: true }).click();
  await expect(page.getByRole('region', { name: '资产时间线' })).toBeVisible();
  await page.request.post('/api/auth/login', { headers: { Origin: origin }, data: { username: 'field-user', password: 'Browser changed passphrase 84!' } });
  await page.reload();
  await expect(page.getByLabel('资产操作')).toHaveCount(0);
});
