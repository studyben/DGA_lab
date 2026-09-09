import React from "react";
import { createRoot } from "react-dom/client";
import { assetPages } from "./features/assets/pages";
import { laboratoryPages } from "./features/laboratory/pages";
import { analysisPages } from "./features/condition-analysis/pages";
import "./styles.css";
import { ConnectionStatus } from "./ConnectionStatus";

const path =
  window.location.pathname === "/"
    ? "/assets"
    : window.location.pathname.replace(/\/$/, "");
const allPages = [...assetPages, ...laboratoryPages, ...analysisPages];
const current = allPages.find((page) => page.path === path);
const inLab = path === "/lab" || path.startsWith("/lab/");
const workspace = inLab ? "DGA 实验室" : "资产管理与仪表板";

function App() {
  return (
    <>
      <a className="skip" href="#main">
        跳到主要内容
      </a>
      <header>
        <a href="/" className="brand">
          <span className="brand-mark">D</span>
          <span>
            DGA <strong>Lab</strong>
            <small>资产与油样管理</small>
          </span>
        </a>
        <nav aria-label="工作区" className="workspaces">
          <a href="/assets" aria-current={!inLab ? "page" : undefined}>
            资产管理与仪表板
          </a>
          <a href="/lab" aria-current={inLab ? "page" : undefined}>
            DGA 实验室
          </a>
        </nav>
        <span className="environment">开发预览</span>
      </header>
      <div className="shell">
        <aside>
          <p className="nav-caption">{inLab ? "实验室工作区" : "资产工作区"}</p>
          <nav aria-label="当前工作区页面">
            {(inLab ? laboratoryPages : assetPages).map((page, index) => (
              <a
                key={page.path}
                href={page.path}
                aria-current={path === page.path ? "page" : undefined}
              >
                <span aria-hidden="true" className="nav-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {page.title}
              </a>
            ))}
            {!inLab && (
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
              <span className="outline-badge">工程基础阶段</span>
            </div>
            <section className="empty-panel" aria-label="页面内容">
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
            </section>
            <section className="overview" aria-label="工作区说明">
              <article>
                <span className="step">01 / 资产身份</span>
                <h2>从现场到设备</h2>
                <p>以正式资产记录为基础，保留清晰的设备层级与历史关系。</p>
              </article>
              <article>
                <span className="step">02 / 油样检测</span>
                <h2>从收样到报告</h2>
                <p>通过油样条码连接采样信息、检测记录和报告结果。</p>
              </article>
              <article>
                <span className="step">03 / 状态分析</span>
                <h2>从结果到趋势</h2>
                <p>围绕同一台物理变压器，追踪可比较的检测结果。</p>
              </article>
            </section>
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
    <App />
  </React.StrictMode>,
);
