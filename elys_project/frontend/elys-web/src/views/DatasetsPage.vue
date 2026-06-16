<template>
  <!-- 版心对齐主页 .hero__inner(1200)：与 Dashboard 同款覆盖，--content-w=1200 + --page-pad-x=0，内容与主页齐边。仅本页生效。 -->
  <WorkbenchShell active-key="datasets" active-top-key="datasets" :show-sidebar="false" :narrow="true" :style="{ '--content-w': '1200px', '--page-pad-x': '0px' }">
    <div class="page__header dataset-page__header">
      <div>
        <h1 class="page__title">数据集管理</h1>
        <p class="page__subtitle">
          上传并管理你的 EEG 数据，按被试查看每条记录的状态，再进入后续分析。
        </p>
      </div>
      <div class="dataset-page__actions">
        <!-- Phase 3 (docs_v2/3-25): 管理员审核入口 -->
        <RouterLink
          v-if="isAdmin && pendingWithdrawals > 0"
          class="btn btn--ghost admin-link"
          to="/admin/withdrawals"
          title="审核数据集负责人提交的撤回申请"
        >
          <AppIcon name="alert" :size="15" />
          撤回审核 ({{ pendingWithdrawals }})
        </RouterLink>
        <RouterLink
          v-if="isAdmin && pendingPublicizations > 0"
          class="btn btn--ghost admin-link"
          to="/admin/publicizations"
          title="审核数据集负责人提交的转公开申请（shared → public）"
        >
          <AppIcon name="observe" :size="15" />
          转公开审核 ({{ pendingPublicizations }})
        </RouterLink>
        <button class="btn btn--primary" type="button" @click="openCreatePanel">
          <AppIcon name="plus" :size="15" />
          新建数据集
        </button>
      </div>
    </div>

    <!-- #15：页面级成功提示（在详情面板之外，删除后选中清空、面板卸载仍可见） -->
    <div v-if="pageNotice" class="inline-success" role="status" style="margin-bottom: 16px;">{{ pageNotice }}</div>

    <section v-if="usesShortcutStudy" class="dataset-shortcut">
      <AppIcon name="studies" :size="18" />
      <div>
        <strong>当前处于研究项快捷入口</strong>
        <span>上传目标会关联到 {{ shortcutStudyLabel }}；普通入口会自动生成研究项。</span>
      </div>
    </section>

    <section class="dataset-workbench">
      <aside class="dataset-catalog" aria-label="数据集目录">
        <div class="dataset-catalog__head">
          <div>
            <h2>数据集</h2>
            <p>{{ assetSearch || assetVisibilityFilter !== 'all' ? `匹配 ${filteredDatasetAssets.length} / 共 ${datasetAssets.length}` : `${datasetAssets.length} 个数据集` }}</p>
          </div>
          <button class="icon-btn" type="button" title="刷新" @click="reloadAll">
            <AppIcon name="restore" :size="15" />
          </button>
        </div>

        <div v-if="datasetAssets.length > 1" class="dataset-catalog__filters">
          <label class="dataset-search">
            <AppIcon name="search" :size="15" />
            <input v-model.trim="assetSearch" type="search" placeholder="搜索数据集名称" />
          </label>
          <select v-model="assetVisibilityFilter" class="input">
            <option value="all">全部可见范围</option>
            <option value="private">私有</option>
            <option value="shared">共享</option>
            <option value="public">公开</option>
          </select>
        </div>

        <EmptyState v-if="isLoadingAssets" description="正在读取数据集…" compact />
        <EmptyState
          v-else-if="!datasetAssets.length"
          title="还没有数据集"
          description="请先新建一个数据集，然后导入 EEG 原始数据。"
          compact
        />
        <EmptyState v-else-if="!filteredDatasetAssets.length" description="没有匹配的数据集。" compact />
        <div v-else class="dataset-list">
          <button
            v-for="asset in filteredDatasetAssets"
            :key="asset.id"
            class="dataset-row"
            :class="{ 'is-active': activePanel !== 'create' && asset.id === selectedDatasetAssetId }"
            type="button"
            @click="selectDatasetAsset(asset.id)"
          >
            <div class="dataset-row__top">
              <IconLine class="dataset-row__emoji" name="folder" :size="16" />
              <strong>{{ asset.name }}</strong>
              <span class="badge" :class="getVisibilityClass(asset.visibility)">
                {{ getVisibilityLabel(asset.visibility) }}
              </span>
            </div>
            <!-- 6-05：数据概要四件套 被试/记录数/任务/时长 -->
            <div v-if="(asset.subject_count ?? 0) > 0 || (asset.recording_count ?? 0) > 0 || (asset.task_codes ?? []).length" class="dataset-row__summary">
              <span v-if="(asset.subject_count ?? 0) > 0"><IconLine name="users" :size="14" /> {{ asset.subject_count }} 名被试</span>
              <span v-if="(asset.recording_count ?? 0) > 0"><IconLine name="list" :size="14" /> {{ asset.recording_count }} 条记录</span>
              <span v-if="(asset.task_codes ?? []).length"><IconLine name="clipboard" :size="14" /> {{ (asset.task_codes ?? []).length }} 种任务</span>
              <span v-if="(asset.total_duration_seconds ?? 0) > 0" title="全部采集记录的总时长"><IconLine name="clock" :size="14" /> 共 {{ formatDuration(asset.total_duration_seconds ?? 0) }}</span>
            </div>
            <div class="dataset-row__meta">
              <span>创建于 {{ formatRelative(asset.created_at) }}</span>
            </div>
          </button>
        </div>
      </aside>

      <section
        class="dataset-detail"
        :class="{ 'dataset-detail--create': activePanel === 'create' }"
        aria-label="数据集工作台"
      >
        <div class="dataset-detail__head">
          <div>
            <span class="section-kicker">{{ activePanel === 'create' ? '新建数据集' : '数据集工作台' }}</span>
            <h2>{{ activePanel === 'create' ? '创建新的数据集' : (selectedDatasetAsset?.name || '数据集工作台') }}</h2>
            <p v-if="activePanel === 'create'" class="dataset-detail__subtitle">
              这是新的数据集，不会修改左侧目录中的已有数据集。
            </p>
          </div>
          <div class="dataset-detail__actions">
            <!-- 6-05：去掉与页头重复的"新建数据集"主按钮，仅保留创建模式下的返回入口 -->
            <button
              v-if="activePanel === 'create'"
              class="btn btn--sm"
              type="button"
              :disabled="!selectedDatasetAsset"
              @click="returnToDatasetWorkbench"
            >
              返回当前数据集
            </button>
            <!-- 发布与共享：高级入口。不与日常的「数据文件 / 上传」并列，仅在需要对外发布 / 授权时进入。 -->
            <button
              v-else-if="selectedDatasetAsset"
              class="btn btn--sm btn--ghost"
              :class="{ 'is-active': activeTab === 'share' }"
              type="button"
              title="数据集的版本发布、对外可见范围与授权成员（高级）"
              @click="activeTab = activeTab === 'share' ? 'data' : 'share'"
            >
              <AppIcon name="network" :size="14" />
              发布与共享
            </button>
          </div>
        </div>

        <form v-if="activePanel === 'create'" class="dataset-create-form" @submit.prevent="bootstrapDataset">
          <div class="dataset-create-intro">
            <div>
              <span class="section-kicker">创建流程</span>
              <h3>定义数据集后直接导入</h3>
              <p>创建完成后自动准备研究项，上传区会切到新数据集。</p>
            </div>
            <div class="dataset-create-steps" aria-label="创建步骤">
              <span>定义</span>
              <span>准备</span>
              <span>导入</span>
            </div>
          </div>

          <div class="dataset-form-grid dataset-form-grid--create">
            <label class="field">
              <span class="field__label">数据集名称</span>
              <input
                v-model.trim="datasetName"
                class="input"
                placeholder="例如：Resting EEG Dataset"
                @input="clearBootstrapResult"
              />
            </label>
            <label class="field">
              <span class="field__label">数据集 code</span>
              <input
                v-model.trim="datasetCode"
                class="input"
                placeholder="rest-eeg"
                @input="clearBootstrapResult"
              />
            </label>
            <label class="field field--wide">
              <span class="field__label">数据集描述</span>
              <textarea
                v-model.trim="datasetDescription"
                class="textarea"
                rows="3"
                placeholder="可填写采集设备、范式、来源、伦理说明或数据边界"
                @input="clearBootstrapResult"
              ></textarea>
            </label>
            <details class="dataset-advanced-settings">
              <summary>高级设置</summary>
              <label class="field">
                <span class="field__label">关联名称</span>
                <input
                  v-model.trim="mountName"
                  class="input"
                  placeholder="primary"
                  @input="clearBootstrapResult"
                />
                <span class="field__hint">默认 primary；仅在同一研究项关联多个数据集时需要调整。</span>
              </label>
            </details>
          </div>

          <div v-if="bootstrapError" class="inline-error">{{ bootstrapError }}</div>
          <div v-if="bootstrapSuccess" class="inline-success">{{ bootstrapSuccess }}</div>

          <div class="dataset-action-bar">
            <span>创建后自动准备导入目标，并上传到当前未发布版本。</span>
            <button class="btn btn--primary" type="submit" :disabled="isBootstrapping || !canCreateDataset">
              <span v-if="isBootstrapping" class="spinner"></span>
              {{ isBootstrapping ? '正在准备...' : '创建并准备导入' }}
            </button>
          </div>
        </form>

        <div v-else-if="selectedDatasetAsset" class="dataset-detail__body">
          <div class="dataset-tabs" role="tablist" aria-label="数据集工作台视图">
            <button
              v-for="tab in datasetTabs"
              :key="tab.key"
              class="dataset-tab"
              :class="{ 'is-active': activeTab === tab.key }"
              type="button"
              role="tab"
              :aria-selected="activeTab === tab.key"
              @click="activeTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>

          <DatasetMaintenanceTab v-if="activeTab === 'data'" />

          <DatasetImportTab v-else-if="activeTab === 'import'" />

          <DatasetShareTab v-else-if="activeTab === 'share'" />
        </div>

        <EmptyState v-else icon="database" title="请选择一个数据集，或新建数据集。" />
      </section>
    </section>

    <DatasetLifecycleModals
      :publish-modal="publishModal"
      :withdraw-modal="withdrawModal"
      :emergency-modal="emergencyModal"
      :visibility-modal="visibilityModal"
      :delete-asset-modal="deleteAssetModal"
      :discard-version-modal="discardVersionModal"
      :publish-target-label="publishTargetLabel"
      :can-submit-publish="canSubmitPublish"
      :selected-dataset-asset="selectedDatasetAsset"
      :current-version="currentVersion"
      :close-publish-modal="closePublishModal"
      :submit-publish="submitPublish"
      :close-withdraw-modal="closeWithdrawModal"
      :submit-withdraw="submitWithdraw"
      :close-emergency-modal="closeEmergencyModal"
      :submit-emergency-takedown="submitEmergencyTakedown"
      :close-visibility-modal="closeVisibilityModal"
      :submit-open-visibility="submitOpenVisibility"
      :close-delete-asset-modal="closeDeleteAssetModal"
      :submit-delete-asset="submitDeleteAsset"
      :close-discard-version-modal="closeDiscardVersionModal"
      :submit-discard-version="submitDiscardVersion"
    />
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, provide, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import DatasetLifecycleModals from '@/components/datasets/DatasetLifecycleModals.vue'
import DatasetImportTab from '@/components/datasets/DatasetImportTab.vue'
import DatasetMaintenanceTab from '@/components/datasets/DatasetMaintenanceTab.vue'
import DatasetShareTab from '@/components/datasets/DatasetShareTab.vue'
import { useAuthStore } from '@/stores/auth'
import {
  formatDuration,
  formatRelative,
  getVisibilityClass,
  getVisibilityLabel,
} from '@/composables/datasets/datasetsFormatters'
import { useDatasetCatalog } from '@/composables/datasets/useDatasetCatalog'
import { useDatasetFiles, FILE_INDEX_PAGE_SIZE } from '@/composables/datasets/useDatasetFiles'
import { useDatasetRecordings } from '@/composables/datasets/useDatasetRecordings'
import { useDatasetLifecycle } from '@/composables/datasets/useDatasetLifecycle'
import { useDatasetImportTarget } from '@/composables/datasets/useDatasetImportTarget'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
import { datasetWithdrawalApi, datasetPublicizationApi } from '@/api/datasetVersions'

