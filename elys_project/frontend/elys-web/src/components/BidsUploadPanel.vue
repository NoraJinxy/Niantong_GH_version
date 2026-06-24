<template>
  <section class="bids-uploader">
    <div class="bids-uploader__head">
      <div>
        <h3>导入 EEG 数据</h3>
        <p>{{ uploadTargetSentence }}</p>
      </div>
      <span class="badge badge--primary">{{ uploadStatusBadgeText }}</span>
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

    <div v-if="groups.length > 1" class="bids-queue-panel">
      <div class="bids-queue-summary" aria-label="批量导入总进度">
        <div>
          <span>总份数</span>
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

    <div v-if="groups.length" class="bids-mapping">
      <div class="bids-mapping__rule">
        <span><AppIcon name="import" :size="14" /> {{ mappingRuleText }}</span>
        <button class="btn btn--sm" type="button" :disabled="isUploading || !groups.length" @click="clearGroups">清空</button>
      </div>

      <div v-if="sessionSplitSuggestion" class="bids-suggestion">
        <span>
          <AppIcon name="studies" :size="14" />
          检测到 {{ sessionSplitSuggestion.samples.join(' / ') }} —— 末尾字母像是会话(session)？
        </span>
        <button class="btn btn--sm" type="button" :disabled="isUploading" @click="applySessionSuffixSplit">
          拆成 subject + session（{{ sessionSplitSuggestion.count }} 份）
        </button>
      </div>

      <div class="bids-bulk">
        <span class="bids-bulk__label">整列批量填</span>
        <div class="bids-bulk__field">
          <label><span>task</span><input v-model.trim="defaultTask" class="bids-inline-input" placeholder="rest" :disabled="isUploading" /></label>
          <button class="btn btn--sm" type="button" :disabled="!canApplyDefaultEntities" @click="applyColumnToReadyGroups('task')">填充全部</button>
        </div>
        <div class="bids-bulk__field">
          <label><span>session</span><input v-model.trim="defaultSession" class="bids-inline-input" placeholder="可空" :disabled="isUploading" /></label>
          <button class="btn btn--sm" type="button" :disabled="!canApplyDefaultEntities" @click="applyColumnToReadyGroups('session')">填充全部</button>
        </div>
        <div class="bids-bulk__field">
          <label><span>run</span><input v-model.trim="defaultRun" class="bids-inline-input" placeholder="可空" :disabled="isUploading" /></label>
          <button class="btn btn--sm" type="button" :disabled="!canApplyDefaultEntities" @click="applyColumnToReadyGroups('run')">填充全部</button>
          <button class="btn btn--sm" type="button" :disabled="!canApplyDefaultEntities" @click="applyRunSequenceToReadyGroups">顺延 01·02·03</button>
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
        <div class="bids-group__filename" :title="group.files.map((file) => file.name).join('  ·  ')">
          <AppIcon name="file" :size="13" />
          <strong>{{ group.title }}</strong>
        </div>

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
              <button
                v-if="group.status === 'replace-pending'"
                class="btn btn--sm btn--primary"
                type="button"
                @click="openReplaceConfirm(group)"
              >
                确认上传
              </button>
              <div
                v-if="['uploading', 'processing', 'done'].includes(group.status)"
                class="upload-processing-steps"
              >
                <span class="is-done">原始文件已上传</span>
                <span :class="{ 'is-active': group.status === 'processing' }">正在整理与标准化</span>
                <span :class="{ 'is-done': group.status === 'done' }">完成后显示结果</span>
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

    <details class="bids-options">
      <summary>
        <span>高级选项</span>
        <span class="muted text-sm">可选</span>
      </summary>
      <div class="bids-advanced-section">
        <span class="bids-advanced-label">导入后会自动整理、标准化并建立文件清单</span>
        <div class="bids-stage-strip" aria-label="导入处理过程">
          <div v-for="stage in importStages" :key="stage.key" class="bids-stage">
            <span>{{ stage.label }}</span>
            <small>{{ stage.description }}</small>
          </div>
        </div>
      </div>
    </details>

    <div class="bids-uploader__footer">
      <div>
        <div v-if="summaryText" class="muted text-sm">{{ summaryText }}</div>
        <div v-if="bidsSummary.total" class="muted text-sm" :class="{ 'is-warning': bidsSummary.hasWarning }">
          {{ bidsSummary.passed }} / {{ bidsSummary.total }} 份通过 BIDS 校验{{ bidsSummary.hasWarning ? '；黄色项可修正后再导入（不影响其余）' : '' }}
        </div>
        <div v-if="!hasUploadTarget" class="muted text-sm">系统正在自动准备上传位置；文件可以先选择，稍候即可提交。</div>
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
        {{ isUploading ? `导入中 ${queueProgressPercent}%` : `导入 ${selectedReadyGroups.length} 份数据` }}
      </button>
    </div>

    <Teleport to="body">
      <div v-if="replaceCandidate" class="bids-confirm-overlay" @click.self="closeReplaceConfirm">
        <form class="bids-confirm-card" @submit.prevent="confirmReplacement">
          <div class="card__header">
            <div>
              <h3 class="card__title">「{{ replaceCandidate.subject }} · {{ replaceCandidate.task }}」已经有数据了</h3>
              <div class="card__sub">
                被试 {{ replaceCandidate.subject }} / {{ replaceCandidate.session ? '会话 ' + replaceCandidate.session : '无会话' }} /
                任务 {{ replaceCandidate.task }} / {{ replaceCandidate.run ? '轮次 ' + replaceCandidate.run : '无轮次' }}
              </div>
            </div>
            <button class="icon-btn" type="button" title="关闭" :disabled="isReplacing" @click="closeReplaceConfirm">×</button>
          </div>

          <div class="alert alert--warning">
            <AppIcon name="database" :size="18" />
            <div class="alert__body">
              这次上传会作为这条记录的「新一次数据」。之前那次会留作历史、随时可查；整理好后，分析会自动改用这次的新数据（万一这次没成功，仍用原来的）。
            </div>
          </div>

          <div class="bids-replace-summary">
            <div>
              <span>之前</span>
              <strong>已上传 {{ replaceDetail?.current_upload_seq || 1 }} 次</strong>
            </div>
            <div>
              <span>这次</span>
              <strong>作为新一次数据</strong>
            </div>
            <div>
              <span>之前的数据</span>
              <strong>留作历史</strong>
            </div>
          </div>

          <div v-if="replaceError" class="inline-error">{{ replaceError }}</div>

          <div class="row row--end gap-2">
            <button class="btn" type="button" :disabled="isReplacing" @click="closeReplaceConfirm">取消（去改标签）</button>
            <button class="btn btn--primary" type="submit" :disabled="isReplacing">
              <span v-if="isReplacing" class="spinner"></span>
              {{ isReplacing ? '正在导入...' : '作为新一次数据上传' }}
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
  speedBps?: number
  statusText: string
  message: string
  outcome: ImportOutcome | null
  existsDetail: DatasetExistsDetail | null
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
const autoFillNote = ref('')
const existingTuples = ref<Set<string>>(new Set())
let existingRecordingsKey = ''
// 上传期撞「已存在」时，自动顺延被试号重传的最大次数。nextFreeSubject 单次就会扫到空号，
// 故正常一次即中；多出来的次数只为兜并发竞争（别的会话刚抢走同号）。超过仍撞才回退到弹窗。
const MAX_AUTO_ADAPT_RETRIES = 8

