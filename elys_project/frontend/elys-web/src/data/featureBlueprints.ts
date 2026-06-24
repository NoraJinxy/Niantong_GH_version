// 「功能蓝图」注册表 —— 把尚未上线（或仅部分上线）的功能，登记成一份可点击的进度说明。
//
// 设计同源于 workbenchPages.ts：数据驱动、单一事实源；通用页面 FeatureBlueprintPage.vue 据此渲染。
// 一个待完成功能 = 一条蓝图，写清三件事：① 这功能要做什么 ② 已经实现了什么 ③ 还差什么。
//
// 无缝替换约定（关键）：
//   功能真正做完时，只改这里——把对应条目的 status 改成 'live' 并填上 liveRoute。
//   入口组件（如 Dashboard 的「快速开始新分析」卡片）会自动从「灰色 → 蓝图页」
//   切换成「正常 → 真功能路由」，无需改任何模板。这就是“无缝替换”。

// planned=规划中（还没动工）；building=开发中（部分已落地）；live=已上线（入口直达真功能）
export type FeatureBlueprintStatus = 'planned' | 'building' | 'live'

export interface FeatureBlueprint {
  /** 路由与查表用的稳定 key，对应 /blueprint/:key */
  key: string
  /** 入口与蓝图页的主标题 */
  title: string
  /** 一行眉题（小标签），点明功能定位 */
  eyebrow: string
  /** AppIcon 图标名 */
  icon: string
  /** 一句话讲清「这是个什么功能」 */
  summary: string
  /** 它最终要帮用户做到的事（面向非工程读者的价值，而非技术细节） */
  intent: string[]
  /** 已经实现、可依赖的底座能力 */
  done: string[]
  /** 还没实现、属于本功能本身的待办 */
  todo: string[]
  /** 进度状态 */
  status: FeatureBlueprintStatus
  /** 功能上线后的真实路由；status==='live' 时入口直接跳这里 */
  liveRoute?: string
}

export const featureBlueprints: Record<string, FeatureBlueprint> = {
  'start-analysis': {
    key: 'start-analysis',
    title: '快速开始新分析',
    eyebrow: '引导式向导 · 上传数据 → 选意图 → 确认参数 → 看结果',
    icon: 'plus',
    summary:
      '一条把“从拿到数据到看见结果”压成几步的引导式向导：你只需要说清“想看什么”，系统替你把分析流程搭好、参数填好，最后直接给出图。',
    intent: [
      '不必先懂节点和参数——选一句“我想看什么”（例如 Target 与 Standard 两种刺激的 ERP 对比），系统据此自动搭好处理流程。',
      '把“上传数据 → 选意图 → 确认参数 → 看结果”做成可逐步确认的向导，而不是一上来就面对一张空白的节点画布。',
      '让医生与研究者第一次用就能跑出一张可用的图，把脑电处理的复杂度藏在后面。',
    ],
    // 已实现的是“向导脚下的底座”——这些能力已经在用，向导只是把它们串成一条捷径。
    done: [
      '数据集上传与管理：FIF / EDF / BDF 导入、版本管理、通道定位（montage）。',
      '研究项与工作流编辑器：拖拽节点搭流程、参数锁定、试跑与正式运行两种模式。',
      '核心分析节点：ERP（事件相关电位）、PSD（功率谱）、TFR（时频）均可计算并产出结果文件。',
      '运行记录与结果预览：时序 / 时频结果可在结果页查看。',
    ],
    // 待实现的是“向导这层薄壳”本身——把上面的底座包成一条无脑可走的路。
    todo: [
      '「选意图」入口：用一句话描述分析目标，映射到具体的分析类型与模板。',
      '由意图自动生成 pipeline（草稿优先，免去面对空表单逐项填写）。',
      '一键编排端点（create-preset）：后端按意图程序化建好流程并预设参数。',
      '向导内「确认参数 → 看结果」的连贯交接：少跳页、少手工选择，一气呵成。',
    ],
    status: 'planned',
    // liveRoute: '/studies',  // 向导做完后填上真实入口，并把 status 改为 'live'
  },
}

export function getFeatureBlueprint(key: string): FeatureBlueprint | undefined {
  return featureBlueprints[key]
}

export function isFeatureLive(key: string): boolean {
  return featureBlueprints[key]?.status === 'live'
}
