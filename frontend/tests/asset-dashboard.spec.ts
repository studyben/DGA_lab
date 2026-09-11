import { expect, test } from '@playwright/test';

test('按产品线筛选现场、配置列表并查看现场与一级设备', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'field-user', password: 'Browser changed passphrase 84!' },
  });
  await page.goto('/assets');
  await expect(page.getByRole('region', { name: '筛选结果指标' })).toContainText('逆变器整机');
  await expect(page.getByRole('table', { name: '现场列表' })).toContainText('Prairie Sun');
  await page.getByRole('button', { name: '储能 ESS', exact: true }).click();
  await expect(page.getByRole('table', { name: '现场列表' })).toContainText('80 MWh');
  await page.getByLabel('每页条数').selectOption('1');
  await expect(page.getByRole('table', { name: '现场列表' })).toContainText('Desert Star');
  await page.getByRole('button', { name: '下一页' }).click();
  await expect(page.getByRole('table', { name: '现场列表' })).toContainText('Prairie Sun');
  await expect(page.getByRole('region', { name: '筛选结果指标' })).toContainText('储能系统');
  await page.getByRole('columnheader', { name: '现场名称' }).getByRole('button').click();
  await expect(page.getByRole('table', { name: '现场列表' })).toContainText('Prairie Sun');
  await page.getByLabel('客户筛选').fill('Prairie');
  await page.getByRole('button', { name: '应用筛选' }).click();
  await expect(page.getByRole('table', { name: '现场列表' })).not.toContainText('Desert Star');
  await page.getByText('显示列', { exact: true }).click();
  await page.getByRole('checkbox', { name: '位置', exact: true }).uncheck();
  await expect(page.getByRole('columnheader', { name: '位置' })).toHaveCount(0);
  await page.getByRole('link', { name: 'Prairie Sun', exact: true }).click();
  await expect(page.getByRole('region', { name: '现场资料' })).toContainText('2020');
  await expect(page.getByRole('region', { name: '现场资料' })).toContainText('Commissioning date');
  await expect(page.getByRole('table', { name: '一级设备清单' })).toContainText('ESS-ROOT-001');
  await expect(page.getByRole('table', { name: '一级设备清单' })).not.toContainText('PCS-CHILD-001');
  await page.getByLabel('序列号筛选').fill('not-found');
  await page.getByRole('button', { name: '应用筛选' }).click();
  await expect(page.getByText('没有符合条件的记录。')).toBeVisible();
  await page.getByRole('button', { name: '清除筛选' }).click();
  await expect(page.getByRole('table', { name: '一级设备清单' })).toContainText('ESS-ROOT-001');
  await page.getByRole('link', { name: '返回现场列表' }).click();
  await expect(page.getByLabel('客户筛选')).toHaveValue('Prairie');
  await expect(page.getByRole('columnheader', { name: '位置' })).toHaveCount(0);
  await page.getByRole('button', { name: '光伏 PV', exact: true }).click();
  await expect(page.getByRole('table', { name: '现场列表' })).not.toContainText('MWh');
});

test('快速切换产品线不显示旧响应且服务失败可重试', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'field-user', password: 'Browser changed passphrase 84!' },
  });
  let fail = true;
  await page.route('**/api/assets/dashboard?*', async route => {
    if (fail) { await route.fulfill({ status: 503, body: '{}' }); return; }
    const response = await route.fetch();
    if (!route.request().url().includes('product_line=ESS')) await new Promise(resolve => setTimeout(resolve, 500));
    await route.fulfill({ response });
  });
  await page.goto('/assets');
  await expect(page.getByRole('alert')).toContainText('资产服务暂不可用');
  fail = false;
  await page.getByRole('button', { name: '重试', exact: true }).click();
  await page.getByRole('button', { name: '储能 ESS', exact: true }).click();
  await expect(page.getByRole('table', { name: '现场列表' })).toContainText('80 MWh');
  await page.waitForTimeout(650);
  await expect(page.getByRole('table', { name: '现场列表' })).toContainText('80 MWh');
});
