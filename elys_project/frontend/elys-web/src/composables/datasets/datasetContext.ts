// 数据集页 · 详情区 tab 子组件的注入上下文（provide / inject）
//
// DatasetsPage 把 5 个 composable 句柄 + 少量页面胶水 provide 出去，各 tab 子组件
// （概览 / 导入 / 采集记录 / 文件索引 / 数据文件 / 技术信息）inject 后按需取用，
// 避免几十个 props 逐层透传。tab 与本页本就强耦合（就是它的标签页），用 provide/inject 合理。
//
// 工程债评审（日志/6_工程债评审260612）：DatasetsPage.vue 模板子组件化批 2 的依赖底座。

import type { ComputedRef, InjectionKey, Ref } from 'vue'
import type { useDatasetCatalog } from './useDatasetCatalog'
import type { useDatasetFiles } from './useDatasetFiles'
import type { useDatasetRecordings } from './useDatasetRecordings'
import type { useDatasetLifecycle } from './useDatasetLifecycle'
import type { useDatasetImportTarget } from './useDatasetImportTarget'

type DatasetWorkbenchTab = 'data' | 'import' | 'share'

export interface DatasetContext {
  catalog: ReturnType<typeof useDatasetCatalog>
  files: ReturnType<typeof useDatasetFiles>
  recordings: ReturnType<typeof useDatasetRecordings>
  lifecycle: ReturnType<typeof useDatasetLifecycle>
  importTarget: ReturnType<typeof useDatasetImportTarget>
  // 页面胶水
  isAdmin: ComputedRef<boolean>
  activeTab: Ref<DatasetWorkbenchTab>
  dataView: Ref<'by-subject' | 'by-type'>
  copyStatus: Ref<string>
  copyTechnicalValue: (value: string, label: string) => Promise<void>
  copyDoi: (doi: string) => Promise<void>
  handleUploaded: () => Promise<void>
}

export const datasetContextKey: InjectionKey<DatasetContext> = Symbol('datasetContext')