const importStages = [
  { key: 'original', label: '原始文件', description: '保留你上传的原文件' },
  { key: 'raw-bids', label: '标准目录', description: '整理为可追踪结构' },
  { key: 'canonical-fif', label: '标准化文件', description: '生成统一分析格式' },
  { key: 'dataset-files', label: '文件清单', description: '更新可检索清单' },
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
  hasUploadTarget.value ? `${readyGroups.value.length} 份可导入` : '准备中',
)
const uploadTargetSentence = computed(() =>
  hasUploadTarget.value
    ? `上传会保存到「${uploadDatasetAssetName.value}」。`
    : '系统正在自动准备上传位置；文件可以先选择，稍候即可提交。',
)
const canUploadSelected = computed(() =>
  !isUploading.value && selectedReadyGroups.value.length > 0 && hasUploadTarget.value,
)
const summaryText = computed(() => {
  if (!groups.value.length) return ''
  const invalid = groups.value.filter((group) => !group.valid).length
  const done = groups.value.filter((group) => group.status === 'done').length
  return `${groups.value.length} 份文件，${readyGroups.value.length} 份可导入，${done} 份已完成${invalid ? `，${invalid} 份需要处理` : ''}`
})
const activeBatchGroup = computed(() =>
  groups.value.find((group) => group.id === batchProgressActiveGroupId.value) || null,
)
const batchProgressText = computed(() => {
  const total = batchProgressTotal.value
  const handled = Math.min(batchProgressCompleted.value, total)
  if (!total) return '批量进度：等待导入'
  if (!isUploading.value) return `批量进度：${handled} / ${total} 份已处理`
  const current = Math.min(handled + 1, total)
  return `批量进度：${handled} / ${total} 份已处理，当前第 ${current} 份`
})
const currentBatchText = computed(() => {
  if (isUploading.value && batchProgressTotal.value) {
    return `第 ${Math.min(batchProgressCompleted.value + 1, batchProgressTotal.value)} / ${batchProgressTotal.value} 份`
  }
  if (batchProgressTotal.value) return `${Math.min(batchProgressCompleted.value, batchProgressTotal.value)} / ${batchProgressTotal.value} 份`
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
  if (queueStats.value.failed) return `${queueStats.value.failed} 份失败，可筛选后重试`
  if (queueStats.value.done && queueStats.value.done === queueStats.value.total) return '全部都已处理完成'
  return `${queueStats.value.done} / ${queueStats.value.total} 份已完成`
})
const queueProgressBarStyle = computed(() => ({ width: `${queueProgressPercent.value}%` }))
const filteredQueueEmptyText = computed(() => {
  if (queueFilter.value === 'pending') return '没有待导入的数据。'
  if (queueFilter.value === 'failed') return '没有失败的数据。'
  if (queueFilter.value === 'done') return '没有已完成的数据。'
  return '当前队列为空。'
})

