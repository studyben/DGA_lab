import { test, expect } from '@playwright/test';

test('方法版本说明解释控制范围、历史保留和停用方式', async ({ page, baseURL }) => {
  const login = await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' },
  });
  expect(login.ok()).toBeTruthy();
  await page.goto('/lab/configuration');
  const help = page.getByRole('region', { name: '方法版本使用说明' });
  await expect(help).toBeVisible();
  await expect(help).toContainText('校验小数位数、录入范围及允许的结果限定符');
  await expect(help).toContainText('不是报告版本');
  await expect(help).toContainText('日常检测可重复使用已有方法版本');
  await expect(help).toContainText('已定稿报告不会随新版本改变');
  await expect(help).toContainText('目前不提供删除功能');
});
