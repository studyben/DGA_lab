export const analysisPages = [
  { path: '/assets/analysis/rules', permission: 'analysis.read', title: '健康规则', description: '配置、批准与追溯设备健康评估规则。' },
  {
    path: "/assets/analysis/trends",
    permission: 'analysis.read',
    title: "变压器趋势",
    description: "按物理变压器查看可比较检测结果的变化。",
  },
  {
    path: "/assets/analysis/alarms",
    permission: 'analysis.read',
    title: "报警中心",
    description: "追溯设备报警的来源、确认与解除情况。",
  },
  {
    path: "/assets/analysis/health",
    permission: 'analysis.read',
    title: "健康概览",
    description: "查看设备自身与子设备汇总健康状态。",
  },
] as const;
