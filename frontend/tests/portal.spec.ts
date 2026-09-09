import { test, expect } from "@playwright/test";

test('正式门户连接真实后端并显示就绪状态', async ({ page }) => {
  await page.goto('/lab');
  await expect(page.getByRole('status')).toContainText('服务连接正常');
});

test("顶部切换工作区，侧栏跟随工作区且支持刷新与返回", async ({ page }) => {
  await page.goto("/");
  const top = page.getByRole("navigation", { name: "工作区", exact: true });
  const side = page.getByRole("navigation", { name: "当前工作区页面" });
  await expect(top.getByRole("link")).toHaveCount(2);
  await expect(
    page.getByRole("heading", { name: "资产仪表板", exact: true }),
  ).toBeVisible();
  await top.getByRole("link", { name: "DGA 实验室" }).click();
  await expect(
    page.getByRole("heading", { name: "实验室首页", exact: true }),
  ).toBeVisible();
  await expect(
    side.getByRole("link", { name: "资产仪表板", exact: true }),
  ).toHaveCount(0);
  await side.getByRole("link", { name: "检测工作台" }).click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "检测工作台", exact: true }),
  ).toBeVisible();
  await top.getByRole("link", { name: "资产管理与仪表板" }).click();
  await expect(page.getByRole('heading', { name: '资产仪表板', exact: true })).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "检测工作台", exact: true }),
  ).toBeVisible();
});

test("服务不可用有明确提示，重试可恢复", async ({ page }) => {
  let unavailable = true;
  await page.route("**/api/health", (route) =>
    route.fulfill({
      status: unavailable ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(
        unavailable
          ? { status: "unavailable", database: "unavailable" }
          : { status: "ok", database: "ok" },
      ),
    }),
  );
  await page.goto("/lab");
  await expect(page.getByRole("status")).toContainText("服务暂不可用");
  unavailable = false;
  await page.getByRole("button", { name: "重试连接" }).click();
  await expect(page.getByRole("status")).toContainText("服务连接正常");
});

test("无效地址可返回已知工作区，键盘可跳过导航", async ({ page }) => {
  await page.goto("/not-a-page");
  await expect(
    page.getByRole("heading", { name: "页面不存在", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "返回资产仪表板" }).click();
  await expect(
    page.getByRole("heading", { name: "资产仪表板", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
});