let uploadGroupSequence = 0

watch(hasUploadTarget, (ready) => {
  if (ready && globalError.value.includes('缺少导入目标')) {
    globalError.value = ''
  }
})

// 导入目标（study + 数据集）就绪或切换时，后台尽力把库里已有的 recordings 捞回来，
// 供「自动分配被试编号」避开已占用的四元组（best-effort，失败只退化为「保证本批内部不冲突」）。
watch(
  () => `${uploadStudyId.value}|${uploadDatasetAssetId.value}`,
  () => { void loadExistingRecordings() },
  { immediate: true },
)

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
  void setSelectedFiles(files)
}

function handleFolderInput(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  void setSelectedFiles(files)
}

async function handleDrop(event: DragEvent) {
  isDragging.value = false
  const dropped = await getDroppedFiles(event.dataTransfer)
  void setSelectedFiles(dropped.files)
}

async function setSelectedFiles(files: File[]) {
  globalError.value = ''
  globalSuccess.value = ''
  autoFillNote.value = ''
  closeReplaceConfirm()
  // 自动分配被试编号要避开库里已有的四元组，先尽力把已有记录捞回来（已缓存则瞬回）
  await loadExistingRecordings()
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
  autoFillNote.value = ''
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

// —— 整列批量填：把某一列一键填到所有「待导入」组，省去 14 行逐个点。
// task 留空不覆盖（task 必填）；session/run 留空即视为「整列清空」。
function applyColumnToReadyGroups(column: 'task' | 'session' | 'run') {
  const value =
    column === 'task' ? defaultTask.value.trim()
    : column === 'session' ? defaultSession.value.trim()
    : defaultRun.value.trim()
  defaultEntityTargetGroups.value.forEach((group) => {
    if (column === 'task') {
      if (value) group.task = value
    } else {
      group[column] = value
    }
    syncGroupSelectionState(group)
  })
}

// run 顺延填充：按当前显示顺序给「待导入」组依次编号 01、02、03…（文件名没带 run 时最省手）。
function applyRunSequenceToReadyGroups() {
  let n = Number(defaultRun.value.trim()) || 1
  defaultEntityTargetGroups.value.forEach((group) => {
    group.run = String(n).padStart(2, '0')
    syncGroupSelectionState(group)
    n += 1
  })
}

// —— 智能建议：被试号末尾的单个字母（如 007a / 007b）通常是「会话(session)」而非被试编号的一部分。
// 命中条件：字段以「数字 + 单个字母」收尾且 session 还空着。给一键拆分，不自动改（语义判断交还用户）。
const sessionSuffixGroups = computed(() =>
  groups.value.filter(
    (group) => group.valid && !group.session.trim() && /^[A-Za-z0-9]*\d[A-Za-z]$/.test(group.subject),
  ),
)
const sessionSplitSuggestion = computed(() => {
  const matches = sessionSuffixGroups.value
  if (matches.length < 2) return null
  const samples = Array.from(new Set(matches.map((group) => group.subject))).slice(0, 3)
  return { count: matches.length, samples }
})
function applySessionSuffixSplit() {
  sessionSuffixGroups.value.forEach((group) => {
    const match = group.subject.match(/^(.*\d)([A-Za-z])$/)
    if (!match) return
    group.subject = match[1]
    group.session = match[2].toLowerCase()
    syncGroupSelectionState(group)
  })
}

// —— BIDS 字段校验：只允许字母和数字。非法字符给 warning 但不拦上传（符合「厚薄分层」的薄层引导：
// 能跑就放行，只在该提醒时提醒）。subject/task 仍由 hasRequiredEntities 作硬性必填。
const BIDS_ENTITY_PATTERN = /^[A-Za-z0-9]+$/
function getBidsWarnings(group: UploadGroup): string[] {
  if (!group.valid) return []
  const warnings: string[] = []
  const entries: Array<[string, string]> = [
    ['subject', group.subject],
    ['session', group.session],
    ['task', group.task],
    ['run', group.run],
  ]
  for (const [label, value] of entries) {
    if (value.trim() && !BIDS_ENTITY_PATTERN.test(value.trim())) {
      warnings.push(`${label} 含字母数字以外的字符`)
    }
  }
  return warnings
}
function groupHasBidsWarning(group: UploadGroup) {
  return getBidsWarnings(group).length > 0
}
const bidsSummary = computed(() => {
  const valid = groups.value.filter((group) => group.valid)
  const passed = valid.filter((group) => hasRequiredEntities(group) && !groupHasBidsWarning(group)).length
  return { total: valid.length, passed, hasWarning: valid.some(groupHasBidsWarning) }
})

const mappingRuleText = computed(() =>
  autoFillNote.value
  || '已按文件名自动识别 subject / run（task 默认 rest）；可整列批量填，或在下方逐行修改。',
)

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
  if (group.status === 'ready' && groupHasBidsWarning(group)) return getBidsWarnings(group)[0]
  return getProgressDisplay(group)
}

