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
  await page.getByRole('button', { name: '检测包', exact: true }).click();
  const packageHelp = page.getByRole('region', { name: '检测包使用说明' });
  await expect(packageHelp).toContainText('不会自动生成检测数据');
  await expect(packageHelp).toContainText('请先在“方法版本”中添加并启用所需方法');
  await page.goto('/lab/workbench?barcode=DGA-20260802-000001');
  await page.getByRole('button', { name: '加载油样', exact: true }).click();
  await expect(page.getByText('需要新增检测包？', { exact: false })).toBeVisible();
  await expect(page.getByText('新增检测按钮不可用或找不到所需方法时', { exact: false })).toBeVisible();
});
