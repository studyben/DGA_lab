export const laboratoryPages = [
  {
    path: "/lab",
    permission: 'laboratory.read',
    title: "实验室首页",
    description: "从收样到报告，在一个工作区内完成油样检测。",
  },
  {
    path: "/lab/reception",
    permission: 'laboratory.write',
    title: "收样登记",
    description: "关联正式资产，记录采样信息并生成油样条码。",
  },
  {
    path: "/lab/identity",
    permission: 'laboratory.write',
    title: "身份待确认",
    description: "核实待绑定油样的设备身份。",
  },
  {
    path: "/lab/samples",
    permission: 'laboratory.read',
    title: "油样台账",
    description: "按油样编号、现场与检测状态查找记录。",
  },
  {
    path: "/lab/workbench",
    permission: 'laboratory.write',
    title: "检测工作台",
    description: "通过条码进入油样，管理检测数据和整体检测定稿。",
  },
  {
    path: "/lab/reports",
    permission: 'laboratory.read',
    title: "报告中心",
    description: "按油样条码查找整体检测定稿后的中文报告。",
  },
] as const;
