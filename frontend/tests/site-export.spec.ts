import { expect, test } from '@playwright/test';

test('只读账号从筛选现场列表下载全部现场，管理员从导入页下载', async ({ page, baseURL }) => {
  const login = await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'field-user', password: 'Browser changed passphrase 84!' },
  });
  expect(login.ok()).toBeTruthy();
  await page.goto('/assets/sites?product_line=ESS&site=missing&page=2&page_size=1');
  await expect(page.getByRole('button', { name: '下载当前现场汇总', exact: true })).toBeVisible();
  const responsePromise = page.waitForResponse(r => r.url().endsWith('/api/assets/sites/export'));
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载当前现场汇总', exact: true }).click();
  const [response, download] = await Promise.all([responsePromise, downloadPromise]);
  expect(response.status()).toBe(200);
  expect(download.suggestedFilename()).toMatch(/^site-reference-\d{8}T\d{6}Z\.xlsx$/);
  await download.saveAs(test.info().outputPath('sites.xlsx'));
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream!) chunks.push(chunk);
  const file = Buffer.concat(chunks);
  expect(file.subarray(0, 2).toString()).toBe('PK');
  expect(file.length).toBeGreaterThan(3000);
  await expect(page.getByRole('status').filter({ hasText: '已生成现场汇总' })).toBeVisible();
  // Verify the same public HTTP file independently of current UI filters.
  expect(await response.headerValue('cache-control')).toBe('no-store');
  await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' },
  });
  await page.goto('/assets/import');
  const second = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载当前现场汇总', exact: true }).click();
  expect((await second).suggestedFilename()).toMatch(/\.xlsx$/);
});

test('生成期间阻止重复请求，服务失败后可以重试', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'field-user', password: 'Browser changed passphrase 84!' },
  });
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  let requests = 0;
  await page.route('**/api/assets/sites/export', async route => {
    requests++;
    if (requests === 1) {
      await pending;
      await route.fulfill({ status: 503, contentType: 'application/json', body: '{"code":"site_export_unavailable"}' });
    } else await route.continue();
  });
  await page.goto('/assets');
  await page.getByRole('button', { name: '下载当前现场汇总', exact: true }).click();
  await expect(page.getByRole('button', { name: '正在生成现场汇总…' })).toBeDisabled();
  await page.keyboard.press('Enter');
  expect(requests).toBe(1);
  release();
  await expect(page.getByRole('alert')).toContainText('生成失败');
  await expect(page.getByRole('status').filter({ hasText: '已生成现场汇总' })).toHaveCount(0);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载当前现场汇总', exact: true }).click();
  await download;
  expect(requests).toBe(2);
  await expect(page.getByRole('alert')).toHaveCount(0);
});

for (const scenario of [
  { name: '登录过期', status: 401, expected: '登录已失效' },
  { name: '权限撤回', status: 403, expected: '没有读取现场的权限' },
  { name: '错误格式', status: 200, expected: '下载响应格式异常' },
  { name: '网络中断', status: 0, expected: '网络连接失败' },
]) test(`${scenario.name}有明确提示且不下载错误文件`, async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'field-user', password: 'Browser changed passphrase 84!' },
  });
  await page.route('**/api/assets/sites/export', route => scenario.status === 0
    ? route.abort('failed') : route.fulfill({ status: scenario.status, contentType: 'application/json', body: '{}' }));
  await page.goto('/assets');
  const downloads: string[] = [];
  page.on('download', file => downloads.push(file.suggestedFilename()));
  await page.getByRole('button', { name: '下载当前现场汇总', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText(scenario.expected);
  await expect(page.getByRole('button', { name: '下载当前现场汇总', exact: true })).toBeEnabled();
  expect(downloads).toEqual([]);
});
