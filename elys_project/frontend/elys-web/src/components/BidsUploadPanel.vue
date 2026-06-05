<template>
  <section class="bids-uploader">
    <div class="bids-uploader__head">
      <div>
        <h3>导入到数据集工作版本</h3>
        <p>{{ uploadTargetSentence }}</p>
      </div>
      <span class="badge badge--primary">{{ uploadStatusBadgeText }}</span>
    </div>

    <div class="bids-target-context" :class="{ 'is-missing': !hasUploadTarget }">
      <div>
        <span>数据集</span>
        <strong>{{ uploadDatasetAssetName }}</strong>
      </div>
      <div>
        <span>处理工作空间</span>
        <strong>{{ uploadStudyName }}</strong>
      </div>
      <div>
        <span>目标状态</span>
        <strong>{{ hasUploadTarget ? '已准备好' : '未准备' }}</strong>
      </div>
    </div>

    <div class="bids-stage-strip" aria-label="Dataset import stages">
      <div v-for="stage in importStages" :key="stage.key" class="bids-stage">
        <span>{{ stage.label }}</span>
        <small>{{ stage.description }}</small>
      </div>
    </div>

    <div
      class="bids-dropzone"
      :class="{ 'is-active': isDragging }"
      @dragenter.prevent="isDragging = true"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <div class="bids-dropzone__icon">
        <AppIcon name="import" :size="26" />
      </div>
      <div>
        <strong>{{ hasUploadTarget ? '选择或拖入 EEG 原始数据' : '可先选择数据，准备导入目标后提交' }}</strong>
        <p>BrainVision 请一次选择 .vhdr / .eeg / .vmrk；EDF、BDF 可作为单文件导入。</p>
      </div>
      <div class="bids-dropzone__actions">
        <button
          class="btn btn--sm btn--primary"
          type="button"
          :disabled="isUploading"
          @click="openFileInput"
        >
          <AppIcon name="file" :size="14" />
          选择数据
        </button>
        <button
          class="btn btn--sm"
          type="button"
          :disabled="isUploading"
          @click="openFolderInput"
        >
          <AppIcon name="studies" :size="14" />
          选择文件夹
        </button>
      </div>
      <input
        :key="`file-${fileInputKey}`"
        ref="fileInput"
        class="hidden-input"
        type="file"
        multiple
        @change="handleSingleFileInput"
      />
      <input
        :key="`folder-${folderInputKey}`"
        ref="folderInput"
        class="hidden-input"
        type="file"
        webkitdirectory
        directory
        multiple
        @change="handleFolderInput"
      />
    </div>

    <details class="bids-options">
      <summary>
        <span>BIDS 实体默认值</span>
        <span class="muted text-sm">可选</span>
      </summary>
      <div class="bids-defaults">
        <label>
          <span>默认任务</span>
          <input v-model.trim="defaultTask" class="input" placeholder="rest" />
        </label>
        <label>
          <span>默认 session</span>
          <input v-model.trim="defaultSession" class="input" placeholder="可空" />
        </label>
        <label>
          <span>默认 run</span>
          <input v-model.trim="defaultRun" class="input" placeholder="可空" />
        </label>
        <div class="bids-default-actions">
          <button class="btn btn--sm" type="button" :disabled="!canApplyDefaultEntities" @click="applyDefaultEntitiesToReadyGroups">
            应用到待导入组
          </button>
          <button class="btn btn--sm" type="button" :disabled="isUploading || !groups.length" @click="clearGroups">
            清空
          </button>
        </div>
      </div>
    </details>

    <div v-if="groups.length" class="bids-queue-panel">
      <div class="bids-queue-summary" aria-label="批量导入总进度">
        <div>
          <span>总组数</span>
          <strong>{{ queueStats.total }}</strong>
        </div>
        <div>
          <span>可导入</span>
          <strong>{{ queueStats.ready }}</strong>
        </div>
        <div>
          <span>已完成</span>
          <strong>{{ queueStats.done }}</strong>
        </div>
        <div>
          <span>失败</span>
          <strong>{{ queueStats.failed }}</strong>
        </div>
        <div>
          <span>当前处理</span>
          <strong>{{ currentBatchText }}</strong>
        </div>
      </div>

      <div class="bids-queue-progress">
        <div class="bids-batch-progress__row">
          <span>{{ queueProgressText }}</span>
          <strong>{{ queueProgressPercent }}%</strong>
        </div>
        <div
          class="progress progress--lg"
          :class="{ 'progress--success': queueProgressPercent >= 100 && !queueStats.failed }"
          role="progressbar"
          :aria-valuenow="queueProgressPercent"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <div class="progress__bar" :style="queueProgressBarStyle"></div>
        </div>
      </div>

      <div class="bids-queue-controls">
        <div class="bids-queue-filters" role="tablist" aria-label="导入队列筛选">
          <button
            v-for="option in queueFilterOptions"
            :key="option.value"
            class="btn btn--sm"
            :class="{ 'btn--primary': queueFilter === option.value }"
            type="button"
            role="tab"
            :aria-selected="queueFilter === option.value"
            @click="queueFilter = option.value"
          >
            {{ option.label }}
            <span>{{ getQueueFilterCount(option.value) }}</span>
          </button>
        </div>

        <div class="bids-queue-actions" aria-label="批量动作">
          <button class="btn btn--sm" type="button" :disabled="isUploading || !queueStats.ready" @click="selectAllReadyGroups">
            全选可导入
          </button>
          <button class="btn btn--sm" type="button" :disabled="isUploading || !selectedGroupCount" @click="clearGroupSelection">
            取消选择
          </button>
          <button class="btn btn--sm" type="button" :disabled="isUploading || !retryableFailedGroups.length" @click="retryFailedGroups">
            重试失败
          </button>
          <button class="btn btn--sm" type="button" :disabled="isUploading || !queueStats.done" @click="clearCompletedGroups">
            清空已完成
          </button>
        </div>
      </div>
    </div>

    <div v-if="groups.length" class="bids-groups">
      <div v-if="!filteredGroups.length" class="bids-empty bids-empty--compact">
        <AppIcon name="file" :size="18" />
        <span>{{ filteredQueueEmptyText }}</span>
      </div>
      <div
        v-for="group in filteredGroups"
        :key="group.id"
        class="bids-group"
        :class="[`is-${group.status}`, { 'is-invalid': hasGroupInlineError(group), 'is-expanded': group.expanded }]"
      >
        <div class="bids-group__row">
          <label class="bids-group__check" :title="canSelectGroup(group) ? '选择该组导入' : getShortGroupMessage(group)">
            <input v-model="group.selected" type="checkbox" :disabled="!canSelectGroup(group) || isUploading" />
          </label>

          <span class="badge bids-group__kind" :class="group.valid ? 'badge--success' : 'badge--danger'">
            {{ group.kindLabel }}
          </span>

          <label class="bids-group__inline-field" :class="{ 'is-error': group.valid && !group.subject.trim() }">
            <span>subject</span>
            <input
              v-model.trim="group.subject"
              class="bids-inline-input"
              placeholder="sub01"
              :disabled="isUploading || !group.valid"
              aria-label="subject"
              @input="syncGroupSelectionState(group)"
            />
          </label>

          <label class="bids-group__inline-field" :class="{ 'is-error': group.valid && !group.task.trim() }">
            <span>task</span>
            <input
              v-model.trim="group.task"
              class="bids-inline-input"
              placeholder="rest"
              :disabled="isUploading || !group.valid"
              aria-label="task"
              @input="syncGroupSelectionState(group)"
            />
          </label>

          <div class="bids-group__inline-pair">
            <label class="bids-group__inline-field">
              <span>session</span>
              <input
                v-model.trim="group.session"
                class="bids-inline-input"
                placeholder="可空"
                :disabled="isUploading || !group.valid"
                aria-label="session"
              />
            </label>
            <label class="bids-group__inline-field">
              <span>run</span>
              <input
                v-model.trim="group.run"
                class="bids-inline-input"
                placeholder="可空"
                :disabled="isUploading || !group.valid"
                aria-label="run"
              />
            </label>
          </div>

          <div class="bids-group__file-count">
            <span>{{ group.files.length }}</span>
            <small>文件</small>
          </div>

          <div class="bids-group__state">
            <strong>{{ getGroupStatusLabel(group) }}</strong>
            <span :class="getGroupHintClass(group)">{{ getGroupInlineHint(group) }}</span>
          </div>

          <div class="bids-group__progress" aria-hidden="true">
            <div
              class="progress"
              :class="getProgressClass(group)"
              role="progressbar"
              :aria-valuenow="group.status === 'processing' ? undefined : group.progress"
              :aria-valuemin="group.status === 'processing' ? undefined : 0"
              :aria-valuemax="group.status === 'processing' ? undefined : 100"
              :aria-busy="group.status === 'processing'"
            >
              <div class="progress__bar" :style="getProgressBarStyle(group)"></div>
            </div>
          </div>

          <button
            class="btn btn--sm bids-group__toggle"
            type="button"
            :aria-expanded="group.expanded"
            @click="toggleGroupExpanded(group)"
          >
            {{ group.expanded ? '收起' : '展开' }}
          </button>
        </div>

        <div v-if="group.expanded" class="bids-group__details">
          <div class="bids-group__detail-grid">
            <div class="bids-group__file-summary">
              <span>文件组成</span>
              <strong>{{ getGroupFileText(group) }}</strong>
              <ul>
                <li v-for="(file, index) in group.files" :key="`${getFileRelativePath(file)}-${index}`">
                  {{ getFileRelativePath(file) }}
                </li>
              </ul>
            </div>

            <div class="bids-group__status-detail">
              <span>当前状态</span>
              <strong>{{ group.statusText }}</strong>
              <div v-if="group.message" :class="getGroupMessageClass(group)">
                {{ group.message }}
              </div>
              <div
                v-if="['uploading', 'processing', 'done'].includes(group.status)"
                class="upload-processing-steps"
              >
                <span class="is-done">original upload 已发送</span>
                <span :class="{ 'is-active': group.status === 'processing' }">Raw BIDS / canonical FIF / dataset_files 处理中</span>
                <span :class="{ 'is-done': group.status === 'done' }">完成后返回结果摘要</span>
              </div>
            </div>
          </div>

          <div v-if="group.outcome" class="bids-import-result">
            <div v-for="item in getOutcomeItems(group.outcome)" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="bids-empty">
      <AppIcon name="file" :size="20" />
      <span>还没有选择数据。</span>
    </div>

    <div class="bids-uploader__footer">
      <div>
        <div v-if="summaryText" class="muted text-sm">{{ summaryText }}</div>
        <div v-if="!hasUploadTarget" class="inline-error">请先准备导入目标；文件可以先选择，目标就绪后再提交导入。</div>
        <div v-if="globalError" class="inline-error">{{ globalError }}</div>
        <div v-if="globalSuccess" class="inline-success">{{ globalSuccess }}</div>
      </div>
      <button
        class="btn btn--primary"
        type="button"
        :disabled="!canUploadSelected"
        @click="uploadSelectedGroups"
      >
        <span v-if="isUploading" class="spinner"></span>
        {{ isUploading ? `导入中 ${queueProgressPercent}%` : `导入 ${selectedReadyGroups.length} 组数据` }}
      </button>
    </div>

    <Teleport to="body">
      <div v-if="replaceCandidate" class="bids-confirm-overlay" @click.self="closeReplaceConfirm">
        <form class="bids-confirm-card" @submit.prevent="confirmReplacement">
          <div class="card__header">
            <div>
              <h3 class="card__title">作为 Recording 新版本导入？</h3>
              <div class="card__sub">
                {{ replaceCandidate.subject }} / {{ replaceCandidate.session || '无 session' }} /
                {{ replaceCandidate.task }} / {{ replaceCandidate.run || '无 run' }}
              </div>
            </div>
            <button class="icon-btn" type="button" title="关闭" :disabled="isReplacing" @click="closeReplaceConfirm">×</button>
          </div>

          <div class="alert alert--warning">
            <AppIcon name="database" :size="18" />
            <div class="alert__body">
              该数据位已经存在。确认后系统会新增一个原始上传版本，并在 BIDS 逻辑视图、标准 FIF 与文件索引写入成功后切换为当前版本。失败时，旧版本继续作为当前数据集工作版本。
            </div>
          </div>

          <div class="bids-replace-summary">
            <div>
              <span>已有 Recording</span>
              <strong>{{ replaceDetail?.dataset_id || '已存在' }}</strong>
            </div>
            <div>
              <span>当前版本</span>
              <strong>{{ replaceDetail?.current_upload_seq ? `upload-${String(replaceDetail.current_upload_seq).padStart(3, '0')}` : '当前版本' }}</strong>
            </div>
            <div>
              <span>本次行为</span>
              <strong>新增原始上传版本并切换当前指针</strong>
            </div>
          </div>

          <div v-if="replaceError" class="inline-error">{{ replaceError }}</div>

          <div class="row row--end gap-2">
            <button class="btn" type="button" :disabled="isReplacing" @click="closeReplaceConfirm">取消</button>
            <button class="btn btn--primary" type="submit" :disabled="isReplacing">
              <span v-if="isReplacing" class="spinner"></span>
              {{ isReplacing ? '正在导入...' : '确认上传新版本' }}
            </button>
          </div>
        </form>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { datasetApi } from '@/api/datasets'
