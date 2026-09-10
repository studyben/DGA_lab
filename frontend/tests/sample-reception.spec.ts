import { expect, test } from '@playwright/test';


test('搜索正式资产、登记油样、预览打印条码并再次扫码取回', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: {
      username: 'browser-admin',
      password: 'Browser changed passphrase 84!',
    },
  });
  await page.goto('/lab/reception');

  await page.getByRole('textbox', { name: '采样时间', exact: true }).fill('2025-06-01T12:00');
  await page.getByLabel('整机或变压器序列号').fill('INV-UNIT-7788');
  await page.getByRole('button', { name: '搜索正式资产' }).click();
  await page.getByRole('group', { name: 'INV-UNIT-7788' })
    .getByRole('button', { name: '选择变压器 TX-CURRENT-2002' }).click();

  await page.getByRole('textbox', { name: '收样时间', exact: true }).fill('2025-06-02T09:30');
  await expect(page.getByLabel('现场名称')).toHaveValue('Prairie Sun');
  await expect(page.getByLabel('设备序列号')).toHaveValue('TX-CURRENT-2002');
  await expect(page.getByLabel('现场名称')).toBeDisabled();
  await expect(page.getByLabel('设备序列号')).toBeDisabled();
  await page.getByLabel('样品容器数量').fill('2');
  await page.getByLabel('备注').fill('Routine annual sample');
  await page.getByRole('button', { name: '登记油样并生成条码' }).click();

  const label = page.getByRole('region', { name: '条码标签预览' });
  await expect(label).toContainText('Prairie Sun');
  await expect(label).toContainText('TX-CURRENT-2002');
  await expect(label.getByLabel(/条码 DGA-/)).toBeVisible();
  await expect(label.getByText('容器 2 只')).toBeVisible();
  const barcode = await label.getByTestId('barcode-value').innerText();

  await page.evaluate(() => {
    window.print = () => { document.body.dataset.printed = 'true'; };
  });
  await page.getByRole('button', { name: '打印条码标签' }).click();
  await expect(page.locator('body')).toHaveAttribute('data-printed', 'true');

  await page.getByLabel('扫描或输入油样条码').fill(barcode);
  await page.getByRole('button', { name: '查询条码' }).click();
  const found = page.getByRole('region', { name: '条码查询结果' });
  await expect(found).toContainText(barcode);
  await expect(found).toContainText('Prairie Solar LLC');
  await expect(found).toContainText('2 只样品容器');
});