function getGroupHintClass(group: UploadGroup) {
  return {
    'is-error': hasGroupInlineError(group),
    'is-warning': group.status === 'replace-pending' || (group.status === 'ready' && groupHasBidsWarning(group)),
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
  if (!group.outcome) return '已导入 · 标准化文件已处理 · 文件清单已更新'
  const fifText = group.outcome.canonicalFifGenerated ? '已生成标准化文件' : '标准化文件状态待确认'
  const fileIndexText = group.outcome.datasetFileCount ? '文件清单已更新' : '文件清单待查询'
  return `已导入 · ${fifText} · ${fileIndexText}`
}

function nowMs() {
  return typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()
}

function formatSpeed(bytesPerSec?: number) {
  if (!bytesPerSec || bytesPerSec <= 0 || !Number.isFinite(bytesPerSec)) return ''
  const units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
  let value = bytesPerSec
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  const digits = unitIndex === 0 || value >= 100 ? 0 : 1
  return `${value.toFixed(digits)} ${units[unitIndex]}`
}

function getProgressDisplay(group: UploadGroup) {
  if (group.status === 'ready') return '0%'
  if (group.status === 'replace-pending') return '待确认'
  if (group.status === 'error') return '0%'
  if (group.status === 'processing') return '等待服务器'
  const speed = formatSpeed(group.speedBps)
  return speed ? `${group.progress}% · ${speed}` : `${group.progress}%`
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

  result.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'))
  assignBatchSubjects(result)
  return result
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
    existsDetail: null,
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
    existsDetail: null,
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
    existsDetail: null,
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
    subject: findEntity(text, /sub-?([A-Za-z0-9]+)/i),
    session: findEntity(text, /ses-?([A-Za-z0-9]+)/i) || defaultSession.value,
    task: findEntity(text, /task-?([A-Za-z0-9]+)/i) || defaultTask.value || 'rest',
    run: findRun(text) || defaultRun.value,
  }
}