import AppIcon from '@/components/AppIcon.vue'
import type { DatasetUploadContext, RecordingUploadResponse } from '@/types'

type UploadKind = 'brainvision' | 'edf' | 'bdf' | 'invalid'
type UploadStatus = 'ready' | 'uploading' | 'processing' | 'replace-pending' | 'done' | 'error'
type QueueFilter = 'all' | 'pending' | 'failed' | 'done'

interface DatasetExistsDetail {
  code: 'DATASET_EXISTS'
  message: string
  dataset_id: string
  subject: string
  session: string | null
  task: string
  run: string | null
  current_upload_seq?: number | null
}

type UploadFileWithPath = File & {
  elysRelativePath?: string
  webkitRelativePath?: string
}

interface FileSystemEntryLike {
  isFile: boolean
  isDirectory: boolean
  name: string
}

interface FileSystemFileEntryLike extends FileSystemEntryLike {
  file: (success: (file: File) => void, error?: (error: DOMException) => void) => void
}

interface FileSystemDirectoryEntryLike extends FileSystemEntryLike {
  createReader: () => FileSystemDirectoryReaderLike
}

interface FileSystemDirectoryReaderLike {
  readEntries: (
    success: (entries: FileSystemEntryLike[]) => void,
    error?: (error: DOMException) => void,
  ) => void
}

