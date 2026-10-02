import React from "react";
import { TrendsPage } from './features/condition-analysis/TrendsPage';
import { RulesPage } from './features/condition-analysis/RulesPage';
import { HealthOverview } from './features/condition-analysis/HealthPanel';
import { AlarmCenterPage } from './features/condition-analysis/AlarmCenterPage';
import { ConfigurationPage } from './features/laboratory/ConfigurationPage';
import { createRoot } from "react-dom/client";
import { assetPages } from "./features/assets/pages";
import { laboratoryPages } from "./features/laboratory/pages";
import { analysisPages } from "./features/condition-analysis/pages";
import "./styles.css";
import { ConnectionStatus } from "./ConnectionStatus";
import sungrowLogo from "./assets/sungrow-logo.svg";
import { AuthProvider, AuthBoundary, SessionControls, useAuth } from './Auth';
import { ReceptionPage } from './features/laboratory/ReceptionPage';
import { WorkbenchPage } from './features/laboratory/WorkbenchPage';
import { DashboardPage, SiteDetailPage } from './features/assets/DashboardPage';
import { EquipmentDetailPage } from './features/assets/EquipmentDetailPage';
import { RepairCenterPage } from './features/assets/LifecyclePanel';
import { AssetImportPage } from './features/assets/AssetImportPage';
import { ReportPage } from './features/laboratory/ReportPage';
import { LaboratoryHomePage } from './features/laboratory/OperationsPages';
import { IdentityPage, LaboratoryLedgerPage } from './features/laboratory/SampleOperationsPanel';
import { UserManagementPage } from './features/identity/UserManagementPage';

const path =
  window.location.pathname === "/"
    ? "/assets"
    : window.location.pathname.replace(/\/$/, "");
const allPages = [...assetPages, ...laboratoryPages, ...analysisPages, { path: '/settings/users', title: '用户与角色', description: '管理内部账号、业务角色及访问状态。', permission: 'assets.read' }];
const siteId = path.match(/^\/assets\/sites\/([^/]+)$/)?.[1];
const equipmentId = path.match(/^\/assets\/equipment\/([^/]+)$/)?.[1];
const current = equipmentId ? { title: '设备详情', description: '查看设备属性、子设备和油样检测历史。', permission: 'assets.read' } : siteId ? { title: '现场详情', description: '查看现场基础资料及当前一级设备。', permission: 'assets.read' } : allPages.find((page) => page.path === path);
const inLab = path === "/lab" || path.startsWith("/lab/");
const workspace = inLab ? "DGA 实验室" : "资产管理与仪表板";

function App() {
  const { can } = useAuth();
  return (
    <>
      <a className="skip" href="#main">
        跳到主要内容
      </a>
      <header>
        <a href="/" className="brand">
          <img src={sungrowLogo} alt="SUNGROW" width={150} height={20} />
          <small>资产与油样管理</small>
        </a>
        <nav aria-label="工作区" className="workspaces">
          {can('assets.read') && <a href="/assets" aria-current={!inLab ? "page" : undefined}>
            资产管理与仪表板
          </a>}
          {can('laboratory.read') && <a href="/lab" aria-current={inLab ? "page" : undefined}>
            DGA 实验室
          </a>}
        </nav>
        <SessionControls />
      </header>
      <div className="shell">
        <aside>
          <p className="nav-caption">{inLab ? "实验室工作区" : "资产工作区"}</p>
          <nav aria-label="当前工作区页面">
            {(inLab ? laboratoryPages : assetPages).map((page, index) => (
              <a
                key={page.path}
                href={can(page.permission) ? page.path : undefined}
                aria-disabled={!can(page.permission) || undefined}
                title={can(page.permission) ? undefined : '当前账号无操作权限'}
                aria-current={path === page.path ? "page" : undefined}
              >
                <span aria-hidden="true" className="nav-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {page.title}
              </a>
            ))}
            {!inLab && can('analysis.read') && (
              <>
                <p className="nav-caption analysis-caption">状态分析</p>
                {analysisPages.map((page) => (
                  <a
                    key={page.path}
                    href={page.path}
                    aria-current={path === page.path ? "page" : undefined}
                  >
                    <span aria-hidden="true" className="nav-number">
                      ↗
                    </span>
                    {page.title}
                  </a>
                ))}
              </>
            )}
            {['identity.manage', 'identity.ordinary.manage', 'identity.am.manage'].some(can) && <><p className="nav-caption analysis-caption">系统管理</p><a href="/settings/users" aria-current={path === '/settings/users' ? 'page' : undefined}>用户与角色</a></>}
          </nav>
          <div className="sidebar-foot">
            <span className="small-mark">DGA LAB</span>
            <p>连接资产身份与检测记录</p>
          </div>
        </aside>
        <main id="main" tabIndex={-1}>
          <div className="content">
            <div className="breadcrumb">
              {workspace}
              <span aria-hidden="true">/</span>
              {current?.title ?? "页面不存在"}
            </div>
            <div className="page-heading">
              <div>
                <p className="eyebrow">
                  {inLab ? "LABORATORY" : "ASSET MANAGEMENT"}
                </p>
                <h1>{current?.title ?? "页面不存在"}</h1>
                <p>
                  {current?.description ??
                    "这个地址暂时无法访问，请从工作区导航选择页面。"}
                </p>
              </div>
              {!(path === '/assets/analysis/trends' || equipmentId || siteId || path === '/assets' || path === '/assets/sites') && <span className="outline-badge">工程基础阶段</span>}
            </div>
            {path === '/settings/users' ? <UserManagementPage/> : path === '/assets/analysis/alarms' ? <AlarmCenterPage/> : path === '/assets/analysis/rules' ? <RulesPage/> : path === '/assets/analysis/health' ? <HealthOverview/> : path === '/assets/analysis/trends' ? <TrendsPage /> : equipmentId ? <EquipmentDetailPage assetId={equipmentId} /> : path === '/assets/import' ? <AssetImportPage /> : path === '/assets/repair-center' ? <RepairCenterPage /> : siteId ? <SiteDetailPage siteId={siteId} /> : path === '/assets' || path === '/assets/sites' ? <DashboardPage /> : path === '/lab' ? <LaboratoryHomePage /> : path === '/lab/samples' ? <LaboratoryLedgerPage /> : path === '/lab/identity' ? <IdentityPage /> : path === '/lab/reception' ? <ReceptionPage /> : path === '/lab/workbench' ? <WorkbenchPage /> : path === '/lab/configuration' ? <ConfigurationPage /> : path === '/lab/reports' ? <ReportPage /> : <section className="empty-panel" aria-label="页面内容">
              <div className="empty-symbol" aria-hidden="true">
                {inLab ? "▤" : "▦"}
              </div>
              <h2>
                {current ? "工作区已就绪，业务功能待开放" : "未找到该页面"}
              </h2>
              <p>
                {current
                  ? "目前已建立统一门户。此页面的正式数据与操作将在对应功能上线后提供。"
                  : "你可以返回资产仪表板，或从顶部切换至实验室。"}
              </p>
              {!current && (
                <a className="button" href="/assets">
                  返回资产仪表板
                </a>
              )}
            </section>}
            <footer>
              内部应用 · 中文桌面工作区
              <ConnectionStatus />
            </footer>
          </div>
        </main>
      </div>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider><AuthBoundary permission={current?.permission ?? 'assets.read'}><App /></AuthBoundary></AuthProvider>
  </React.StrictMode>,
);