type DatasetWorkbenchTab = 'data' | 'import' | 'share'

// 发布与共享降级为高级入口：不再做主 tab，仅从工作台头部的次级按钮进入（见模板）。
const datasetTabs: Array<{ key: DatasetWorkbenchTab; label: string }> = [
  { key: 'data', label: '数据文件' },
  { key: 'import', label: '上传' },
]

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.roles?.includes('admin') ?? false)

// 管理员审核入口仅在「确有待审申请」时出现：空队列时按钮无意义，藏掉保持页面干净。
const pendingWithdrawals = ref(0)
const pendingPublicizations = ref(0)
async function loadPendingReviewCounts() {
  if (!isAdmin.value) return
  const [withdrawals, publicizations] = await Promise.all([
    datasetWithdrawalApi.listPending().then((r) => r.data).catch(() => []),
    datasetPublicizationApi.listPending().then((r) => r.data).catch(() => []),
  ])
  pendingWithdrawals.value = withdrawals.length
  pendingPublicizations.value = publicizations.length
}

// 目录主轴（批 2）：数据集资产列表 + 选中 + 搜索 / 筛选，是其他 composable 的依赖底座。
const catalog = useDatasetCatalog()
const {
  datasetAssets,
  selectedDatasetAssetId,
  assetSearch,
  assetVisibilityFilter,
  isLoadingAssets,
  selectedDatasetAsset,
  filteredDatasetAssets,
  loadDatasetAssets,
} = catalog