type DataTransferItemWithEntry = DataTransferItem & {
  webkitGetAsEntry?: () => FileSystemEntryLike | null
}

interface ImportOutcome {
  recordingId: string
  datasetAssetId: string | null
  originalFileCount: number
  rawBidsFileCount: number
  datasetFileCount: number
  canonicalFifGenerated: boolean
  responseMessage: string
}

interface UploadGroup {
  id: string
  kind: UploadKind
  kindLabel: string
  title: string
  files: File[]
  valid: boolean
  selected: boolean
  subject: string
  task: string
  session: string
  run: string
  status: UploadStatus
  progress: number
  statusText: string
  message: string
  outcome: ImportOutcome | null
  expanded: boolean
}

const props = defineProps<{
  studyId: string
  studyName?: string
  datasetAssetId?: string
  datasetAssetName?: string
  mountName?: string
  uploadContext?: DatasetUploadContext
}>()

const emit = defineEmits<{
  uploaded: []
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)
const fileInputKey = ref(0)
const folderInputKey = ref(0)
const groups = ref<UploadGroup[]>([])
const isDragging = ref(false)
const isUploading = ref(false)
const defaultTask = ref('rest')
const defaultSession = ref('')
const defaultRun = ref('')
const queueFilter = ref<QueueFilter>('all')
const globalError = ref('')
const globalSuccess = ref('')
const replaceCandidate = ref<UploadGroup | null>(null)
const replaceDetail = ref<DatasetExistsDetail | null>(null)
const replaceError = ref('')
const isReplacing = ref(false)
const batchProgressTotal = ref(0)
const batchProgressCompleted = ref(0)
const batchProgressActiveGroupId = ref('')

const importStages = [
  { key: 'original', label: '原始上传', description: '保留原始文件' },
  { key: 'raw-bids', label: 'BIDS 逻辑视图', description: '整理可追踪结构' },
  { key: 'canonical-fif', label: '标准 FIF', description: '生成兼容文件' },
  { key: 'dataset-files', label: '文件索引', description: '更新可检索清单' },
] as const

const queueFilterOptions: Array<{ value: QueueFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '待导入' },
  { value: 'failed', label: '失败' },
  { value: 'done', label: '已完成' },
]