// run 既要认 BIDS 写法（run-01 / run01 / run_01），也要认实验室常见简写（_r01 / -r1）。
// 简写要求「分隔符 + r + 数字」且后面紧跟分隔符或结尾，避免误伤 subject 里的字母。
// 若 run 认不出来，同一被试的多个 run 四元组会全部撞车 → 触发去重把 subject 改花（见 assignBatchSubjects）。
function findRun(text: string) {
  const bids = text.match(/run[-_]?(\d+)/i)
  if (bids?.[1]) return sanitizeEntity(bids[1])
  const shorthand = text.match(/[_-]r(\d+)(?=[_.\-]|$)/i)
  if (shorthand?.[1]) return sanitizeEntity(shorthand[1])
  return ''
}

function findEntity(text: string, pattern: RegExp) {
  const match = text.match(pattern)
  return match?.[1] ? sanitizeEntity(match[1]) : ''
}

function sanitizeEntity(value: string) {
  return value.replace(/[^A-Za-z0-9]/g, '')
}

// —— 批量被试编号（subject）自动分配 ——
// 痛点：一批没带 BIDS「sub-」标签的文件，旧逻辑会各自兜底成同一个 subject（'01'），
// 于是它们的 (subject/session/task/run) 四元组彼此相同 → 互相覆盖、触发「已存在」弹窗。
// 这里做一次「批级」消歧：先尝试从文件名 / 路径的差异里抠出能区分彼此的编号；抠不出来再
// 顺序兜底（01、02…），并避开库里已有的四元组。只是「大致模糊」的猜测，用户仍可在表格逐个改。

function discriminatorSource(group: UploadGroup) {
  const primary = group.files.find((file) => getFileExtension(file) === '.vhdr') || group.files[0]
  if (!primary) return ''
  const path = getFileRelativePath(primary).replace(/\\/g, '/')
  const extension = getFileExtension(primary)
  return extension ? path.slice(0, path.length - extension.length) : path
}

function longestCommonPrefix(items: string[]) {
  if (!items.length) return ''
  let prefix = items[0]
  for (const item of items) {
    while (prefix && !item.startsWith(prefix)) prefix = prefix.slice(0, -1)
    if (!prefix) return ''
  }
  return prefix
}

function longestCommonSuffix(items: string[]) {
  if (!items.length) return ''
  let suffix = items[0]
  for (const item of items) {
    while (suffix && !item.endsWith(suffix)) suffix = suffix.slice(1)
    if (!suffix) return ''
  }
  return suffix
}

function padNumericTokens(tokens: string[]) {
  if (!tokens.every((token) => /^\d+$/.test(token))) return tokens
  const width = Math.max(2, ...tokens.map((token) => token.length))
  return tokens.map((token) => token.padStart(width, '0'))
}

// 剥掉一组标签的公共前缀 / 公共后缀，留下中间「真正不一样」的那段当区分编号。
// 仅当每个都非空且互不相同才算可靠；否则返回空串数组，交给顺序兜底。
function deriveDistinctTokens(labels: string[]): string[] {
  if (labels.length < 2) return labels.map(() => '')
  const prefix = longestCommonPrefix(labels)
  const trimmedFront = labels.map((label) => label.slice(prefix.length))
  const suffix = longestCommonSuffix(trimmedFront)
  const cores = trimmedFront.map((label) => (suffix ? label.slice(0, label.length - suffix.length) : label))
  const tokens = cores.map((core) => sanitizeEntity(core))
  if (!tokens.every(Boolean)) return labels.map(() => '')
  if (new Set(tokens).size !== tokens.length) return labels.map(() => '')
  return padNumericTokens(tokens)
}

function normalizeEntityValue(value: string | null | undefined) {
  return (value || '').toString().trim().replace(/[^A-Za-z0-9]/g, '').toLowerCase()
}

function normalizeSubjectValue(value: string | null | undefined) {
  return normalizeEntityValue((value || '').toString().replace(/^sub-?/i, ''))
}

