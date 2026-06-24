// 数据集页 · 目录主轴（catalog）
//
// 从 DatasetsPage.vue 抽出的"数据集资产列表 + 选中 + 搜索 / 筛选"核心状态，是其他
// composable（版本 / 文件 / 记录 / 导入目标）的依赖底座：selectedDatasetAsset 与
// selectedDatasetAssetId 被它们读取；loadDatasetAssets 在各处提交后被调用以刷新列表。
// 自包含：仅依赖 datasetAssetApi 与 getDateValue，无需 options 注入。
//
// 工程债评审（日志/6_工程债评审260612「工程债评审与重构路线」§2.2 前端上帝组件）：
// DatasetsPage.vue 拆分批 2。

import { computed, ref } from 'vue'
import { datasetAssetApi } from '@/api/datasetAssets'
import type { DatasetAsset } from '@/types'
import { getDateValue } from './datasetsFormatters'

export function useDatasetCatalog() {
  const datasetAssets = ref<DatasetAsset[]>([])
  const selectedDatasetAssetId = ref('')
  const assetSearch = ref('')
  const assetVisibilityFilter = ref<'all' | 'private' | 'shared' | 'public'>('all')
  const isLoadingAssets = ref(false)

  const selectedDatasetAsset = computed(() =>
    datasetAssets.value.find((asset) => asset.id === selectedDatasetAssetId.value) || null,
  )

  const filteredDatasetAssets = computed(() => {
    const keyword = assetSearch.value.trim().toLowerCase()
    return datasetAssets.value
      .filter((asset) => {
        if (assetVisibilityFilter.value !== 'all' && asset.visibility !== assetVisibilityFilter.value) return false
        if (!keyword) return true
        return [asset.name, asset.code, asset.description || '']
          .some((text) => text.toLowerCase().includes(keyword))
      })
      .sort((a, b) => getDateValue(b.updated_at || b.created_at) - getDateValue(a.updated_at || a.created_at))
  })

  const assetStats = computed(() => ({
    total: datasetAssets.value.length,
    private: datasetAssets.value.filter((asset) => asset.visibility === 'private').length,
    shared: datasetAssets.value.filter((asset) => asset.visibility === 'shared').length,
    public: datasetAssets.value.filter((asset) => asset.visibility === 'public').length,
  }))

  function sortedAssets(assets: DatasetAsset[]) {
    return [...assets].sort((a, b) => getDateValue(b.updated_at || b.created_at) - getDateValue(a.updated_at || a.created_at))
  }

  async function loadDatasetAssets() {
    isLoadingAssets.value = true
    try {
      const res = await datasetAssetApi.list()
      datasetAssets.value = res.data.assets
      if (!selectedDatasetAssetId.value && datasetAssets.value.length) {
        selectedDatasetAssetId.value = sortedAssets(datasetAssets.value)[0].id
      } else if (selectedDatasetAssetId.value && !datasetAssets.value.some((asset) => asset.id === selectedDatasetAssetId.value)) {
        selectedDatasetAssetId.value = datasetAssets.value.length ? sortedAssets(datasetAssets.value)[0].id : ''
      }
    } catch {
      datasetAssets.value = []
    } finally {
      isLoadingAssets.value = false
    }
  }

  return {
    datasetAssets,
    selectedDatasetAssetId,
    assetSearch,
    assetVisibilityFilter,
    isLoadingAssets,
    selectedDatasetAsset,
    filteredDatasetAssets,
    assetStats,
    sortedAssets,
    loadDatasetAssets,
  }
}