const readyGroups = computed(() =>
  groups.value.filter(isReadyUploadGroup),
)
const selectedReadyGroups = computed(() => readyGroups.value.filter((group) => group.selected))
const retryableFailedGroups = computed(() => groups.value.filter((group) => group.valid && group.status === 'error'))
const selectedGroupCount = computed(() => groups.value.filter((group) => group.selected).length)
const defaultEntityTargetGroups = computed(() => groups.value.filter((group) => group.valid && group.status === 'ready'))
const canApplyDefaultEntities = computed(() => !isUploading.value && defaultEntityTargetGroups.value.length > 0)
const queueStats = computed(() => {
  const total = groups.value.length
  const failed = groups.value.filter(isFailedQueueGroup).length
  const done = groups.value.filter((group) => group.status === 'done').length
  const ready = readyGroups.value.length
  const pending = groups.value.filter(isPendingQueueGroup).length
  return { total, ready, done, failed, pending }
})
const filteredGroups = computed(() => groups.value.filter((group) => matchesQueueFilter(group, queueFilter.value)))
const uploadStudyId = computed(() => props.uploadContext?.studyId || props.studyId)
const uploadStudyName = computed(() =>
  formatProcessingWorkspaceName(
    props.uploadContext?.studyName
    || props.studyName
    || (uploadStudyId.value ? '已准备处理工作空间' : '未准备处理工作空间'),
  ),
)
const uploadDatasetAssetId = computed(() => props.uploadContext?.datasetAssetId || props.datasetAssetId || '')
const uploadDatasetAssetName = computed(() =>
  props.uploadContext?.datasetAssetName
  || props.datasetAssetName
  || (uploadDatasetAssetId.value ? '已选择数据集' : '未指定数据集'),
)
const uploadMountName = computed(() => props.uploadContext?.mountName || props.mountName || '')
const hasUploadTarget = computed(() =>
  Boolean(uploadStudyId.value && uploadDatasetAssetId.value && uploadMountName.value),
)
const uploadStatusBadgeText = computed(() =>
  hasUploadTarget.value ? `${readyGroups.value.length} 组可导入` : '等待导入目标',
)
const uploadTargetSentence = computed(() =>
  hasUploadTarget.value
    ? `上传会写入 ${uploadDatasetAssetName.value} 的工作版本。`
    : '请先准备导入目标；文件可以先选择，目标就绪后再提交。',
)
const canUploadSelected = computed(() =>
  !isUploading.value && selectedReadyGroups.value.length > 0 && hasUploadTarget.value,
)
const summaryText = computed(() => {
  if (!groups.value.length) return ''
  const invalid = groups.value.filter((group) => !group.valid).length
  const done = groups.value.filter((group) => group.status === 'done').length
  return `${groups.value.length} 组文件，${readyGroups.value.length} 组可导入，${done} 组已完成${invalid ? `，${invalid} 组需要处理` : ''}`
})
const activeBatchGroup = computed(() =>
  groups.value.find((group) => group.id === batchProgressActiveGroupId.value) || null,
)
const batchProgressPercent = computed(() => {
  const total = batchProgressTotal.value
  if (!total) return 0
  const activeFraction = isUploading.value && activeBatchGroup.value
    ? getBatchGroupFraction(activeBatchGroup.value)
    : 0
  const handled = Math.min(batchProgressCompleted.value + activeFraction, total)
  return Math.max(0, Math.min(100, Math.round((handled / total) * 100)))
})
const batchProgressText = computed(() => {
  const total = batchProgressTotal.value
  const handled = Math.min(batchProgressCompleted.value, total)
  if (!total) return '批量进度：等待导入'
  if (!isUploading.value) return `批量进度：${handled} / ${total} 组已处理`
  const current = Math.min(handled + 1, total)
  return `批量进度：${handled} / ${total} 组已处理，当前第 ${current} 组`
})
const currentBatchText = computed(() => {
  if (isUploading.value && batchProgressTotal.value) {
    return `第 ${Math.min(batchProgressCompleted.value + 1, batchProgressTotal.value)} / ${batchProgressTotal.value} 组`
  }
  if (batchProgressTotal.value) return `${Math.min(batchProgressCompleted.value, batchProgressTotal.value)} / ${batchProgressTotal.value} 组`
  return '未开始'
})
const queueProgressPercent = computed(() => {
  const total = queueStats.value.total
  if (!total) return 0
  const activeFraction = isUploading.value && activeBatchGroup.value
    ? getBatchGroupFraction(activeBatchGroup.value)
    : 0
  const handled = queueStats.value.done + queueStats.value.failed + activeFraction
  return Math.max(0, Math.min(100, Math.round((handled / total) * 100)))
})
const queueProgressText = computed(() => {
  if (!groups.value.length) return '等待选择数据'
  if (isUploading.value) return batchProgressText.value
  if (queueStats.value.failed) return `${queueStats.value.failed} 组失败，可筛选后重试`
  if (queueStats.value.done && queueStats.value.done === queueStats.value.total) return '全部组已处理完成'
  return `${queueStats.value.done} / ${queueStats.value.total} 组已完成`
})
const queueProgressBarStyle = computed(() => ({ width: `${queueProgressPercent.value}%` }))
const filteredQueueEmptyText = computed(() => {
  if (queueFilter.value === 'pending') return '没有待导入组。'
  if (queueFilter.value === 'failed') return '没有失败组。'
  if (queueFilter.value === 'done') return '没有已完成组。'
  return '当前队列为空。'
})

let uploadGroupSequence = 0

function formatProcessingWorkspaceName(value: string) {
  return value.replace(/\s*Study$/i, ' 处理工作空间')
}

watch(hasUploadTarget, (ready) => {
  if (ready && globalError.value.includes('缺少导入目标')) {
    globalError.value = ''
  }
})

function makeUploadGroupId() {
  const randomUUID = globalThis.crypto?.randomUUID
  if (typeof randomUUID === 'function') return randomUUID.call(globalThis.crypto)
  uploadGroupSequence += 1
  return `upload-${Date.now()}-${uploadGroupSequence}-${Math.random().toString(36).slice(2, 10)}`
}

function openFileInput() {
  globalError.value = ''
  globalSuccess.value = ''
  fileInput.value?.click()
}

function openFolderInput() {
  globalError.value = ''
  globalSuccess.value = ''
  folderInput.value?.click()
}

function handleSingleFileInput(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  setSelectedFiles(files)
}

function handleFolderInput(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  setSelectedFiles(files)
}

async function handleDrop(event: DragEvent) {
  isDragging.value = false
  const dropped = await getDroppedFiles(event.dataTransfer)
  setSelectedFiles(dropped.files)
}