// 唯一性以 (subject/session/task/run) 四元组为准，与后端 DATASET_EXISTS 的判重口径一致。
function entityTupleKey(subject: string, session?: string | null, task?: string | null, run?: string | null) {
  return [
    normalizeSubjectValue(subject),
    normalizeEntityValue(session),
    normalizeEntityValue(task),
    normalizeEntityValue(run),
  ].join('|')
}

function groupTupleKey(group: UploadGroup) {
  return entityTupleKey(group.subject, group.session, group.task, group.run)
}

function nextFreeSubject(taken: Set<string>, group: UploadGroup) {
  for (let n = 1; n < 1000; n += 1) {
    const candidate = String(n).padStart(2, '0')
    if (!taken.has(entityTupleKey(candidate, group.session, group.task, group.run))) return candidate
  }
  return String(Date.now())
}

function assignBatchSubjects(allGroups: UploadGroup[]) {
  const valid = allGroups.filter((group) => group.valid)
  if (!valid.length) {
    autoFillNote.value = ''
    return
  }

  // 第一步：对「文件名没带 sub- 标签」的多个文件，尝试按文件名差异抠出彼此区分的编号
  let touched = 0
  const anonymous = valid.filter((group) => !group.subject.trim())
  if (anonymous.length > 1) {
    const tokens = deriveDistinctTokens(anonymous.map(discriminatorSource))
    anonymous.forEach((group, index) => {
      if (tokens[index]) {
        group.subject = tokens[index]
        touched += 1
      }
    })
  }

  // 第二步：全批去重兜底 —— 任何与「库里已有」或「本批在前的组」相同的四元组，顺延到下一个空号
  const taken = new Set(existingTuples.value)
  for (const group of valid) {
    let key = groupTupleKey(group)
    if (!group.subject.trim() || taken.has(key)) {
      group.subject = nextFreeSubject(taken, group)
      touched += 1
      key = groupTupleKey(group)
    }
    taken.add(key)
  }

  autoFillNote.value = valid.length > 1 && touched
    ? '已按文件名自动区分被试编号（subject），避免互相覆盖、也尽量避开已导入的数据；如不准确可直接在下方逐个修改。'
    : ''
}

// 尽力把当前 study 下已有的 recordings 四元组捞回来，给自动分配避让。
// 口径必须与后端导入判重一致：后端按「同一研究项 (study) 内 subject/session/task/run 唯一」判重，
// 并不按 dataset_asset 细分（见 dataset_imports.py 的 DATASET_EXISTS）。所以这里也要收**全 study**
// 的记录、不再按当前数据集过滤——否则会漏掉「同 study、别的数据集」已占用的四元组，自动分配照样
// 发出会撞的编号，上传时才弹「已存在」。best-effort：拿不到就退化为「只保证本批内部不冲突」，
// 真撞了还有上传期 409 自动避让兜底。按 study 缓存，重复选文件不重复请求。
async function loadExistingRecordings(force = false) {
  const studyId = uploadStudyId.value
  if (!studyId) {
    existingTuples.value = new Set()
    existingRecordingsKey = ''
    return
  }
  if (!force && studyId === existingRecordingsKey) return
  try {
    const res = await datasetApi.list(studyId)
    const tuples = new Set<string>()
    for (const recording of res.data.recordings) {
      tuples.add(entityTupleKey(recording.bids_subject_id || recording.subject_id, recording.session, recording.task, recording.run))
    }
    existingTuples.value = tuples
    existingRecordingsKey = studyId
  } catch {
    // 忽略：退化为「只保证本批内部不冲突」，真撞了由上传期 409 自动避让兜底
  }
}

// 上传期把后端报回来的「已占用四元组」登记进避让集合，供本次重传与后续上传一起避开。
function registerOccupiedTuple(subject: string, session?: string | null, task?: string | null, run?: string | null) {
  const next = new Set(existingTuples.value)
  next.add(entityTupleKey(subject, session, task, run))
  existingTuples.value = next
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
    datasetFileCount: 0,
    canonicalFifGenerated: Boolean(recording?.fif_path),
    responseMessage: response.message || '已导入数据集工作版本',
  }
}

