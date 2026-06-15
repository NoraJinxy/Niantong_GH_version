export interface WorkbenchNavItem {
  key: string
  label: string
  to: string
  icon: string
  status?: 'live' | 'preview'
}

export interface WorkbenchNavGroup {
  title: string
  items: WorkbenchNavItem[]
}

export interface ModuleMetric {
  label: string
  value: string
  hint: string
  tone?: 'primary' | 'accent' | 'success' | 'warning' | 'danger'
}

export interface ModulePanel {
  title: string
  caption?: string
  items: string[]
}

export interface ModulePage {
  key: string
  navKey: string
  icon: string
  title: string
  eyebrow: string
  description: string
  status: string
  visualKind: 'pipeline' | 'wave' | 'heatmap' | 'network' | 'brain' | 'table' | 'figure' | 'ml' | 'admin' | 'gallery'
  metrics: ModuleMetric[]
  workflow: string[]
  panels: ModulePanel[]
  actions?: WorkbenchNavItem[]
}

export const topNavItems: WorkbenchNavItem[] = [
  { key: 'dashboard', label: '工作台', to: '/dashboard', icon: 'dashboard', status: 'live' },
  { key: 'datasets', label: '数据集', to: '/datasets', icon: 'database', status: 'live' },
  { key: 'studies', label: '研究项', to: '/studies', icon: 'studies', status: 'live' },
  { key: 'observe', label: '观察', to: '/observe', icon: 'observe', status: 'preview' },
  { key: 'stats', label: '统计', to: '/statistics', icon: 'stats', status: 'preview' },
  { key: 'figure', label: '作图', to: '/figures', icon: 'figure', status: 'preview' },
  { key: 'ai', label: '机器学习', to: '/ml', icon: 'cpu', status: 'preview' },
]

export const sideNavGroups: WorkbenchNavGroup[] = [
  {
    title: '四对象主线',
    items: [
      { key: 'dashboard', label: '工作台总览', to: '/dashboard', icon: 'dashboard', status: 'live' },
      { key: 'datasets', label: '数据集管理', to: '/datasets', icon: 'database', status: 'live' },
      { key: 'studies', label: '研究项', to: '/studies', icon: 'studies', status: 'live' },
    ],
  },
  {
    title: '预处理与分析预览',
    items: [
      { key: 'ica', label: '独立成分审核', to: '/ica', icon: 'preprocess', status: 'preview' },
      { key: 'statistics', label: '统计分析', to: '/statistics', icon: 'stats', status: 'preview' },
      { key: 'ml', label: '机器学习', to: '/ml', icon: 'cpu', status: 'preview' },
      { key: 'admin', label: '管理面板', to: '/admin', icon: 'admin', status: 'preview' },
    ],
  },
  {
    title: '观察与出图',
    items: [
      { key: 'observe', label: '观察入口', to: '/observe', icon: 'observe', status: 'preview' },
      { key: 'view-erp', label: '事件相关电位', to: '/observe/waveform', icon: 'wave', status: 'preview' },
      { key: 'view-psd', label: '功率谱密度', to: '/observe/psd', icon: 'spectrum', status: 'preview' },
      { key: 'view-tfr', label: '时频分析', to: '/observe/tfr', icon: 'heatmap', status: 'preview' },
      { key: 'view-connectivity', label: '脑网络', to: '/observe/connectivity', icon: 'network', status: 'preview' },
      { key: 'view-microstate', label: '微状态', to: '/observe/microstate', icon: 'brain', status: 'preview' },
      { key: 'view-source', label: '溯源分析', to: '/observe/source', icon: 'source', status: 'preview' },
      { key: 'figures', label: '作图模块', to: '/figures', icon: 'figure', status: 'preview' },
    ],
  },
]