function setSelectedFiles(files: File[]) {
  globalError.value = ''
  globalSuccess.value = ''
  closeReplaceConfirm()
  const hasIncompleteRelatedData = hasIncompleteBrainVisionSelection(files)
  groups.value = classifyFiles(files)
  queueFilter.value = 'all'
  resetBatchProgress()
  fileInputKey.value += 1
  folderInputKey.value += 1
  if (hasIncompleteRelatedData) {
    globalError.value = 'BrainVision 是 1 个数据集，请在同一个选择框里一次框选同名 .vhdr、.eeg、.vmrk 三个文件。'
  } else if (!groups.value.length) {
    globalError.value = '没有找到可导入的 EEG 文件'
  }
}

function clearGroups() {
  groups.value = []
  globalError.value = ''
  globalSuccess.value = ''
  resetBatchProgress()
  closeReplaceConfirm()
}

function resetBatchProgress() {
  batchProgressTotal.value = 0
  batchProgressCompleted.value = 0
  batchProgressActiveGroupId.value = ''
}

function hasRequiredEntities(group: UploadGroup) {
  return Boolean(group.subject.trim() && group.task.trim())
}

function isReadyUploadGroup(group: UploadGroup) {
  return group.valid && hasRequiredEntities(group) && group.status === 'ready'
}

function canSelectGroup(group: UploadGroup) {
  return isReadyUploadGroup(group)
}

function syncGroupSelectionState(group: UploadGroup) {
  if (!isReadyUploadGroup(group)) group.selected = false
}

function isFailedQueueGroup(group: UploadGroup) {
  return group.status === 'error' || !group.valid || (group.valid && !hasRequiredEntities(group))
}

function isPendingQueueGroup(group: UploadGroup) {
  if (group.status === 'ready') return isReadyUploadGroup(group)
  return ['uploading', 'processing', 'replace-pending'].includes(group.status)
}

function matchesQueueFilter(group: UploadGroup, filter: QueueFilter) {
  if (filter === 'pending') return isPendingQueueGroup(group)
  if (filter === 'failed') return isFailedQueueGroup(group)
  if (filter === 'done') return group.status === 'done'
  return true
}

function getQueueFilterCount(filter: QueueFilter) {
  if (filter === 'pending') return queueStats.value.pending
  if (filter === 'failed') return queueStats.value.failed
  if (filter === 'done') return queueStats.value.done
  return queueStats.value.total
}

function applyDefaultEntitiesToReadyGroups() {
  defaultEntityTargetGroups.value.forEach((group) => {
    if (defaultTask.value.trim()) group.task = defaultTask.value.trim()
    group.session = defaultSession.value.trim()
    group.run = defaultRun.value.trim()
  })
}

function selectAllReadyGroups() {
  groups.value.forEach((group) => {
    group.selected = isReadyUploadGroup(group)
  })
}

function clearGroupSelection() {
  groups.value.forEach((group) => {
    group.selected = false
  })
}

function retryFailedGroups() {
  const failedGroups = retryableFailedGroups.value.slice()
  failedGroups.forEach((group) => {
    group.status = 'ready'
    group.progress = 0
    group.statusText = '等待重试'
    group.message = ''
    group.outcome = null
    group.selected = true
    group.expanded = false
  })
  if (failedGroups.length) {
    queueFilter.value = 'pending'
    resetBatchProgress()
    globalError.value = ''
  }
}

function clearCompletedGroups() {
  groups.value = groups.value.filter((group) => group.status !== 'done')
  if (!groups.value.length) queueFilter.value = 'all'
  resetBatchProgress()
}

function getGroupFileText(group: UploadGroup) {
  if (!group.valid) return group.files.map((file) => file.name).join(' / ')
  if (group.kind === 'brainvision') return '已识别 .vhdr / .eeg / .vmrk 关联文件，将作为一条原始上传'
  if (group.files.length === 1) return group.files[0].name
  return `已整理 ${group.files.length} 个关联文件，将作为一条原始上传`
}

function getGroupMessageClass(group: UploadGroup) {
  if (!group.valid || group.status === 'error') return 'inline-error'
  if (group.status === 'replace-pending') return 'inline-warning'
  if (group.status === 'done') return 'inline-success'
  return 'muted text-sm'
}

function hasGroupInlineError(group: UploadGroup) {
  return !group.valid || group.status === 'error' || (group.valid && !hasRequiredEntities(group))
}

function getShortGroupMessage(group: UploadGroup) {
  if (group.valid && !group.subject.trim()) return '缺少 subject'
  if (group.valid && !group.task.trim()) return '缺少 task'
  if (group.status === 'replace-pending') return 'Recording 已存在'

  const message = group.message || (!group.valid ? '不可导入' : '')
  if (!message) return getProgressDisplay(group)
  if (message.includes('BrainVision 数据缺少关联文件：')) {
    return message.replace('BrainVision 数据缺少关联文件：', '缺少 ')
  }
  if (message.includes('不支持的文件类型：')) {
    return message.replace('不支持的文件类型：', '不支持 ')
  }
  if (message.includes('当前格式暂不支持')) return '格式暂不支持'
  if (message.includes('当前文件由系统生成')) return '系统生成文件'
  if (message.includes('缺少导入目标')) return '缺少导入目标'
  if (message.includes('Recording 已经存在') || message.includes('Recording 已存在')) return 'Recording 已存在'
  return message.length > 20 ? `${message.slice(0, 20)}...` : message
}

function getGroupInlineHint(group: UploadGroup) {
  if (hasGroupInlineError(group) || group.status === 'replace-pending') return getShortGroupMessage(group)
  if (group.status === 'done') return getGroupSuccessSummary(group)
  return getProgressDisplay(group)
}

function getGroupHintClass(group: UploadGroup) {
  return {
    'is-error': hasGroupInlineError(group),
    'is-warning': group.status === 'replace-pending',
    'is-success': group.status === 'done',
  }
}

function toggleGroupExpanded(group: UploadGroup) {
  group.expanded = !group.expanded
}

