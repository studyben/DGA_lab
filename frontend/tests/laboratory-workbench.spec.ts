import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.request.post('/api/auth/login', {
    headers: { Origin: 'http://frontend:8080' },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' },
  });
});

async function addDga(page: import('@playwright/test').Page, h2: string) {
  await page.getByRole('button', { name: '新增DGA' }).click();
  const values: Record<string, string> = {
    'H₂结果': h2,
    'CH₄结果': '11.25',
    'C₂H₂结果': '0.125',
    'C₂H₄结果': '4.5',
    'C₂H₆结果': '5.75',
    'CO结果': '120',
    'CO₂结果': '900',
  };
  for (const [label, value] of Object.entries(values)) {
    await page.getByLabel(label, { exact: true }).fill(value);
  }
  await page.getByRole('button', { name: '保存DGA检测' }).click();
}

test('scan barcode, add two DGA records, edit and delete', async ({ page }) => {
  await page.goto('/lab/workbench');
  await page.getByLabel('扫描或输入油样条码', { exact: true }).fill('DGA-20260802-000001');
  await page.getByRole('button', { name: '加载油样' }).click();
  await expect(page.getByRole('heading', { name: 'DGA-20260802-000001' })).toBeVisible();
  await expect(page.getByText('检测中', { exact: true })).toBeVisible();

  await addDga(page, '10.125');
  await expect(page.getByText('DGA 检测 #1')).toBeVisible();
  await addDga(page, '12.5');
  await expect(page.getByText('DGA 检测 #2')).toBeVisible();

  const cards = page.getByRole('article', { name: /DGA 检测 #/ });
  await cards.nth(0).getByRole('button', { name: '修改' }).click();
  await page.getByLabel('H₂结果', { exact: true }).fill('15');
  await page.getByRole('button', { name: '保存修改' }).click();
  await expect(cards.nth(0)).toContainText('H2 15');

  page.once('dialog', dialog => dialog.accept('误录的复测数据'));
  await cards.nth(1).getByRole('button', { name: '删除' }).click();
  await expect(cards).toHaveCount(1);
  await expect(page.getByText('DGA 检测 #2')).toHaveCount(0);
});