export const modulePages: Record<string, ModulePage> = {
  pipeline: {
    key: 'pipeline',
    navKey: 'pipeline',
    icon: 'pipeline',
    title: '工作流与运行工作台',
    eyebrow: '工作流定义 · 运行记录追踪',
    description: '把数据选择规则、节点参数、运行模式和输出追踪组织为可复用的脑电处理流程。',
    status: '已接入工作流编辑、运行创建、输入快照、Artifact 和 Manifest 基础入口',
    visualKind: 'pipeline',
    metrics: [
      { label: '节点', value: '12', hint: '覆盖 MNE 常用步骤', tone: 'primary' },
      { label: '模板', value: '5', hint: 'ERP / PSD / TFR / 网络 / 微状态', tone: 'accent' },
      { label: '运行模式', value: 'trial / analysis', hint: '区分试跑与正式分析', tone: 'warning' },
      { label: '输出', value: 'Artifact', hint: '结果通过运行记录追溯', tone: 'success' },
    ],
    workflow: ['选择 Study 与数据规则', '拖拽节点生成工作流', '配置参数并锁定版本', '创建运行并追踪结果'],
    panels: [
      { title: '节点库', caption: '导入 · 清洗 · 分析 · 导出', items: ['Load FIF / Raw', 'Band-pass Filter', 'ICA Reject', 'Epoch + Baseline', 'ERP / PSD / TFR', 'Export Report'] },
      { title: '运行前检查', caption: '防止参数和数据状态不一致', items: ['确认采样率一致', '确认通道布局', '检查 bads 标记', '记录算法版本'] },
      { title: '结果管理', caption: '写入 derivatives 与数据库索引', items: ['保存配置快照', '保存任务日志', '保存可视化缩略图', '生成可下载报告'] },
    ],
  },
  preprocess: {
    key: 'preprocess',
    navKey: 'preprocess',
    icon: 'preprocess',
    title: '预处理交互',
    eyebrow: '坏通道 · 坏段 · ICA · 静态预览',
    description: '为研究团队提供可审阅的预处理控制台，人工判断与自动建议同时保留。',
    status: '预处理算法与人工审核记录后续接入',
    visualKind: 'wave',
    metrics: [
      { label: '坏通道', value: '3', hint: 'Fp1 / T7 / P8 待确认', tone: 'danger' },
      { label: 'ICA 成分', value: '20', hint: 'IC03 推荐剔除', tone: 'warning' },
      { label: '保留率', value: '92%', hint: 'Epoch 质量预估', tone: 'success' },
      { label: '审计', value: '可追踪', hint: '人工修改写入日志', tone: 'primary' },
    ],
    workflow: ['查看原始波形与功率谱', '标记坏通道与坏段', '审核 ICA 成分', '保存清洗参数并生成 clean FIF'],
    panels: [
      { title: '坏通道建议', items: ['Fp1 噪声峰值偏高', 'T7 长段平坦', 'P8 高频肌电污染'] },
      { title: 'ICA 审核', items: ['IC03 眼动特征明显', 'IC11 心电相关', 'IC16 边界型，建议人工复核'] },
      { title: '输出文件', items: ['sub-01_task-rest_clean.fif', 'preprocess_report.html', 'bads.tsv / ica.json'] },
    ],
  },
  statistics: {
    key: 'statistics',
    navKey: 'statistics',
    icon: 'stats',
    title: '统计分析',
    eyebrow: '参数检验 · 非参数检验 · 多重比较',
    description: '面向科研出图与论文报告，把条件、组别、ROI、时间窗和频段组织为可复核的统计任务。',
    status: '当前为统计配置和结果报告静态页',
    visualKind: 'table',
    metrics: [
      { label: '检验', value: 't / ANOVA', hint: '支持常见组内组间设计', tone: 'primary' },
      { label: '校正', value: 'FDR', hint: '也规划 cluster permutation', tone: 'accent' },
      { label: '效应量', value: 'Cohen d', hint: '报告中同步展示', tone: 'success' },
      { label: '导出', value: 'CSV / PNG', hint: '适配论文流程', tone: 'warning' },
    ],
    workflow: ['选择分析结果表', '定义条件、组别与 ROI', '选择检验方法和校正策略', '生成统计表与图形标注'],
    panels: [
      { title: '配置项', items: ['Target vs Standard', 'Cz / Pz ROI', '300-500 ms 时间窗', 'FDR q < 0.05'] },
      { title: '报告区', items: ['均值差与置信区间', 'p 值与校正后 p 值', '效应量', '样本量与缺失说明'] },
      { title: '附加分析', items: ['相关分析', '混合线性模型', '置换检验', '批量任务'] },
    ],
  },
  figures: {
    key: 'figures',
    navKey: 'figures',
    icon: 'figure',
    title: '论文出图设计器',
    eyebrow: 'Figure Builder · 静态预览',
    description: '把 ERP、拓扑图、频谱、时频图和统计标注组合为期刊友好的多面板图。',
    status: '当前展示版式与图层模型，导出服务后续接入',
    visualKind: 'figure',
    metrics: [
      { label: '画布', value: '180 mm', hint: '双栏期刊宽度', tone: 'primary' },
      { label: '图层', value: '8', hint: '波形、拓扑、注释、图例', tone: 'accent' },
      { label: '导出', value: 'SVG / PNG', hint: '规划 PDF', tone: 'success' },
      { label: '预设', value: '6', hint: '期刊尺寸与字体', tone: 'warning' },
    ],
    workflow: ['选择分析结果', '拖放多面板布局', '设置字体、色板与统计标注', '批量导出图和图注'],
    panels: [
      { title: '图层', items: ['ERP waveform', 'Topomap 300-500 ms', 'Significance bar', 'Legend + caption'] },
      { title: '期刊预设', items: ['单栏 85 mm', '双栏 180 mm', 'Times New Roman 图内标签', '600 dpi 位图导出'] },
      { title: '质量检查', items: ['颜色可区分', '线宽一致', '显著性标注不遮挡', '图注字段完整'] },
    ],
  },
  ml: {
    key: 'ml',
    navKey: 'ml',
    icon: 'ai',
    title: '机器学习工作台',
    eyebrow: 'Feature · Model · Explainability',
    description: '从脑电特征表出发，配置交叉验证、模型训练、性能评估与可解释性输出。',
    status: 'Phase 3 静态预览，当前不提交真实训练任务',
    visualKind: 'ml',
    metrics: [
      { label: '特征', value: '384', hint: 'PSD / ERP / Network', tone: 'primary' },
      { label: '模型', value: '4', hint: 'SVM / RF / XGBoost / LR', tone: 'accent' },
      { label: 'AUC', value: '0.86', hint: '示例结果', tone: 'success' },
      { label: '验证', value: '5-fold', hint: '分层交叉验证', tone: 'warning' },
    ],
    workflow: ['选择特征表和标签', '配置训练/验证拆分', '选择模型与参数空间', '查看性能和可解释性'],
    panels: [
      { title: '训练配置', items: ['StandardScaler', 'SVM RBF', 'Class weight balanced', 'Nested CV'] },
      { title: '结果输出', items: ['ROC / PR 曲线', '混淆矩阵', '特征重要性', '模型卡片'] },
      { title: '风险控制', items: ['防止数据泄漏', '记录随机种子', '保存版本锁定', '报告类别不平衡'] },
    ],
  },
  admin: {
    key: 'admin',
    navKey: 'admin',
    icon: 'admin',
    title: '管理面板',
    eyebrow: 'Storage · Compute · Users · Audit',
    description: '集中查看部署、存储、计算资源、用户权限和告警阈值。',
    status: '当前为管理页静态预览，不直接改服务器配置',
    visualKind: 'admin',
    metrics: [
      { label: '存储模型', value: 'Dataset / Study', hint: '数据资产与研究输出分区', tone: 'primary' },
      { label: '计算节点', value: '1', hint: 'data server', tone: 'accent' },
      { label: '在线服务', value: '4', hint: 'Nginx / FastAPI / PostgreSQL / Redis', tone: 'success' },
      { label: '告警', value: '2', hint: '容量与队列阈值', tone: 'warning' },
    ],
    workflow: ['检查服务状态', '查看存储与队列', '管理用户和角色', '导出审计日志'],
    panels: [
      { title: '存储设置', items: ['Dataset assets', 'Study artifacts', '运行 manifest'] },
      { title: '计算设置', items: ['FastAPI workers', 'MNE 转换任务', '任务日志保留'] },
      { title: '安全设置', items: ['JWT 登录', '角色权限', 'CORS 白名单', '审计日志'] },
    ],
  },
  observe: {
    key: 'observe',
    navKey: 'observe',
    icon: 'observe',
    title: '观察浏览',
    eyebrow: 'ERP · PSD · TFR · Connectivity · Microstate · Source',
    description: '集中进入六类 EEG 结果观察页面，适合从数据集快速检查到论文前图形探索。',
    status: '观察入口为静态导航，具体计算结果后续由任务系统写入',
    visualKind: 'gallery',
    metrics: [
      { label: '观察类型', value: '6', hint: '覆盖时域到源空间', tone: 'primary' },
      { label: '最近结果', value: '12', hint: '示例列表', tone: 'accent' },
      { label: '通道布局', value: '64 ch', hint: '支持多 montage', tone: 'success' },
      { label: '对比方式', value: '条件 / 组别', hint: '规划联动筛选', tone: 'warning' },
    ],
    workflow: ['选择 Study 与 Run 结果', '进入专用观察页面', '调整条件、ROI 与时间窗', '导出图像或加入 Figure Builder'],
    panels: [
      { title: '推荐入口', items: ['时域 ERP', '频域 PSD', '时频 TFR', '脑网络', '微状态', '溯源观察'] },
      { title: '联动筛选', items: ['Study', 'Dataset', '被试', '任务', '条件', 'Run'] },
      { title: '快速输出', items: ['PNG 快照', 'SVG 图层', '统计标注', '加入论文画布'] },
    ],
    actions: [
      { key: 'view-erp', label: '事件相关电位', to: '/observe/waveform', icon: 'wave', status: 'preview' },
      { key: 'view-psd', label: '功率谱密度', to: '/observe/psd', icon: 'spectrum', status: 'preview' },
      { key: 'view-tfr', label: '时频分析', to: '/observe/tfr', icon: 'heatmap', status: 'preview' },
      { key: 'view-connectivity', label: '脑网络', to: '/observe/connectivity', icon: 'network', status: 'preview' },
      { key: 'view-microstate', label: '微状态', to: '/observe/microstate', icon: 'brain', status: 'preview' },
      { key: 'view-source', label: '溯源', to: '/observe/source', icon: 'source', status: 'preview' },
    ],
  },
  'view-erp': {
    key: 'view-erp',
    navKey: 'view-erp',
    icon: 'wave',
    title: '时域 ERP 观察',
    eyebrow: 'Target vs Standard · Cz/Pz',
    description: '查看条件平均波形、置信区间、时间窗测量和拓扑快照。',
    status: '静态波形预览，未来接入 ERP 结果文件',
    visualKind: 'wave',
    metrics: [
      { label: '时间窗', value: '300-500 ms', hint: 'P300 主窗口', tone: 'primary' },
      { label: '条件', value: '2', hint: 'target / standard', tone: 'accent' },
      { label: '峰值差', value: '3.4 uV', hint: '示例统计', tone: 'success' },
      { label: '通道', value: 'Cz / Pz', hint: 'ROI 可切换', tone: 'warning' },
    ],
    workflow: ['选择通道或 ROI', '切换条件和组别', '调整测量时间窗', '导出波形和统计表'],
    panels: [
      { title: '测量', items: ['峰值潜伏期', '平均振幅', '面积积分', '置信区间'] },
      { title: '显示', items: ['单被试叠加', 'Grand average', '拓扑图联动', '显著性阴影'] },
      { title: '导出', items: ['ERP 曲线 PNG', '测量表 CSV', 'Figure Builder 图层'] },
    ],
  },
  'view-psd': {
    key: 'view-psd',
    navKey: 'view-psd',
    icon: 'spectrum',
    title: '频域 PSD 观察',
    eyebrow: 'Welch PSD · Alpha / Beta',
    description: '比较频段功率、通道谱线、地形图和组间差异。',
    status: '静态频谱预览，未来接入 PSD 任务结果',
    visualKind: 'wave',
    metrics: [
      { label: '频段', value: '1-45 Hz', hint: '示例展示', tone: 'primary' },
      { label: 'Alpha', value: '+18%', hint: '闭眼条件示例', tone: 'success' },
      { label: 'Beta', value: '-7%', hint: '运动想象示例', tone: 'warning' },
      { label: '方法', value: 'Welch', hint: 'MNE psd_array_welch', tone: 'accent' },
    ],
    workflow: ['选择数据和通道', '设定频段与窗长', '查看谱线和拓扑图', '导出频段功率表'],
    panels: [
      { title: '频段配置', items: ['Delta 1-4 Hz', 'Theta 4-8 Hz', 'Alpha 8-13 Hz', 'Beta 13-30 Hz'] },
      { title: '质量检查', items: ['工频噪声', '肌电高频污染', '通道异常峰', '组内离群值'] },
      { title: '输出', items: ['band_power.tsv', 'psd_topomap.png', 'condition_diff.csv'] },
    ],
  },
  'view-tfr': {
    key: 'view-tfr',
    navKey: 'view-tfr',
    icon: 'heatmap',
    title: '时频分析',
    eyebrow: 'Cz · ERSP · RdBu',
    description: '查看事件相关同步/去同步，按时间、频率、条件和通道联动探索。',
    status: '静态热图预览，未来接入 TFR 计算结果',
    visualKind: 'heatmap',
    metrics: [
      { label: '频率', value: '4-40 Hz', hint: 'Morlet 示例', tone: 'primary' },
      { label: '时间', value: '-500~1000 ms', hint: '事件锁定', tone: 'accent' },
      { label: 'Baseline', value: '-300~-100 ms', hint: 'dB 转换', tone: 'success' },
      { label: '显著区', value: '2', hint: '示例 cluster', tone: 'warning' },
    ],
    workflow: ['选择事件和通道', '配置小波或 multitaper', '查看时频图和拓扑切片', '导出 cluster 与图像'],
    panels: [
      { title: '参数', items: ['Morlet cycles 3-7', 'dB baseline', 'Cz / C3 / C4', 'Target minus Rest'] },
      { title: '交互', items: ['鼠标选区', '频段平均', '时间切片拓扑', '条件差异'] },
      { title: '导出', items: ['TFR heatmap', 'cluster mask', 'frequency band table'] },
    ],
  },
  'view-connectivity': {
    key: 'view-connectivity',
    navKey: 'view-connectivity',
    icon: 'network',
    title: '脑网络观察',
    eyebrow: 'Connectivity · Graph Metrics',
    description: '展示通道或 ROI 间连接强度、网络边、节点指标和条件差异。',
    status: '静态网络预览，未来接入连接性计算结果',
    visualKind: 'network',
    metrics: [
      { label: '节点', value: '32', hint: 'ROI 级网络', tone: 'primary' },
      { label: '边', value: '128', hint: '阈值后保留', tone: 'accent' },
      { label: '指标', value: '4', hint: 'degree / clustering / efficiency', tone: 'success' },
      { label: '频段', value: 'Alpha', hint: '8-13 Hz', tone: 'warning' },
    ],
    workflow: ['选择频段和连接指标', '设定阈值策略', '查看网络和矩阵', '导出图指标表'],
    panels: [
      { title: '连接指标', items: ['PLI', 'wPLI', 'Coherence', 'Envelope correlation'] },
      { title: '图指标', items: ['Degree', 'Clustering', 'Global efficiency', 'Betweenness'] },
      { title: '风险提示', items: ['体积传导控制', '阈值敏感性', '多重比较校正'] },
    ],
  },
  'view-microstate': {
    key: 'view-microstate',
    navKey: 'view-microstate',
    icon: 'brain',
    title: '微状态观察',
    eyebrow: 'Microstate A/B/C/D',
    description: '查看微状态拓扑、持续时间、出现率、覆盖率和状态转移矩阵。',
    status: '静态微状态预览，未来接入聚类与拟合结果',
    visualKind: 'brain',
    metrics: [
      { label: '状态', value: '4', hint: 'A/B/C/D', tone: 'primary' },
      { label: 'GEV', value: '78%', hint: '解释方差示例', tone: 'success' },
      { label: '平均时长', value: '82 ms', hint: '全状态均值', tone: 'accent' },
      { label: '转移', value: '矩阵', hint: 'Markov 风格展示', tone: 'warning' },
    ],
    workflow: ['选择清洗后数据', '运行聚类或加载模板', '查看状态序列与统计', '比较组间微状态指标'],
    panels: [
      { title: '指标', items: ['Mean duration', 'Occurrence', 'Coverage', 'GEV'] },
      { title: '拓扑', items: ['MS-A', 'MS-B', 'MS-C', 'MS-D'] },
      { title: '输出', items: ['microstate_stats.tsv', 'transition_matrix.csv', 'topomap.png'] },
    ],
  },
  'view-source': {
    key: 'view-source',
    navKey: 'view-source',
    icon: 'source',
    title: '溯源观察',
    eyebrow: 'Source Localization · 静态预览',
    description: '展示源空间激活、皮层视图、时间窗差异和 ROI 摘要。',
    status: '源定位需要 MRI/BEM/forward model，当前为静态展示',
    visualKind: 'brain',
    metrics: [
      { label: '方法', value: 'sLORETA', hint: '示例设置', tone: 'primary' },
      { label: '时间窗', value: '320-430 ms', hint: 'P300 峰区', tone: 'accent' },
      { label: 'ROI', value: '6', hint: '显著激活区示例', tone: 'success' },
      { label: '模型', value: 'fsaverage', hint: '规划支持个体 MRI', tone: 'warning' },
    ],
    workflow: ['选择 forward / inverse 解', '设定时间窗和条件差', '查看皮层激活', '导出 ROI 表和截图'],
    panels: [
      { title: '输入', items: ['bem.fif', 'trans.fif', 'forward.fif', 'evoked.fif'] },
      { title: '显示', items: ['左/右半球', 'Inflated surface', 'Hot colormap', 'ROI 标签'] },
      { title: '注意', items: ['源定位依赖头模型质量', '需要记录坐标系', '结果应与传感器空间交叉验证'] },
    ],
  },
}

export function getModulePage(key: string): ModulePage {
  return modulePages[key] || modulePages.observe
}

export function isWorkbenchNavPreview(item: WorkbenchNavItem): boolean {
  return item.status === 'preview'
}
