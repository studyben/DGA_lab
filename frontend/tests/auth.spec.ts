import { test, expect } from '@playwright/test';

test('未登录先登录，首次修改密码后进入门户并退出', async ({ page }) => {
  await page.goto('/lab');
  await expect(page.getByRole('heading', { name: '登录', exact: true })).toBeVisible();
  await page.getByLabel('用户名', { exact: true }).fill('first-login');
  await page.getByLabel('密码', { exact: true }).fill('Browser initial passphrase 42!');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('heading', { name: '首次登录，请修改密码' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: '工作区', exact: true })).toHaveCount(0);
  await page.getByLabel('当前密码', { exact: true }).fill('Browser initial passphrase 42!');
  await page.getByLabel('新密码', { exact: true }).fill('Browser changed passphrase 84!');
  await page.getByLabel('确认新密码', { exact: true }).fill('Browser changed passphrase 84!');
  await page.getByRole('button', { name: '保存密码并继续' }).click();
  await expect(page.getByRole('heading', { name: '实验室首页', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '实验室首页', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByRole('heading', { name: '登录', exact: true })).toBeVisible();
});

test('现场工程师没有实验室入口且不能用地址绕过权限', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', {
    headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'field-user', password: 'Browser changed passphrase 84!' },
  });
  await page.goto('/');
  const top = page.getByRole('navigation', { name: '工作区', exact: true });
  await expect(top.getByRole('link', { name: 'DGA 实验室' })).toHaveCount(0);
  await page.goto('/lab');
  await expect(page.getByRole('heading', { name: '无权访问此页面' })).toBeVisible();
  const response = await page.request.get('/api/laboratory/access');
  expect(response.status()).toBe(403);
});
