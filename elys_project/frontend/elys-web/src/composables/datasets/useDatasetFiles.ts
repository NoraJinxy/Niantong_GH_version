// 数据集页 · working 文件索引 + 数据文件分桶
//
// 从 DatasetsPage.vue 抽出：所选数据集 working 版本的文件列表、搜索 / 角色筛选 / 分页，
// 以及"你上传的原始 / 标准 FIF / 技术文件"两桶汇总（数据文件视图用）。
// 依赖 catalog 的 selectedDatasetAssetId（经 options 注入）。重置分页的
// watch([fileSearch, fileRoleFilter]) 仍留在页面（与其他跨簇 watch 同处编排）。
//
// 工程债评审（日志/6_工程债评审260612「工程债评审与重构路线」§2.2 前端上帝组件）：
// DatasetsPage.vue 拆分批 3。

import { computed, ref, type Ref } from 'vue'
import { datasetAssetApi } from '@/api/datasetAssets'
import type { DatasetFile } from '@/types'
import {
  type DatasetFileRoleFilter,
  countFilesByRole,
  fileBucketOf,
  getFileDisplayPath,
  getFileRoleLabel,
  getFileShortPath,
  matchesFileRoleFilter,
} from './datasetsFormatters'

export const FILE_INDEX_PAGE_SIZE = 30

interface DatasetFilesOptions {
  selectedDatasetAssetId: Ref<string>
}

export function useDatasetFiles(options: DatasetFilesOptions) {
  const { selectedDatasetAssetId } = options

  const selectedAssetFiles = ref<DatasetFile[]>([])
  const isLoadingAssetFiles = ref(false)
  const selectedAssetFilesError = ref('')
  const fileSearch = ref('')
  const fileRoleFilter = ref<DatasetFileRoleFilter>('all')
  const fileDisplayLimit = ref(FILE_INDEX_PAGE_SIZE)

  const selectedAssetFileStats = computed(() => {
    const files = selectedAssetFiles.value
    return {
      total: files.length,
      original: countFilesByRole(files, ['original', 'upload', 'source']),
      // 两层重构：raw_bids 角色已下线（降纯逻辑），原「BIDS 逻辑视图」统计退役。canonicalFif 仍按 'fif' 子串匹配新角色。
      canonicalFif: countFilesByRole(files, ['canonical', 'fif']),
      totalSize: files.reduce((sum, file) => sum + (file.file_size || 0), 0),
    }
  })

  // 资产级 2 桶（用于顶部汇总卡 + 按类型视图）
  const assetBuckets = computed(() => {
    const buckets = {
      upload: { count: 0, size: 0, files: [] as DatasetFile[] },
      fif: { count: 0, size: 0, files: [] as DatasetFile[] },
      tech: { count: 0, size: 0, files: [] as DatasetFile[] },
    }
    for (const file of selectedAssetFiles.value) {
      const bucket = buckets[fileBucketOf(file)]
      bucket.files.push(file)
      bucket.count += 1
      bucket.size += file.file_size || 0
    }
    return buckets
  })

  const filteredAssetFiles = computed(() => {
    const keyword = fileSearch.value.trim().toLowerCase()
    return selectedAssetFiles.value.filter((file) => {
      if (!matchesFileRoleFilter(file, fileRoleFilter.value)) return false
      if (!keyword) return true
      return [
        getFileShortPath(file),
        getFileDisplayPath(file),
        getFileRoleLabel(file.file_role),
        file.file_role,
        file.sha256 || '',
      ].some((text) => text.toLowerCase().includes(keyword))
    })
  })

  const visibleAssetFiles = computed(() => filteredAssetFiles.value.slice(0, fileDisplayLimit.value))
  const hiddenAssetFileCount = computed(() => Math.max(0, filteredAssetFiles.value.length - visibleAssetFiles.value.length))

  async function loadSelectedAssetFiles() {
    const assetId = selectedDatasetAssetId.value
    selectedAssetFilesError.value = ''
    selectedAssetFiles.value = []
    fileDisplayLimit.value = FILE_INDEX_PAGE_SIZE
    if (!assetId) return
    isLoadingAssetFiles.value = true
    try {
      const res = await datasetAssetApi.listFiles(assetId, { version_label: 'working' })
      selectedAssetFiles.value = res.data.files
    } catch {
      selectedAssetFilesError.value = '文件索引读取失败，请确认该数据集是否已完成导入或稍后重试。'
    } finally {
      isLoadingAssetFiles.value = false
    }
  }

  function resetFileIndexView(clearFilters = false) {
    fileDisplayLimit.value = FILE_INDEX_PAGE_SIZE
    if (!clearFilters) return
    fileSearch.value = ''
    fileRoleFilter.value = 'all'
  }

  function showMoreAssetFiles() {
    fileDisplayLimit.value += FILE_INDEX_PAGE_SIZE
  }

  return {
    selectedAssetFiles,
    isLoadingAssetFiles,
    selectedAssetFilesError,
    fileSearch,
    fileRoleFilter,
    fileDisplayLimit,
    selectedAssetFileStats,
    assetBuckets,
    filteredAssetFiles,
    visibleAssetFiles,
    hiddenAssetFileCount,
    loadSelectedAssetFiles,
    resetFileIndexView,
    showMoreAssetFiles,
  }
}