function getGroupStatusLabel(group: UploadGroup) {
  if (!group.valid) return '不可导入'
  if (group.status === 'ready') return '待导入'
  if (group.status === 'uploading') return '上传中'
  if (group.status === 'processing') return '处理中'
  if (group.status === 'replace-pending') return '待确认'
  if (group.status === 'done') return '已导入'
  if (group.status === 'error') return '失败'
  return group.statusText
}

function getGroupSuccessSummary(group: UploadGroup) {
  if (!group.outcome) return '已导入 · 标准 FIF 已处理 · 文件索引已更新'
  const fifText = group.outcome.canonicalFifGenerated ? '已生成标准 FIF' : '标准 FIF 状态待确认'
  const fileIndexText = group.outcome.datasetFileCount ? '文件索引已更新' : '文件索引待查询'
  return `已导入 · ${fifText} · ${fileIndexText}`
}

function getProgressDisplay(group: UploadGroup) {
  if (group.status === 'ready') return '0%'
  if (group.status === 'replace-pending') return '待确认'
  if (group.status === 'error') return '0%'
  if (group.status === 'processing') return '等待服务器'
  return `${group.progress}%`
}

function getProgressClass(group: UploadGroup) {
  return {
    'progress--indeterminate': group.status === 'processing',
    'progress--success': group.status === 'done',
  }
}

function getProgressBarStyle(group: UploadGroup) {
  if (group.status === 'processing') return undefined
  return { width: `${group.progress}%` }
}

function getBatchGroupFraction(group: UploadGroup) {
  if (['done', 'error', 'replace-pending'].includes(group.status)) return 1
  if (group.status === 'processing') return 0.95
  if (group.status === 'uploading') return Math.max(0.05, Math.min(group.progress, 100) / 100)
  return 0
}

function hasIncompleteBrainVisionSelection(files: File[]) {
  const groups = groupBrainVisionFiles(files.filter(isBrainVisionFile))
  return Array.from(groups.values()).some((items) => !isCompleteBrainVisionGroup(items))
}

function classifyFiles(files: File[]): UploadGroup[] {
  const result: UploadGroup[] = []
  const brainvision = groupBrainVisionFiles(files.filter(isBrainVisionFile))

  for (const file of files) {
    const extension = getFileExtension(file)
    if (isBrainVisionFile(file)) continue
    if (extension === '.edf' || extension === '.bdf') {
      result.push(makeSingleFileGroup(file, extension === '.edf' ? 'edf' : 'bdf'))
      continue
    }
    if (extension) {
      result.push(makeInvalidGroup([file], getUnsupportedMessage(extension)))
    }
  }

  brainvision.forEach((items) => {
    if (!isCompleteBrainVisionGroup(items)) {
      result.push(makeInvalidGroup(items, getMissingBrainVisionMessage(items)))
      return
    }
    result.push(makeBrainVisionGroup(sortBrainVisionFiles(items)))
  })

  return result.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'))
}

function makeBrainVisionGroup(files: File[]): UploadGroup {
  const primary = files.find((file) => getFileExtension(file) === '.vhdr') || files[0]
  const entities = inferEntities(primary)
  return {
    id: makeUploadGroupId(),
    kind: 'brainvision',
    kindLabel: 'BrainVision',
    title: getFileStem(primary),
    files,
    valid: true,
    selected: true,
    subject: entities.subject,
    task: entities.task,
    session: entities.session,
    run: entities.run,
    status: 'ready',
    progress: 0,
    statusText: '等待导入',
    message: '',
    outcome: null,
    expanded: false,
  }
}

function makeSingleFileGroup(file: File, kind: 'edf' | 'bdf'): UploadGroup {
  const entities = inferEntities(file)
  return {
    id: makeUploadGroupId(),
    kind,
    kindLabel: kind.toUpperCase(),
    title: file.name,
    files: [file],
    valid: true,
    selected: true,
    subject: entities.subject,
    task: entities.task,
    session: entities.session,
    run: entities.run,
    status: 'ready',
    progress: 0,
    statusText: '等待导入',
    message: '',
    outcome: null,
    expanded: false,
  }
}

function makeInvalidGroup(files: File[], message: string): UploadGroup {
  const title = files[0]?.name || '无法识别的文件'
  return {
    id: makeUploadGroupId(),
    kind: 'invalid',
    kindLabel: '不可导入',
    title,
    files,
    valid: false,
    selected: false,
    subject: '',
    task: defaultTask.value || 'rest',
    session: defaultSession.value,
    run: defaultRun.value,
    status: 'error',
    progress: 0,
    statusText: '不可导入',
    message,
    outcome: null,
    expanded: true,
  }
}

function getUnsupportedMessage(extension: string) {
  const rejected: Record<string, string> = {
    '.set': '当前格式暂不支持，请先转换为平台支持的原始数据格式。',
    '.fdt': '当前格式暂不支持，请先转换为平台支持的原始数据格式。',
    '.fif': '当前文件由系统生成，不需要直接导入。',
    '.cnt': '已识别该格式，当前版本暂不支持直接导入。',
    '.mff': '已识别该格式，当前版本暂不支持直接导入。',
    '.gdf': '已识别该格式，当前版本暂不支持直接导入。',
    '.mat': '已识别该格式，当前版本暂不支持直接导入。',
    '.h5': '已识别该格式，当前版本暂不支持直接导入。',
    '.hdf5': '已识别该格式，当前版本暂不支持直接导入。',
    '.csv': '当前文件不作为独立 EEG 数据导入。',
    '.tsv': '当前文件不作为独立 EEG 数据导入。',
  }
  return rejected[extension] || `不支持的文件类型：${extension}`
}

function getMissingBrainVisionMessage(files: File[]) {
  const extensions = new Set(files.map(getFileExtension))
  const missing = ['.vhdr', '.eeg', '.vmrk'].filter((extension) => !extensions.has(extension))
  return `BrainVision 数据缺少关联文件：${missing.join(' / ')}`
}

