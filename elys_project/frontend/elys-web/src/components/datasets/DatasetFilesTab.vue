<template>
          <section class="dataset-tab-panel" aria-label="文件索引">
            <div class="dataset-file-panel">
              <div class="dataset-panel-head">
                <div>
                  <h3>working 文件索引</h3>
                  <p>按需查看逻辑路径和文件角色；服务器绝对路径不会在这里展示。</p>
                </div>
                <button class="btn btn--sm" type="button" :disabled="isLoadingAssetFiles" @click="loadSelectedAssetFiles">
                  <AppIcon name="restore" :size="14" />
                  刷新
                </button>
              </div>

              <div class="dataset-file-stats">
                <div>
                  <span>文件总数</span>
                  <strong>{{ selectedAssetFileStats.total }}</strong>
                </div>
                <div>
                  <span>原始上传</span>
                  <strong>{{ selectedAssetFileStats.original }}</strong>
                </div>
                <div>
                  <span>标准 FIF</span>
                  <strong>{{ selectedAssetFileStats.canonicalFif }}</strong>
                </div>
                <div>
                  <span>体量</span>
                  <strong>{{ formatFileSize(selectedAssetFileStats.totalSize) }}</strong>
                </div>
              </div>

              <div v-if="selectedAssetFiles.length" class="dataset-file-toolbar">
                <label class="dataset-file-search">
                  <span>关键词</span>
                  <div>
                    <AppIcon name="search" :size="14" />
                    <input
                      v-model.trim="fileSearch"
                      class="input"
                      type="search"
                      placeholder="搜索短路径、logical_path 或校验值"
                    />
                  </div>
                </label>
                <label class="dataset-file-filter">
                  <span>文件角色</span>
                  <select v-model="fileRoleFilter" class="select">
                    <option v-for="option in fileRoleOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <div class="dataset-file-counter">
                  <span>当前结果</span>
                  <strong>{{ filteredAssetFiles.length }}</strong>
                </div>
              </div>

              <div v-if="isLoadingAssetFiles" class="dataset-list-empty">正在读取文件索引...</div>
              <div v-else-if="selectedAssetFilesError" class="inline-error">{{ selectedAssetFilesError }}</div>
              <div v-else-if="!selectedAssetFiles.length" class="dataset-list-empty">
                还没有写入文件索引。准备导入目标后，可以在导入页选择数据上传。
              </div>
              <div v-else-if="!filteredAssetFiles.length" class="dataset-list-empty">
                没有符合当前筛选条件的文件。
              </div>
              <div v-else class="dataset-file-list">
                <details v-for="file in visibleAssetFiles" :key="file.id" class="dataset-file-row">
                  <summary>
                    <span class="dataset-file-name">{{ getFileShortPath(file) }}</span>
                    <span class="dataset-file-meta">
                      <strong>{{ getFileRoleLabel(file.file_role) }}</strong>
                      <small>{{ formatFileSize(file.file_size || 0) }}</small>
                    </span>
                  </summary>
                  <div class="dataset-file-detail">
                    <div>
                      <span>完整 logical_path</span>
                      <strong>{{ getFileFullLogicalPath(file) }}</strong>
                    </div>
                    <div>
                      <span>relative_path</span>
                      <strong>{{ getFileRelativePath(file) }}</strong>
                    </div>
                    <div>
                      <span>文件角色</span>
                      <strong>{{ getFileRoleLabel(file.file_role) }}</strong>
                    </div>
                    <div>
                      <span>体量</span>
                      <strong>{{ formatFileSize(file.file_size || 0) }}</strong>
                    </div>
                    <div>
                      <span>sha256</span>
                      <strong>{{ file.sha256 || '未返回' }}</strong>
                    </div>
                    <div>
                      <span>写入时间</span>
                      <strong>{{ formatDate(file.created_at) }}</strong>
                    </div>
                  </div>
                </details>
              </div>

              <div v-if="filteredAssetFiles.length" class="dataset-file-more">
                <span>
                  已显示 {{ visibleAssetFiles.length }} / {{ filteredAssetFiles.length }} 个文件
                </span>
                <button
                  v-if="hiddenAssetFileCount"
                  class="btn btn--sm"
                  type="button"
                  @click="showMoreAssetFiles"
                >
                  显示更多 {{ Math.min(FILE_INDEX_PAGE_SIZE, hiddenAssetFileCount) }} 个
                </button>
              </div>
            </div>
          </section>

</template>

<script setup lang="ts">
// 数据集详情「文件索引」tab。状态经 datasetContext inject。
import { inject } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import { FILE_INDEX_PAGE_SIZE } from '@/composables/datasets/useDatasetFiles'
import { type DatasetFileRoleFilter, formatDate, formatFileSize, getFileShortPath, getFileRoleLabel, getFileFullLogicalPath, getFileRelativePath } from '@/composables/datasets/datasetsFormatters'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
const ctx = inject(datasetContextKey)!
const {
  selectedAssetFiles, isLoadingAssetFiles, selectedAssetFilesError, fileSearch, fileRoleFilter,
  selectedAssetFileStats, filteredAssetFiles, visibleAssetFiles, hiddenAssetFileCount,
  loadSelectedAssetFiles, showMoreAssetFiles,
} = ctx.files
const fileRoleOptions: Array<{ value: DatasetFileRoleFilter; label: string }> = [
  { value: 'all', label: '全部角色' },
  { value: 'original', label: '原始上传' },
  { value: 'raw-bids', label: 'BIDS 逻辑视图' },
  { value: 'canonical-fif', label: '标准 FIF' },
  { value: 'other', label: '其他' },
]
</script>