function getOutcomeItems(outcome: ImportOutcome) {
  return [
    {
      label: '导入结果',
      value: getOutcomeUserSummary(outcome),
    },
    {
      label: '原始文件',
      value: `已登记 ${outcome.originalFileCount} 个原始文件`,
    },
    {
      label: '标准化文件',
      value: outcome.canonicalFifGenerated ? '已生成或已登记' : '尚未返回生成状态，可能仍在转换',
    },
    {
      label: '文件清单',
      value: outcome.datasetFileCount
        ? `已返回 ${outcome.datasetFileCount} 条文件清单`
        : '本次上传未返回清单详情',
    },
  ]
}

function getOutcomeUserSummary(outcome: ImportOutcome) {
  const fifText = outcome.canonicalFifGenerated ? '已生成标准化文件' : '标准化文件状态待确认'
  const fileIndexText = outcome.datasetFileCount ? '文件清单已更新' : '文件清单待查询'
  return `已导入；${fifText}；${fileIndexText}`
}

async function uploadGroup(group: UploadGroup, replaceExisting = false, autoAdaptDepth = 0): Promise<'success' | 'duplicate' | 'failed'> {
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
  group.speedBps = undefined
  group.statusText = '正在上传原始数据'
  group.message = ''
  group.outcome = null

  // 实时上传速度：用相邻两次进度回调之间的「字节增量 / 时间增量」估算，并做指数平滑以防抖动
  let lastLoaded = 0
  let lastSampleTime = nowMs()
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
        onProgress: (percent, loaded) => {
          group.progress = percent
          const now = nowMs()
          const elapsed = (now - lastSampleTime) / 1000
          // 至少间隔 200ms 再采样一次，避免高频回调把速度算得忽高忽低
          if (elapsed >= 0.2) {
            const delta = loaded - lastLoaded
            if (delta >= 0 && elapsed > 0) {
              const instantBps = delta / elapsed
              group.speedBps = group.speedBps ? group.speedBps * 0.6 + instantBps * 0.4 : instantBps
            }
            lastLoaded = loaded
            lastSampleTime = now
          }
          if (group.status !== 'processing') {
            group.status = 'uploading'
            group.statusText = '正在上传原始数据'
          }
        },
        onUploadComplete: () => {
          group.status = 'processing'
          group.progress = 100
          group.speedBps = undefined
          group.statusText = '上传完成，正在整理与标准化'
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
      // 撞到「同 study 已存在的四元组」。用户诉求是「上传即新数据、自动避开重叠」，所以默认不弹
      // 「覆盖为新版本」，而是把这条已占用的四元组登记下来、被试号顺延到下一个空号后自动重传，
      // 直到避开后端 study 级判重。仅当连续多次仍撞（极端并发）才回退到弹窗，把选择权交还用户。
      registerOccupiedTuple(existsDetail.subject, existsDetail.session, existsDetail.task, existsDetail.run)
      if (autoAdaptDepth < MAX_AUTO_ADAPT_RETRIES) {
        const previousSubject = group.subject
        group.subject = nextFreeSubject(new Set(existingTuples.value), group)
        autoFillNote.value = `「被试 ${previousSubject}·${group.task}」在本研究项已存在，已自动改用被试 ${group.subject} 上传以避免覆盖；如需调整可在表格中修改。`
        return uploadGroup(group, false, autoAdaptDepth + 1)
      }
      group.status = 'replace-pending'
      group.progress = 0
      group.statusText = '等待确认'
      group.message = '该数据位已存在，且自动避让多次仍冲突，请确认是否作为新一次数据（版本）导入。'
      group.selected = false
      group.outcome = null
      group.existsDetail = existsDetail
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
    globalSuccess.value = `已成功导入 ${successCount} 份数据到当前数据集`
    emit('uploaded')
    void loadExistingRecordings(true)
  }
  if (duplicateCount) {
    globalError.value = '有 Recording 已经存在，请在弹窗中确认是否新增原始上传版本并切换当前指针'
  }
  if (failCount) {
    globalError.value = `${failCount} 份导入失败，请查看对应红色提示后重试`
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

function openReplaceConfirm(group: UploadGroup) {
  replaceCandidate.value = group
  replaceDetail.value = group.existsDetail
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
      void loadExistingRecordings(true)
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