// working 文件索引 + 数据文件分桶（批 3）
const files = useDatasetFiles({ selectedDatasetAssetId })
const {
  fileSearch,
  fileRoleFilter,
  fileDisplayLimit,
  loadSelectedAssetFiles,
  resetFileIndexView,
} = files

const activePanel = ref<'catalog' | 'create'>('catalog')
const activeTab = ref<DatasetWorkbenchTab>('data')
const copyStatus = ref('')

// #15：页面级提示（渲染在详情面板之外）。删除成功后详情面板随选中清空而卸载，
// 详情内的 lifecycleMessage 看不到，故另设页面级 pageNotice，~4s 后自动清空。
const pageNotice = ref('')
let pageNoticeTimer: ReturnType<typeof setTimeout> | null = null
function showPageNotice(message: string) {
  pageNotice.value = message
  if (pageNoticeTimer) clearTimeout(pageNoticeTimer)
  pageNoticeTimer = setTimeout(() => {
    pageNotice.value = ''
    pageNoticeTimer = null
  }, 4000)
}

// 数据集生命周期：版本 / 授权用户 / 开放·转公开 / 删除（批 5）
const lifecycle = useDatasetLifecycle({ selectedDatasetAsset, selectedDatasetAssetId, loadDatasetAssets, showPageNotice })
const {
  datasetVersions,
  lifecycleMessage,
  publishModal,
  withdrawModal,
  emergencyModal,
  visibilityModal,
  discardVersionModal,
  deleteAssetModal,
  currentVersion,
  canSubmitPublish,
  publishTargetLabel,
  loadSelectedAssetVersions,
  closePublishModal,
  submitPublish,
  closeWithdrawModal,
  submitWithdraw,
  closeEmergencyModal,
  submitEmergencyTakedown,
  closeVisibilityModal,
  submitOpenVisibility,
  closeDeleteAssetModal,
  submitDeleteAsset,
  closeDiscardVersionModal,
  submitDiscardVersion,
} = lifecycle

