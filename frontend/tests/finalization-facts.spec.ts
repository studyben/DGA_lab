import { expect, test } from '@playwright/test';

const asset = '40000000-0000-0000-0000-000000000051';

test('公开无请求定稿显示未请求，现有趋势仍读取有效结果', async ({ page, baseURL }, testInfo) => {
  const login = await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' },
  });
  expect(login.ok()).toBeTruthy();
  const history = await page.request.get(`/api/laboratory/assets/${asset}/test-history`);
  expect(history.ok()).toBeTruthy();
  const samples = (await history.json()).samples;
  expect(samples).toHaveLength(1);
  const barcode = samples[0].barcode_value;
  const status = await page.request.get(`/api/laboratory/reports/by-barcode/${barcode}`);
  expect((await status.json()).unavailable_reason).toBe('report_not_requested');
  await page.goto(`/lab/reports?barcode=${encodeURIComponent(barcode)}`);
  await expect(page.getByText('未请求', { exact: true })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: '检测已整体定稿' })).toHaveText('检测已整体定稿，尚未请求系统报告；有效检测结果不依赖 PDF 生成。');
  await expect(page.getByText(/请撤回并重新定稿/)).toHaveCount(0);
  await expect(page.getByRole('link', { name: '下载 PDF' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '重新生成报告' })).toHaveCount(0);
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('no-request-report-1920.png'), fullPage: true });
  await page.goto(`/assets/equipment/${asset}`);
  await page.getByRole('link', { name: '查看变压器趋势', exact: true }).click();
  await page.getByLabel('趋势检测类型').selectOption('MOISTURE');
  await expect(page.getByRole('table', { name: '趋势结果' })).toContainText(barcode);
  await expect(page.getByRole('region', { name: '趋势统计' })).toContainText('有效数值 1');
  await expect(page.getByRole('table', { name: '趋势结果' })).toContainText('7.25');
  await page.screenshot({ path: testInfo.outputPath('no-request-trend-1920.png'), fullPage: true });
});
