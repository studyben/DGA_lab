import { test, expect } from '@playwright/test';
import path from 'node:path';

test('管理员上传校验、查看错误、确认重复序列号警告后整批发布新资产', async ({ page, baseURL }) => {
  await page.request.post('/api/auth/login', { headers: { Origin: new URL(baseURL!).origin },
    data: { username: 'browser-admin', password: 'Browser changed passphrase 84!' } });
  await page.goto('/assets/import');
  await expect(page.getByRole('link', { name: '下载 Excel 模板与参考资料' })).toBeVisible();
  await page.getByLabel('选择 Excel 文件').setInputFiles({ name: 'invalid.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.from('invalid workbook') });
  await page.getByRole('button', { name: '上传并校验' }).click();
  await expect(page.getByRole('table', { name: '逐行问题' })).toContainText('无法安全读取');
  await expect(page.getByRole('button', { name: '发布新资产', exact: true })).toBeDisabled();
  await page.getByLabel('选择 Excel 文件').setInputFiles(path.join(process.cwd(), 'tests/fixtures/asset-import.xlsx'));
  await page.getByRole('button', { name: '上传并校验' }).click();
  await expect(page.getByRole('table', { name: '逐行问题' })).toContainText('序列号重复', { timeout: 15000 });
  await expect(page.getByRole('button', { name: '发布新资产', exact: true })).toBeDisabled();
  await page.getByLabel('我已核对全部警告，确认这些是需要新增的物理设备').check();
  await page.getByRole('button', { name: '发布新资产', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '整批发布成功' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('table', { name: '资产预览' })).toContainText('AST-');
  await page.getByRole('region', { name: '批次历史' }).getByRole('button', { name: 'asset-import.xlsx', exact: true }).first().click();
  await expect(page.getByRole('table', { name: '资产预览' })).toContainText('AST-');
  await page.getByRole('table', { name: '资产预览' }).getByRole('link').click();
  await expect(page.getByRole('region', { name: '设备属性' })).toContainText('维修中心');
});