function inferEntities(file: File) {
  const text = `${getFileRelativePath(file)} ${file.name}`
  return {
    subject: findEntity(text, /sub-?([A-Za-z0-9]+)/i) || '01',
    session: findEntity(text, /ses-?([A-Za-z0-9]+)/i) || defaultSession.value,
    task: findEntity(text, /task-?([A-Za-z0-9]+)/i) || defaultTask.value || 'rest',
    run: findEntity(text, /run-?([A-Za-z0-9]+)/i) || defaultRun.value,
  }
}

function findEntity(text: string, pattern: RegExp) {
  const match = text.match(pattern)
  return match?.[1] ? sanitizeEntity(match[1]) : ''
}

function sanitizeEntity(value: string) {
  return value.replace(/[^A-Za-z0-9]/g, '')
}

function getFileExtension(file: File) {
  const index = file.name.lastIndexOf('.')
  return index >= 0 ? file.name.slice(index).toLowerCase() : ''
}

function getFileStem(file: File) {
  const index = file.name.lastIndexOf('.')
  return index >= 0 ? file.name.slice(0, index) : file.name
}

function isBrainVisionFile(file: File) {
  return ['.vhdr', '.eeg', '.vmrk'].includes(getFileExtension(file))
}

function getFileRelativePath(file: File) {
  const withRelativePath = file as UploadFileWithPath
  return withRelativePath.elysRelativePath || withRelativePath.webkitRelativePath || file.name
}

function getFileParent(file: File) {
  const path = getFileRelativePath(file).replace(/\\/g, '/')
  const index = path.lastIndexOf('/')
  return index >= 0 ? path.slice(0, index) : ''
}

function groupBrainVisionFiles(files: File[]) {
  const groups = new Map<string, File[]>()
  for (const file of files) {
    const key = `${getFileParent(file)}|${getFileStem(file).toLowerCase()}`
    groups.set(key, [...(groups.get(key) || []), file])
  }
  return groups
}

function isCompleteBrainVisionGroup(files: File[]) {
  const extensions = new Set(files.map(getFileExtension))
  return ['.vhdr', '.eeg', '.vmrk'].every((extension) => extensions.has(extension))
}

async function getDroppedFiles(dataTransfer: DataTransfer | null): Promise<{ files: File[]; hasDirectory: boolean }> {
  if (!dataTransfer) return { files: [], hasDirectory: false }

  const entries = Array.from(dataTransfer.items || [])
    .map((item) => (item as DataTransferItemWithEntry).webkitGetAsEntry?.() || null)
    .filter(Boolean) as FileSystemEntryLike[]

  if (!entries.length) {
    return { files: Array.from(dataTransfer.files || []), hasDirectory: false }
  }

  const files = (await Promise.all(entries.map((entry) => readDroppedEntry(entry)))).flat()
  return {
    files,
    hasDirectory: entries.some((entry) => entry.isDirectory),
  }
}

async function readDroppedEntry(entry: FileSystemEntryLike, parentPath = ''): Promise<File[]> {
  const relativePath = parentPath ? `${parentPath}/${entry.name}` : entry.name

  if (entry.isFile) {
    const file = await readFileEntry(entry as FileSystemFileEntryLike)
    return [withElysRelativePath(file, relativePath)]
  }

  if (!entry.isDirectory) return []

  const directory = entry as FileSystemDirectoryEntryLike
  const children = await readAllDirectoryEntries(directory)
  const nested = await Promise.all(children.map((child) => readDroppedEntry(child, relativePath)))
  return nested.flat()
}

function readFileEntry(entry: FileSystemFileEntryLike) {
  return new Promise<File>((resolve, reject) => {
    entry.file(resolve, reject)
  })
}

async function readAllDirectoryEntries(directory: FileSystemDirectoryEntryLike) {
  const reader = directory.createReader()
  const entries: FileSystemEntryLike[] = []

  while (true) {
    const batch = await new Promise<FileSystemEntryLike[]>((resolve, reject) => {
      reader.readEntries(resolve, reject)
    })
    if (!batch.length) break
    entries.push(...batch)
  }

  return entries
}

function withElysRelativePath(file: File, relativePath: string): File {
  try {
    Object.defineProperty(file, 'elysRelativePath', {
      value: relativePath.replace(/^\/+/, ''),
      configurable: true,
    })
  } catch {
    // Some browser File objects are not extensible. The plain filename still works for single-file uploads.
  }
  return file
}

function sortBrainVisionFiles(files: File[]) {
  const order = ['.vhdr', '.eeg', '.vmrk']
  return [...files].sort(
    (a, b) => order.indexOf(getFileExtension(a)) - order.indexOf(getFileExtension(b)),
  )
}

function getUploadErrorMessage(err: any) {
  const detail = err.response?.data?.detail
  if (isDatasetExistsDetail(detail)) return detail.message
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join('；')
  }
  if (detail) return detail
  if (err.response?.status) return `导入失败 (HTTP ${err.response.status})`
  if (err.code === 'ECONNABORTED') return '导入失败：上传或转换超时'
  if (err.message) return `导入失败：${err.message}`
  return '导入失败'
}

function isDatasetExistsDetail(detail: unknown): detail is DatasetExistsDetail {
  return Boolean(
    detail
      && typeof detail === 'object'
      && (detail as DatasetExistsDetail).code === 'DATASET_EXISTS',
  )
}

function getDatasetExistsDetail(err: any): DatasetExistsDetail | null {
  const detail = err.response?.data?.detail
  return isDatasetExistsDetail(detail) ? detail : null
}

function buildImportOutcome(response: RecordingUploadResponse, group: UploadGroup): ImportOutcome {
  const recording = response.recording
  return {
    recordingId: recording?.id || '兼容记录',
    datasetAssetId: recording?.dataset_asset_id || null,
    originalFileCount: group.files.length,
    rawBidsFileCount: 0,
    datasetFileCount: 0,
    canonicalFifGenerated: Boolean(recording?.fif_path),
    responseMessage: response.message || '已导入数据集工作版本',
  }
}

