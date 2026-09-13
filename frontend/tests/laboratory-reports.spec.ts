import { expect, test } from '@playwright/test';

const barcode = 'DGA-20260802-000002';

test('finalized barcode exposes only the current generated report', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const login = await page.request.post('/api/auth/login', {
    headers: { Origin: origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' },
  });
  expect(login.ok()).toBeTruthy();
  const session = await login.json();
  const mutationHeaders = { Origin: origin, 'X-CSRF-Token': session.csrf_token };

  await page.goto('/lab/reports');
  await page.getByLabel('油样条码').fill(`  ${barcode.toLowerCase()}  `);
  await page.getByRole('button', { name: '查询报告' }).click();
  await expect(page.getByText('检测尚未整体定稿，无法生成报告。')).toBeVisible();
  await expect(page.getByRole('link', { name: '下载 PDF' })).toHaveCount(0);

  const workbench = await page.request.get(`/api/laboratory/workbench/${barcode}`);
  expect(workbench.ok()).toBeTruthy();
  const method = (await workbench.json()).methods.find(
    (item: { test_type: string; is_active: boolean }) => item.test_type === 'DGA' && item.is_active,
  );
  const measurement = (value: string) => ({ qualifier: 'EQ', value });
  const added = await page.request.post(`/api/laboratory/samples/${barcode}/tests`, {
    headers: mutationHeaders,
    data: {
      test_type: 'DGA', method_version_id: method.id,
      measured_at: '2026-08-03T15:30:00Z', instrument_name: 'GC-BROWSER', notes: '报告验收',
      result: {
        kind: 'DGA', h2: measurement('10.125'), ch4: measurement('11.250'),
        c2h2: measurement('0.125'), c2h4: measurement('4.500'),
        c2h6: measurement('5.750'), co: measurement('120.000'), co2: measurement('900.000'),
      },
    },
  });
  expect(added.status()).toBe(201);

  const finalized = await page.request.post(
    `/api/laboratory/samples/${encodeURIComponent(barcode)}/finalization`,
    { headers: mutationHeaders, data: { acknowledged_warning_codes: [] } },
  );
  expect(finalized.ok()).toBeTruthy();

  await page.getByRole('button', { name: '查询报告' }).click();
  await expect(page.getByText(/报告排队中|报告正在生成|报告已生成/)).toBeVisible();
  await expect(page.getByText('报告已生成，可在线预览或下载。')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTitle('中文检测报告预览')).toBeVisible();
  const download = page.getByRole('link', { name: '下载 PDF' });
  await expect(download).toBeVisible();
  const file = await page.request.get(await download.getAttribute('href') ?? '');
  expect(file.status()).toBe(200);
  expect(file.headers()['content-type']).toContain('application/pdf');
  expect((await file.body()).subarray(0, 4).toString()).toBe('%PDF');

  const withdrawn = await page.request.post(
    `/api/laboratory/samples/${encodeURIComponent(barcode)}/finalization-withdrawals`,
    { headers: mutationHeaders, data: { reason: '浏览器验收撤回定稿' } },
  );
  expect(withdrawn.ok()).toBeTruthy();
  await page.getByRole('button', { name: '查询报告' }).click();
  await expect(page.getByText('检测尚未整体定稿，无法生成报告。')).toBeVisible();
  await expect(download).toHaveCount(0);

  const refinalized = await page.request.post(
    `/api/laboratory/samples/${encodeURIComponent(barcode)}/finalization`,
    { headers: mutationHeaders, data: { acknowledged_warning_codes: [] } },
  );
  expect(refinalized.ok()).toBeTruthy();
  await page.getByRole('button', { name: '查询报告' }).click();
  await expect(page.getByText('报告已生成，可在线预览或下载。')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTitle('中文检测报告预览')).toBeVisible();
  await expect(page.getByText('版本', { exact: true })).toHaveCount(0);
});