// 导入目标准备：建集 / 挂载 + study 自动配对，产出 uploadContext / recordsStudyContext（批 6）
const importTarget = useDatasetImportTarget({ selectedDatasetAsset, selectedDatasetAssetId, activePanel, activeTab, loadDatasetAssets, loadSelectedAssetFiles })
const {
  studies,
  datasetName,
  datasetCode,
  datasetDescription,
  selectedStudyId,
  mountName,
  uploadSectionRef,
  uploadPanelRef,
  isBootstrapping,
  bootstrapError,
  bootstrapSuccess,
  queryStudyId,
  usesShortcutStudy,
  shortcutStudyLabel,
  canCreateDataset,
  canMountSelected,
  isTargetForSelectedAsset,
  recordsStudyContext,
  uploadContext,
  loadStudies,
  resetDatasetCreateForm,
  clearBootstrapResult,
  bootstrapDataset,
  mountExistingDatasetAsset,
  scrollToUploadPanel,
} = importTarget

// ===== 数据文件管理器（filemanager 视图）：后台 3 类文件角色 → 用户 2 个桶 =====
const dataView = ref<'by-subject' | 'by-type'>('by-subject')

// 采集记录：列表 + 每条记录文件懒加载 + 按被试分组（批 4）。依赖 recordsStudyContext。
const recordings = useDatasetRecordings({ selectedDatasetAsset, recordsStudyContext })
const {
  selectedAssetRecordings,
  loadSelectedAssetRecordings,
  resetRecordsView,
  loadRecordingFiles,
} = recordings