function getOutcomeItems(outcome: ImportOutcome) {
  return [
    {
      label: '用户摘要',
      value: getOutcomeUserSummary(outcome),
    },
    {
      label: 'original upload',
      value: `已登记 ${outcome.originalFileCount} 个原始文件`,
    },
    {
      label: 'Raw BIDS',
      value: outcome.rawBidsFileCount
        ? `已登记 ${outcome.rawBidsFileCount} 个 raw_bids 文件`
        : '当前上传响应未返回文件树，待 Dataset File API 查询',
    },
    {
      label: 'canonical FIF',
      value: outcome.canonicalFifGenerated ? '已生成或已登记' : '未返回生成状态，可能仍待转换',
    },
    {
      label: 'dataset_files',
      value: outcome.datasetFileCount
        ? `已返回 ${outcome.datasetFileCount} 条文件索引`
        : '当前上传响应未返回索引详情',
    },
    {
      label: 'API response',
      value: outcome.responseMessage,
    },
  ]
}

function getOutcomeUserSummary(outcome: ImportOutcome) {
  const fifText = outcome.canonicalFifGenerated ? '已生成标准 FIF' : '标准 FIF 状态待确认'
  const fileIndexText = outcome.datasetFileCount ? '文件索引已更新' : '文件索引待查询'
  return `已导入；${fifText}；${fileIndexText}`
}

async function uploadGroup(group: UploadGroup, replaceExisting = false): Promise<'success' | 'duplicate' | 'failed'> {
  const target = getUploadTarget()
  if (!target) {
    group.status = 'error'
    group.progress = 0
    group.statusText = '导入失败'
    group.message = '缺少导入目标，无法提交上传。'
    group.outcome = null
    group.expanded = true
    return 'failed'
  }

  group.status = 'uploading'
  group.progress = 0
  group.statusText = '正在上传原始数据'
  group.message = ''
  group.outcome = null

  try {
    const res = await datasetApi.upload(
      target.studyId,
      {
        subject: group.subject,
        task: group.task,
        session: group.session || undefined,
        run: group.run || undefined,
        files: group.files,
        replaceExisting,
        datasetAssetId: target.datasetAssetId,
        mountName: target.mountName,
      },
      {
        onProgress: (percent) => {
          group.progress = percent
          if (group.status !== 'processing') {
            group.status = 'uploading'
            group.statusText = '正在上传原始数据'
          }
        },
        onUploadComplete: () => {
          group.status = 'processing'
          group.progress = 100
          group.statusText = '上传完成，正在生成 BIDS 逻辑视图、标准 FIF 和文件索引'
        },
      },
    )
    group.outcome = buildImportOutcome(res.data, group)
    group.status = 'done'
    group.progress = 100
    group.statusText = getOutcomeUserSummary(group.outcome)
    group.message = group.outcome.responseMessage
    group.selected = false
    group.expanded = false
    return 'success'
  } catch (err: any) {
    const existsDetail = getDatasetExistsDetail(err)
    if (existsDetail && !replaceExisting) {
      group.status = 'replace-pending'
      group.progress = 0
      group.statusText = '等待确认'
      group.message = '该 Recording 已存在，请确认是否作为原始上传新版本导入并切换为当前版本。'
      group.selected = false
      group.outcome = null
      group.expanded = true
      replaceCandidate.value = group
      replaceDetail.value = existsDetail
      replaceError.value = ''
      return 'duplicate'
    }
    group.status = 'error'
    group.progress = 0
    group.statusText = '导入失败'
    group.message = getUploadErrorMessage(err)
    group.outcome = null
    group.expanded = true
    return 'failed'
  }
}

async function uploadSelectedGroups() {
  if (!hasUploadTarget.value) {
    globalError.value = '缺少导入目标，无法提交上传。'
    return
  }

  isUploading.value = true
  globalError.value = ''
  globalSuccess.value = ''

  const uploadQueue = selectedReadyGroups.value.slice()
  batchProgressTotal.value = uploadQueue.length
  batchProgressCompleted.value = 0
  batchProgressActiveGroupId.value = ''

  let successCount = 0
  let failCount = 0
  let duplicateCount = 0
  for (const group of uploadQueue) {
    batchProgressActiveGroupId.value = group.id
    const result = await uploadGroup(group)
    batchProgressCompleted.value += 1
    if (result === 'success') successCount += 1
    if (result === 'failed') failCount += 1
    if (result === 'duplicate') {
      duplicateCount += 1
      break
    }
  }

  if (successCount) {
    globalSuccess.value = `已成功导入 ${successCount} 组数据到当前数据集`
    emit('uploaded')
  }
  if (duplicateCount) {
    globalError.value = '有 Recording 已经存在，请在弹窗中确认是否新增原始上传版本并切换当前指针'
  }
  if (failCount) {
    globalError.value = `${failCount} 组导入失败，请查看对应红色提示后重试`
  }
  batchProgressActiveGroupId.value = ''
  isUploading.value = false
}

function closeReplaceConfirm() {
  if (isReplacing.value) return
  replaceCandidate.value = null
  replaceDetail.value = null
  replaceError.value = ''
}

function getUploadTarget() {
  if (!hasUploadTarget.value) return null
  return {
    studyId: uploadStudyId.value,
    datasetAssetId: uploadDatasetAssetId.value,
    mountName: uploadMountName.value,
  }
}

async function confirmReplacement() {
  if (!replaceCandidate.value) return
  isReplacing.value = true
  isUploading.value = true
  replaceError.value = ''
  globalError.value = ''
  try {
    const result = await uploadGroup(replaceCandidate.value, true)
    if (result === 'success') {
      globalSuccess.value = '已新增原始上传版本，并切换为当前数据集工作版本'
      emit('uploaded')
      replaceCandidate.value = null
      replaceDetail.value = null
      replaceError.value = ''
    } else {
      replaceError.value = replaceCandidate.value.message || '导入新版本失败，请稍后重试'
    }
  } finally {
    isReplacing.value = false
    isUploading.value = false
  }
}
</script>
