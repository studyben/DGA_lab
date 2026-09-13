import { expect, test } from '@playwright/test';

const asset = '40000000-0000-0000-0000-000000000002';
const returnTo = `/assets/equipment/${asset}?return_to=${encodeURIComponent('/assets/sites/20000000-0000-0000-0000-000000000001?product_line=PV')}`;

test('变压器趋势按方法分组，限定结果不计统计，并保留返回上下文', async ({ page, baseURL }) => {
  test.setTimeout(90000);
  const login = await page.request.post('/api/auth/login', { headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  expect(login.ok()).toBeTruthy();
  const headers = { Origin: new URL(baseURL!).origin, 'X-CSRF-Token': (await login.json()).csrf_token };
  const version = `TREND-BROWSER-${Date.now()}`;
  const createMethod = async (label: string) => {
    const response = await page.request.post('/api/laboratory/configuration/methods', { headers, data: {
      test_type: 'MOISTURE', display_name: label, version_label: label,
      fields: [{ code: 'MOISTURE', display_name: '微水', unit_code: 'TEST-UNIT' }],
    } });
    expect(response.status()).toBe(201);
    return (await response.json()).id as string;
  };
  const first = await createMethod(version);
  const other = await createMethod(version + '-OTHER');
  for (const [day, method, qualifier, value] of [
    ['01', first, 'EQ', '2'], ['02', first, 'EQ', '4'], ['04', first, 'EQ', '8'],
    ['05', first, 'ND', null], ['06', other, 'EQ', '100'],
  ]) {
    const received = await page.request.post('/api/laboratory/samples', { headers, data: {
      sampled_at: `2026-07-${day}T12:00:00Z`, received_at: `2026-07-${day}T13:00:00Z`,
      site_name: 'fixture', equipment_serial: 'fixture', container_count: 1,
      identity_status: 'ASSOCIATED', formal_asset_id: asset,
    } });
    expect(received.status()).toBe(201);
    const barcode = (await received.json()).barcode_value;
    const entry = await page.request.post(`/api/laboratory/samples/${barcode}/tests`, { headers, data: {
      test_type: 'MOISTURE', method_version_id: method, measured_at: `2026-07-${day}T14:00:00Z`,
      result: { kind: 'MOISTURE', result: { qualifier, value } },
    } });
    expect(entry.status()).toBe(201);
    const finalized = await page.request.post(`/api/laboratory/samples/${barcode}/finalization`, { headers, data: { acknowledged_warning_codes: [] } });
    expect(finalized.status()).toBe(200);
  }
  await page.goto(returnTo);
  await expect(page.getByRole('link', { name: '查看变压器趋势', exact: true })).toBeVisible();
  await page.getByRole('link', { name: '查看变压器趋势', exact: true }).click();
  await page.getByLabel('趋势检测类型').selectOption('MOISTURE');
  await page.getByLabel('可比较方法分组').selectOption({ label: `${version} · ${version} · TEST-UNIT` });
  await expect(page.getByRole('region', { name: '趋势统计' })).toContainText('有效数值 3');
  await expect(page.getByRole('region', { name: '最新观测' })).toContainText('ND');
  await expect(page.getByRole('table', { name: '趋势结果' })).toContainText('方法版本不同');
  await expect(page.getByRole('table', { name: '趋势结果' })).toContainText('限定结果不参与统计');
  await expect(page.getByRole('img', { name: '检测趋势图' })).toBeVisible();
  const trendUrl = page.url();
  const source = page.getByRole('table', { name: '趋势结果' }).locator('tbody tr').first();
  const sourceBarcode = (await source.getByRole('link').first().textContent())!;
  await source.getByText('查看来源', { exact: true }).click();
  await source.getByRole('link', { name: '查看条码报告', exact: true }).click();
  await expect(page.getByLabel('油样条码', { exact: true })).toHaveValue(sourceBarcode);
  await expect(page.getByText('报告已生成，可在线预览或下载。')).toBeVisible({ timeout: 30000 });
  await page.goto(trendUrl);
  await expect(page.getByRole('img', { name: '检测趋势图' })).toBeVisible();
  await page.screenshot({ path: '/app/test-results/trends-desktop.png', fullPage: true });
  for (const width of [1920, 1280]) {
    await page.setViewportSize({ width, height: 1080 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    const controls = page.locator('.trend-filters input, .trend-filters select, .trend-filters button');
    const boxes = await controls.evaluateAll(elements => elements.map(el => {
      const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    }));
    for (let i=0;i<boxes.length;i++) for (let j=i+1;j<boxes.length;j++) {
      const a=boxes[i],b=boxes[j];
      expect(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top).toBeTruthy();
    }
  }
  await page.getByLabel('趋势结束日期').fill('2026-07-02');
  await page.getByRole('button', { name: '筛选趋势', exact: true }).click();
  await expect(page.getByRole('region', { name: '趋势统计' })).toContainText('有效数值 2');
  await page.getByLabel('趋势检测类型').selectOption('DGA');
  await page.getByLabel('趋势指标').selectOption('CO');
  await expect(page.getByRole('status').filter({ hasText: '没有已定稿的检测结果' })).toBeVisible();
  await page.getByRole('link', { name: '返回设备详情', exact: true }).click();
  await expect(page).toHaveURL(new URL(returnTo, baseURL).href);
});

test('趋势请求失败可重试，非法返回链接不跳转外站', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', { headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  await page.route('**/api/condition-analysis/**', route => route.fulfill({ status: 503, json: { code: 'trend_source_unavailable' } }));
  await page.goto(`/assets/analysis/trends?asset_id=${asset}&return_to=${encodeURIComponent('https://example.com/')}`);
  await expect(page.getByRole('alert')).toContainText('趋势数据暂不可用');
  await expect(page.getByRole('link', { name: '返回设备详情', exact: true })).toHaveAttribute('href', `/assets/equipment/${asset}`);
  await page.unroute('**/api/condition-analysis/**');
  await page.getByRole('button', { name: '重试趋势' }).click();
  await expect(page.getByRole('region', { name: '变压器身份' })).toContainText('SYS-TX-002');
  await page.getByLabel('趋势开始日期').fill('2026-09-02');
  await page.getByLabel('趋势结束日期').fill('2026-09-01');
  await page.getByRole('button', { name: '筛选趋势', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('日期范围');
});
