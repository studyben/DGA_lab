export const assetPages = [
  {
    path: "/assets",
    permission: 'assets.read',
    title: "资产仪表板",
    description: "按光伏与储能产品线，查看客户现场和设备规模。",
  },
  {
    path: "/assets/sites",
    permission: 'assets.read',
    title: "客户与现场",
    description: "查看现场基础资料、装机容量与运行设备。",
  },
  {
    path: "/assets/equipment",
    permission: 'assets.read',
    title: "资产台账",
    description: "沿设备层级查看资产身份、子设备与检测历史。",
  },
  {
    path: "/assets/repair-center",
    permission: 'assets.read',
    title: "维修中心",
    description: "查看离场设备的位置与生命周期状态。",
  },
  {
    path: "/assets/import",
    permission: 'assets.import',
    title: "批量导入",
    description: "通过校验和预览发布正式资产资料。",
  },
] as const;
