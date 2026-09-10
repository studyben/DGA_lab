import { test, expect } from '@playwright/test';


test('收样人员按整机序列号查找并明确选择采样时的变压器', async ({ page, baseURL }) => {
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

  const result = page.getByRole('group', { name: 'INV-UNIT-7788' });
  await expect(result).toContainText('Prairie Solar LLC');
  await expect(result).toContainText('Prairie Sun');
  await expect(result).toContainText('Texas, USA');
  await expect(result).toContainText('TX-CURRENT-2002');
  await expect(page.getByText('尚未选择正式资产')).toBeVisible();

  await result.getByRole('button', { name: '选择变压器 TX-CURRENT-2002' }).click();
  await expect(page.getByRole('region', { name: '资产关联结果' }).getByRole('status'))
    .toContainText('已关联 TX-CURRENT-2002');

  await page.getByRole('textbox', { name: '采样时间', exact: true }).fill('2023-06-01T12:00');
  await expect(page.getByRole('group', { name: 'INV-UNIT-7788' })).toHaveCount(0);
  await expect(page.getByText('尚未选择正式资产')).toBeVisible();

  await page.getByRole('button', { name: '搜索正式资产' }).click();
  const historicalResult = page.getByRole('group', { name: 'INV-UNIT-7788' });
  await expect(historicalResult).toContainText('TX-OLD-1001');
  await expect(historicalResult).not.toContainText('TX-CURRENT-2002');
});


test('采样时间改变后忽略仍在返回途中的旧资产结果', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: {
      username: 'browser-admin',
      password: 'Browser changed passphrase 84!',
    },
  });
  await page.route('**/api/assets/search?*', async route => {
    const response = await route.fetch();
    await new Promise(resolve => setTimeout(resolve, 300));
    await route.fulfill({ response });
  });
  await page.goto('/lab/reception');
  await page.getByRole('textbox', { name: '采样时间', exact: true }).fill('2025-06-01T12:00');
  await page.getByLabel('整机或变压器序列号').fill('INV-UNIT-7788');
  await page.getByRole('button', { name: '搜索正式资产' }).click();

  await page.getByRole('textbox', { name: '采样时间', exact: true }).fill('2023-06-01T12:00');
  await page.waitForTimeout(500);

  await expect(page.getByRole('group', { name: 'INV-UNIT-7788' })).toHaveCount(0);
  await expect(page.getByText('尚未选择正式资产')).toBeVisible();
});


test('采样时间在资产上下文解码期间改变时不提交旧选择', async ({ page, baseURL }) => {
  await page.addInitScript(() => {
    const realFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const response = await realFetch(...args);
      const url = String(args[0]);
      if (!url.includes('/sampling-context?')) return response;
      return new Proxy(response, {
        get(target, property) {
          if (property === 'json') return async () => {
            await new Promise(resolve => setTimeout(resolve, 300));
            return target.json();
          };
          const value = Reflect.get(target, property, target);
          return typeof value === 'function' ? value.bind(target) : value;
        },
      });
    };
  });
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

  await page.getByRole('textbox', { name: '采样时间', exact: true }).fill('2023-06-01T12:00');
  await page.waitForTimeout(500);

  await expect(page.getByText('尚未选择正式资产')).toBeVisible();
  await expect(page.getByText('已关联 TX-CURRENT-2002')).toHaveCount(0);
});