// 详情区 tab 子组件经 inject 取用（拆分批 2）
provide(datasetContextKey, {
  catalog,
  files,
  recordings,
  lifecycle,
  importTarget,
  isAdmin,
  activeTab,
  dataView,
  copyStatus,
  copyTechnicalValue,
  copyDoi,
  handleUploaded,
})

watch(selectedDatasetAssetId, () => {
  resetFileIndexView(true)
  resetRecordsView()
  void loadSelectedAssetFiles()
  void loadSelectedAssetVersions()
  if (activeTab.value === 'data') void loadSelectedAssetRecordings()
})

watch([fileSearch, fileRoleFilter], () => {
  fileDisplayLimit.value = FILE_INDEX_PAGE_SIZE
})

watch(activeTab, (tab) => {
  if (tab === 'data') void loadSelectedAssetRecordings()
})

// 「数据文件」按被试视图需要每条记录的文件分类 → 进入或记录变化时预加载每条记录的文件
watch(selectedAssetRecordings, (list) => {
  if (activeTab.value !== 'data') return
  for (const recording of list) void loadRecordingFiles(recording)
})

watch(
  () => [
    recordsStudyContext.value?.studyId || '',
    recordsStudyContext.value?.mountId || '',
    recordsStudyContext.value?.mountName || '',
  ].join('|'),
  () => {
    if (activeTab.value === 'data') void loadSelectedAssetRecordings()
  },
)

onMounted(async () => {
  void loadPendingReviewCounts()
  await Promise.all([loadStudies(), loadDatasetAssets()])
  if (queryStudyId.value) {
    selectedStudyId.value = studies.value.find((study) => study.id === queryStudyId.value)?.id || queryStudyId.value
  }
  if (!datasetAssets.value.length) openCreatePanel()
  // Phase 3 (docs_v2/3-25): 初次进入也加载版本
  if (selectedDatasetAssetId.value) void loadSelectedAssetVersions()
})

// #15：组件卸载时清掉页面级提示定时器，避免泄漏
onUnmounted(() => {
  if (pageNoticeTimer) clearTimeout(pageNoticeTimer)
})

async function reloadAll() {
  await Promise.all([loadStudies(), loadDatasetAssets()])
  await loadSelectedAssetFiles()
  await loadSelectedAssetVersions()
}

function selectDatasetAsset(assetId: string) {
  if (selectedDatasetAssetId.value === assetId) {
    activePanel.value = 'catalog'
    activeTab.value = 'data'
    return
  }
  selectedDatasetAssetId.value = assetId
  activePanel.value = 'catalog'
  activeTab.value = 'data'
  clearBootstrapResult()
}

function openCreatePanel() {
  resetDatasetCreateForm()
  activePanel.value = 'create'
  activeTab.value = 'data'
}

function returnToDatasetWorkbench() {
  activePanel.value = 'catalog'
  activeTab.value = 'data'
  clearBootstrapResult()
}

async function copyTechnicalValue(value: string, label: string) {
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable')
    await navigator.clipboard.writeText(value)
    copyStatus.value = `已复制 ${label}`
  } catch {
    copyStatus.value = '复制失败，请手动选择文本'
  }
  window.setTimeout(() => {
    if (copyStatus.value.startsWith('已复制') || copyStatus.value.startsWith('复制失败')) {
      copyStatus.value = ''
    }
  }, 1800)
}

async function handleUploaded() {
  await Promise.all([loadStudies(), loadDatasetAssets()])
  await loadSelectedAssetFiles()
  if (activeTab.value === 'data') await loadSelectedAssetRecordings()
}

async function copyDoi(doi: string) {
  try {
    await navigator.clipboard.writeText(doi)
    lifecycleMessage.value = `已复制 DOI 到剪贴板：${doi}`
  } catch {
    lifecycleMessage.value = `DOI：${doi}（剪贴板写入失败，请手动复制）`
  }
}
</script>

<!-- 拆分批 2：CSS 改全局（类名均为本页独有、无 :deep / 无全局类覆盖，渲染与 scoped 一致），
     以便抽出的 tab 子组件直接复用这些 .dataset-* 样式，无需逐 tab 搬 CSS。 -->
<style src="./DatasetsPage.css"></style>
