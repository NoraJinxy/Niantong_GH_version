<template>
  <div class="load-data-panel-v2">
    <!-- 加载/错误状态 -->
    <div v-if="loading" class="state-text">正在读取研究项数据...</div>
    <div v-else-if="error" class="state-text state-text--error">{{ error }}</div>
    <div v-else-if="!studyDatasets.length" class="state-text">当前研究项还没有可用数据。</div>

    <template v-else>
      <!-- 主体：横向两栏 -->
      <div class="ldp-main">

        <!-- 左栏：Tab + 搜索 + Include + Exclude -->
        <div class="ldp-rules-col">

          <div class="ldp-tabbar">
            <button
              v-for="tab in TABS"
              :key="tab.key"
              class="ldp-tab"
              :class="{ 'is-active': currentTab === tab.key }"
              type="button"
              @click="switchTab(tab.key)"
            >
              <span>{{ tab.label }}</span>
              <span v-if="ruleCount(tab.key) > 0" class="ldp-tab-badge">{{ ruleCount(tab.key) }}</span>
            </button>
          </div>

          <div class="ldp-search">
            <input
              v-model="filterText"
              class="control"
              type="search"
              :placeholder="filterPlaceholder"
            />
          </div>

          <!-- Include listbox -->
          <div class="ldp-rule-section ldp-rule-section--include">
            <div class="ldp-rule-header">
              <strong><IconLine name="check" :size="11" /> Include</strong>
              <span class="ldp-rule-count">{{ currentIncludes.size }}</span>
              <button
                v-if="currentIncludes.size > 0"
                type="button"
                class="ldp-clear-btn"
                @click="clearInclude"
              >清空</button>
            </div>
            <div
              ref="includeListRef"
              class="ldp-listbox"
              tabindex="0"
              @keydown="handleListKeydown($event, 'include')"
            >
              <div v-if="!visibleCandidates.length" class="ldp-empty-hint">
                {{ filterText.trim() ? '无匹配项' : '无候选项' }}
              </div>
              <div
                v-for="(item, idx) in visibleCandidates"
                :key="'inc-' + item"
                class="ldp-list-item"
                :class="{
                  'is-selected': currentIncludes.has(item),
                  'is-disabled': currentExcludes.has(item),
                }"
                @click="handleListClick($event, 'include', idx, item)"
              >
                {{ item }}
              </div>
            </div>
          </div>

          <!-- Exclude listbox -->
          <div class="ldp-rule-section ldp-rule-section--exclude">
            <div class="ldp-rule-header">
              <strong><IconLine name="x" :size="11" /> Exclude</strong>
              <span class="ldp-rule-count">{{ currentExcludes.size }}</span>
              <button
                v-if="currentExcludes.size > 0"
                type="button"
                class="ldp-clear-btn"
                @click="clearExclude"
              >清空</button>
            </div>
            <div
              ref="excludeListRef"
              class="ldp-listbox"
              tabindex="0"
              @keydown="handleListKeydown($event, 'exclude')"
            >
              <div v-if="!visibleCandidates.length" class="ldp-empty-hint">
                {{ filterText.trim() ? '无匹配项' : '无候选项' }}
              </div>
              <div
                v-for="(item, idx) in visibleCandidates"
                :key="'exc-' + item"
                class="ldp-list-item"
                :class="{
                  'is-selected': currentExcludes.has(item),
                  'is-disabled': currentIncludes.has(item),
                }"
                @click="handleListClick($event, 'exclude', idx, item)"
              >
                {{ item }}
              </div>
            </div>
          </div>

        </div>

        <!-- 右栏：文件列表 -->
        <div class="ldp-files-col">
          <div class="ldp-files-section">
            <div class="ldp-section-header">
              <strong>文件列表</strong>
              <span class="ldp-section-count">{{ hitFiles.length }} 条</span>
              <select v-model="groupByMode" class="ldp-group-select">
                <option value="none">不分组</option>
                <option value="subject">按被试</option>
                <option value="task">按任务</option>
                <option value="session">按 Session</option>
              </select>
            </div>
            <div
              ref="fileListRef"
              class="ldp-files-content"
              tabindex="0"
              @keydown="handleFileListKeydown"
            >
              <div v-if="!hitFiles.length" class="ldp-empty-hint">无命中文件</div>
              <template v-for="group in groupedHitFiles" :key="group.name">
                <div v-if="groupByMode !== 'none'" class="ldp-file-group-header">
                  <span><IconLine name="chevronDown" :size="11" /> {{ group.name }}</span>
                  <span class="ldp-group-count">{{ group.files.length }} 条</span>
                </div>
                <div
                  v-for="file in group.files"
                  :key="'f-' + file.id"
                  class="ldp-file-item"
                  :class="{
                    'is-selected': fileListSelected.has(file.id),
                    'is-in-selected': selectedFileIds.includes(file.id),
                    'is-flat': groupByMode === 'none',
                  }"
                  @click="handleFileListClick($event, file.id)"
                >
                  {{ file.name }}
                </div>
              </template>
            </div>
            <div class="ldp-file-actions">
              <span class="ldp-file-hint">{{ fileListSelected.size }} 已勾选</span>
              <button
                v-if="hitFiles.length > 0 && fileListSelected.size === 0"
                type="button"
                class="ldp-action-btn"
                :disabled="!hitFiles.length"
                title="把命中的全部文件放入 Selected"
                @click="addAllHitToSelected"
              ><IconLine name="chevronDown" :size="12" /> 全部放入</button>
              <button
                type="button"
                class="ldp-action-btn ldp-action-btn--primary"
                :disabled="!fileListSelected.size"
                @click="addToSelected"
              ><IconLine name="chevronDown" :size="12" /> 放入 Selected</button>
            </div>
          </div>
        </div>

      </div>

      <!-- 底部 Selected File 区（横跨）—— LoadData 节点真正输出的数据集 -->
      <div class="ldp-selected-section" :class="{ 'is-empty-required': selectedFiles.length === 0 }">
        <div class="ldp-section-header">
          <strong>Selected File</strong>
          <span class="ldp-section-count">{{ selectedFiles.length }} 条</span>
          <span v-if="selectedFiles.length === 0" class="ldp-required-flag">必须 ≥ 1 才能运行</span>
          <div class="ldp-icon-actions">
            <button
              type="button"
              class="ldp-icon-btn"
              title="上移选中项"
              :disabled="!selectedListSelected.size"
              @click="moveSelectedUp"
            ><IconLine name="chevronUp" :size="14" /></button>
            <button
              type="button"
              class="ldp-icon-btn"
              title="下移选中项"
              :disabled="!selectedListSelected.size"
              @click="moveSelectedDown"
            ><IconLine name="chevronDown" :size="14" /></button>
            <button
              type="button"
              class="ldp-icon-btn ldp-icon-btn--danger"
              title="删除选中项 (Delete)"
              :disabled="!selectedListSelected.size"
              @click="deleteSelectedItems"
            ><IconLine name="trash" :size="14" /></button>
            <button
              type="button"
              class="ldp-icon-btn ldp-icon-btn--danger"
              title="清空全部"
              :disabled="!selectedFiles.length"
              @click="clearAllSelected"
            ><IconLine name="x" :size="14" /></button>
          </div>
        </div>
        <div
          ref="selectedListRef"
          class="ldp-selected-list"
          tabindex="0"
          @keydown="handleSelectedListKeydown"
        >
          <div v-if="!selectedFiles.length" class="ldp-empty-hint ldp-empty-hint--required">
            请从上方文件列表勾选并点「放入 Selected」 —— 这里的文件才是 LoadData 真正加载的数据
          </div>
          <div
            v-for="(file, idx) in selectedFiles"
            :key="'s-' + file.id"
            class="ldp-selected-item"
            :class="{ 'is-selected': selectedListSelected.has(file.id) }"
            @click="handleSelectedListClick($event, idx, file.id)"
          >
            <span class="ldp-selected-idx">{{ String(idx + 1).padStart(3, ' ') }}</span>
            <span class="ldp-selected-name">{{ file.name }}</span>
          </div>
        </div>
      </div>

      <p class="ldp-hint">
        单击切换 · Shift+单击范围选 · Ctrl+单击切换 · Ctrl+A 全选 · Delete 移除已选
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import IconLine from './IconLine.vue'
import type { Recording } from '@/types'

// === 类型 ===
type FilterListValue<T extends string = string> = 'all' | T[]

interface LoadDataFilter {
  subjects: FilterListValue
  sessions: FilterListValue
  tasks: FilterListValue
  runs: FilterListValue
  qa_status: FilterListValue
  require_fif?: boolean
  dataset_asset_id?: string | null
  dataset_asset_ids?: FilterListValue
  mount_id?: string | null
  // UI 状态持久化字段（explicit 模式下后端不读，仅用于面板重开时恢复 exclude 选择）
  _ui_exclude_subjects?: string[]
  _ui_exclude_sessions?: string[]
  _ui_exclude_tasks?: string[]
  _ui_exclude_runs?: string[]
}

interface LoadDataParams {
  selection_mode: 'filter' | 'explicit'
  dataset_filter: LoadDataFilter
  dataset_ids: string[]
}

type TabKey = 'subject' | 'exp'
type GroupMode = 'subject' | 'task' | 'session' | 'none'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'subject', label: '被试' },
  { key: 'exp', label: '实验' },
]

interface Props {
  studyDatasets: Recording[]
  modelValue: LoadDataParams
  loading?: boolean
  error?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  error: '',
})

const emit = defineEmits<{
  'update:modelValue': [params: LoadDataParams]
}>()

const currentTab = ref<TabKey>('subject')
const filterText = ref('')
const groupByMode = ref<GroupMode>('none')

const includes = ref({
  subject: new Set<string>(),
  exp: new Set<string>(),
})
const excludes = ref({
  subject: new Set<string>(),
  exp: new Set<string>(),
})

const selectedFileIds = ref<string[]>([])
const fileListSelected = ref<Set<string>>(new Set())
const selectedListSelected = ref<Set<string>>(new Set())

const includeListRef = ref<HTMLDivElement | null>(null)
const excludeListRef = ref<HTMLDivElement | null>(null)
const fileListRef = ref<HTMLDivElement | null>(null)
const selectedListRef = ref<HTMLDivElement | null>(null)

let lastIncludeIndex = -1
let lastExcludeIndex = -1
let lastFileListIndex = -1
let lastSelectedListIndex = -1
let suspendEmit = false

// === 候选项 ===
const candidatesBySubject = computed<string[]>(() => {
  const set = new Set<string>()
  for (const d of props.studyDatasets) {
    if (d.bids_subject_id) set.add(d.bids_subject_id)
  }
  return [...set].sort()
})

const candidatesByExp = computed<string[]>(() => {
  const set = new Set<string>()
  for (const d of props.studyDatasets) {
    if (d.task) set.add(`task:${d.task}`)
    if (d.session) set.add(`ses:${d.session}`)
    if (d.run) set.add(`run:${d.run}`)
  }
  return [...set].sort((a, b) => {
    const ka = a.split(':')[0]
    const kb = b.split(':')[0]
    const order: Record<string, number> = { task: 0, ses: 1, run: 2 }
    const oa = order[ka] ?? 99
    const ob = order[kb] ?? 99
    if (oa !== ob) return oa - ob
    return a.localeCompare(b)
  })
})

const candidatesByTag = computed<string[]>(() => [])

const allCandidates = computed<string[]>(() => {
  if (currentTab.value === 'subject') return candidatesBySubject.value
  if (currentTab.value === 'exp') return candidatesByExp.value
  return candidatesByTag.value
})

const visibleCandidates = computed<string[]>(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) return allCandidates.value
  return allCandidates.value.filter((item) => item.toLowerCase().includes(q))
})

const currentIncludes = computed<Set<string>>(() => includes.value[currentTab.value])
const currentExcludes = computed<Set<string>>(() => excludes.value[currentTab.value])

const filterPlaceholder = computed(() => {
  if (currentTab.value === 'subject') return '过滤被试...'
  return '过滤实验维度...'
})

// === 筛选逻辑 (同 Tab OR + 跨 Tab AND) ===
const filteredDatasets = computed<Recording[]>(() => {
  return props.studyDatasets.filter((dataset) => {
    const sub = dataset.bids_subject_id || ''
    if (includes.value.subject.size > 0 && !includes.value.subject.has(sub)) return false
    if (excludes.value.subject.has(sub)) return false

    const expTags: string[] = []
    if (dataset.task) expTags.push(`task:${dataset.task}`)
    if (dataset.session) expTags.push(`ses:${dataset.session}`)
    if (dataset.run) expTags.push(`run:${dataset.run}`)

    if (includes.value.exp.size > 0) {
      const byKind: Record<string, string[]> = { task: [], ses: [], run: [] }
      for (const t of includes.value.exp) {
        const [k] = t.split(':')
        if (byKind[k]) byKind[k].push(t)
      }
      for (const kind of ['task', 'ses', 'run']) {
        const list = byKind[kind]
        if (list.length === 0) continue
        if (!list.some((tag) => expTags.includes(tag))) return false
      }
    }

    if (excludes.value.exp.size > 0) {
      if (expTags.some((t) => excludes.value.exp.has(t))) return false
    }

    return true
  })
})

// === 命中文件 ===
function bidsFileName(d: Recording): string {
  // 后端存的 BIDS 实体本就带前缀（sub- / ses- / task- / run-），直接拼即可，别再补前缀（否则 ses-ses-b…）。
  const parts: string[] = []
  if (d.bids_subject_id) parts.push(d.bids_subject_id)
  if (d.session) parts.push(d.session)
  if (d.task) parts.push(d.task)
  if (d.run) parts.push(d.run)
  return `${parts.join('_')}_eeg.fif`
}

interface HitFile {
  id: string
  name: string
  dataset: Recording
}

const hitFiles = computed<HitFile[]>(() => {
  return filteredDatasets.value.map((d) => ({
    id: d.id,
    name: bidsFileName(d),
    dataset: d,
  }))
})

interface FileGroup {
  name: string
  files: HitFile[]
}

const groupedHitFiles = computed<FileGroup[]>(() => {
  const mode = groupByMode.value
  if (mode === 'none') {
    return [{ name: '全部', files: hitFiles.value }]
  }
  const groups = new Map<string, HitFile[]>()
  for (const f of hitFiles.value) {
    let key: string
    if (mode === 'subject') key = f.dataset.bids_subject_id || '(无被试)'
    else if (mode === 'task') key = f.dataset.task || '(无任务)'
    else key = f.dataset.session || '(无 session)'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(f)
  }
  return [...groups.entries()]
    .map(([name, files]) => ({ name, files }))
    .sort((a, b) => a.name.localeCompare(b.name))
})

const flatFileIds = computed<string[]>(() => {
  const ids: string[] = []
  for (const g of groupedHitFiles.value) {
    for (const f of g.files) ids.push(f.id)
  }
  return ids
})

function getFlatIndex(id: string): number {
  return flatFileIds.value.indexOf(id)
}

// === Selected ===
const selectedFiles = computed<HitFile[]>(() => {
  const hitMap = new Map<string, HitFile>()
  for (const f of hitFiles.value) hitMap.set(f.id, f)
  return selectedFileIds.value.map((id) => {
    const found = hitMap.get(id)
    if (found) return found
    return { id, name: id, dataset: {} as Recording }
  })
})

// === Tab / 计数 ===
function switchTab(key: TabKey) {
  if (currentTab.value === key) return
  currentTab.value = key
  filterText.value = ''
  lastIncludeIndex = -1
  lastExcludeIndex = -1
}

function ruleCount(tab: TabKey): number {
  return includes.value[tab].size + excludes.value[tab].size
}

// === 规则 listbox 多选 ===
function handleListClick(
  e: MouseEvent,
  kind: 'include' | 'exclude',
  idx: number,
  id: string,
) {
  const targetSet = kind === 'include' ? currentIncludes.value : currentExcludes.value
  const otherSet = kind === 'include' ? currentExcludes.value : currentIncludes.value
  if (otherSet.has(id)) return

  const listEl = kind === 'include' ? includeListRef.value : excludeListRef.value
  listEl?.focus()

  const lastIdx = kind === 'include' ? lastIncludeIndex : lastExcludeIndex
  if (e.shiftKey && lastIdx >= 0) {
    const [start, end] = [Math.min(lastIdx, idx), Math.max(lastIdx, idx)]
    for (let i = start; i <= end; i++) {
      const itemId = visibleCandidates.value[i]
      if (!itemId || otherSet.has(itemId)) continue
      targetSet.add(itemId)
    }
  } else {
    if (targetSet.has(id)) targetSet.delete(id)
    else targetSet.add(id)
  }
  if (kind === 'include') lastIncludeIndex = idx
  else lastExcludeIndex = idx

  triggerSetMutation()
  emitChange()
}

function handleListKeydown(e: KeyboardEvent, kind: 'include' | 'exclude') {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
    e.preventDefault()
    const targetSet = kind === 'include' ? currentIncludes.value : currentExcludes.value
    const otherSet = kind === 'include' ? currentExcludes.value : currentIncludes.value
    for (const id of visibleCandidates.value) {
      if (otherSet.has(id)) continue
      targetSet.add(id)
    }
    triggerSetMutation()
    emitChange()
  }
}

function triggerSetMutation() {
  includes.value = {
    subject: new Set(includes.value.subject),
    exp: new Set(includes.value.exp),
  }
  excludes.value = {
    subject: new Set(excludes.value.subject),
    exp: new Set(excludes.value.exp),
  }
}

function clearInclude() {
  includes.value[currentTab.value] = new Set()
  triggerSetMutation()
  emitChange()
}

function clearExclude() {
  excludes.value[currentTab.value] = new Set()
  triggerSetMutation()
  emitChange()
}

// === 文件列表多选 ===
function handleFileListClick(e: MouseEvent, id: string) {
  fileListRef.value?.focus()
  const idx = getFlatIndex(id)

  if (e.shiftKey && lastFileListIndex >= 0) {
    const [start, end] = [Math.min(lastFileListIndex, idx), Math.max(lastFileListIndex, idx)]
    for (let i = start; i <= end; i++) {
      fileListSelected.value.add(flatFileIds.value[i])
    }
  } else if (e.ctrlKey || e.metaKey) {
    if (fileListSelected.value.has(id)) fileListSelected.value.delete(id)
    else fileListSelected.value.add(id)
  } else {
    fileListSelected.value.clear()
    fileListSelected.value.add(id)
  }
  lastFileListIndex = idx
  fileListSelected.value = new Set(fileListSelected.value)
}

function handleFileListKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
    e.preventDefault()
    fileListSelected.value = new Set(flatFileIds.value)
  }
}

function addToSelected() {
  if (!fileListSelected.value.size) return
  const newIds: string[] = []
  for (const id of fileListSelected.value) {
    if (!selectedFileIds.value.includes(id)) newIds.push(id)
  }
  if (!newIds.length) return
  selectedFileIds.value = [...selectedFileIds.value, ...newIds]
  fileListSelected.value = new Set()
  emitChange()
}

/** 一键把所有命中文件加入 Selected —— 常见场景：用户已经用 Include/Exclude 过滤好，
 *  不想再手动 Ctrl+A 多一步。 */
function addAllHitToSelected() {
  if (!hitFiles.value.length) return
  const newIds: string[] = []
  for (const file of hitFiles.value) {
    if (!selectedFileIds.value.includes(file.id)) newIds.push(file.id)
  }
  if (!newIds.length) return
  selectedFileIds.value = [...selectedFileIds.value, ...newIds]
  emitChange()
}

// === Selected 列表多选 ===
function handleSelectedListClick(e: MouseEvent, idx: number, id: string) {
  selectedListRef.value?.focus()
  if (e.shiftKey && lastSelectedListIndex >= 0) {
    const [start, end] = [Math.min(lastSelectedListIndex, idx), Math.max(lastSelectedListIndex, idx)]
    for (let i = start; i <= end; i++) {
      selectedListSelected.value.add(selectedFileIds.value[i])
    }
  } else if (e.ctrlKey || e.metaKey) {
    if (selectedListSelected.value.has(id)) selectedListSelected.value.delete(id)
    else selectedListSelected.value.add(id)
  } else {
    selectedListSelected.value.clear()
    selectedListSelected.value.add(id)
  }
  lastSelectedListIndex = idx
  selectedListSelected.value = new Set(selectedListSelected.value)
}

function handleSelectedListKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
    e.preventDefault()
    selectedListSelected.value = new Set(selectedFileIds.value)
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    e.preventDefault()
    deleteSelectedItems()
  }
}

function moveSelectedUp() {
  if (!selectedListSelected.value.size) return
  const indices = [...selectedListSelected.value]
    .map((id) => selectedFileIds.value.indexOf(id))
    .filter((i) => i >= 0)
    .sort((a, b) => a - b)
  if (!indices.length || indices[0] === 0) return
  const next = [...selectedFileIds.value]
  for (const idx of indices) {
    ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
  }
  selectedFileIds.value = next
  emitChange()
}

function moveSelectedDown() {
  if (!selectedListSelected.value.size) return
  const indices = [...selectedListSelected.value]
    .map((id) => selectedFileIds.value.indexOf(id))
    .filter((i) => i >= 0)
    .sort((a, b) => b - a)
  if (!indices.length || indices[0] === selectedFileIds.value.length - 1) return
  const next = [...selectedFileIds.value]
  for (const idx of indices) {
    ;[next[idx + 1], next[idx]] = [next[idx], next[idx + 1]]
  }
  selectedFileIds.value = next
  emitChange()
}

function deleteSelectedItems() {
  if (!selectedListSelected.value.size) return
  selectedFileIds.value = selectedFileIds.value.filter(
    (id) => !selectedListSelected.value.has(id),
  )
  selectedListSelected.value = new Set()
  emitChange()
}

function clearAllSelected() {
  if (!selectedFileIds.value.length) return
  if (!window.confirm(`确定清空 ${selectedFileIds.value.length} 个已选文件？`)) return
  selectedFileIds.value = []
  selectedListSelected.value = new Set()
  emitChange()
}

// === 与 modelValue 双向同步 ===
function emitChange() {
  if (suspendEmit) return
  // 计算当前 Include 过滤状态，保存到 dataset_filter（让切回页面能恢复 listbox 状态）。
  // 但这个 filter 不再参与"自动加载全部命中" —— Selected File 才是 LoadData 真正的输出。
  const subjects: FilterListValue =
    includes.value.subject.size > 0 ? [...includes.value.subject] : 'all'
  const sessions: FilterListValue = (() => {
    const v = [...includes.value.exp]
      .filter((t) => t.startsWith('ses:'))
      .map((t) => t.slice(4))
    return v.length ? v : 'all'
  })()
  const tasks: FilterListValue = (() => {
    const v = [...includes.value.exp]
      .filter((t) => t.startsWith('task:'))
      .map((t) => t.slice(5))
    return v.length ? v : 'all'
  })()
  const runs: FilterListValue = (() => {
    const v = [...includes.value.exp]
      .filter((t) => t.startsWith('run:'))
      .map((t) => t.slice(4))
    return v.length ? v : 'all'
  })()

  // 保存 exclude 状态（后端在 explicit 模式下不读这些字段，仅用于面板重开时 UI 恢复）
  const _ui_exclude_subjects = [...excludes.value.subject]
  const _ui_exclude_sessions = [...excludes.value.exp]
    .filter((t) => t.startsWith('ses:'))
    .map((t) => t.slice(4))
  const _ui_exclude_tasks = [...excludes.value.exp]
    .filter((t) => t.startsWith('task:'))
    .map((t) => t.slice(5))
  const _ui_exclude_runs = [...excludes.value.exp]
    .filter((t) => t.startsWith('run:'))
    .map((t) => t.slice(4))

  // 永远走 explicit 模式 —— Selected File 列表 = LoadData 真正的输出集合
  // Selected File 空 → dataset_ids 空 → 后端 validator 报 LOAD_DATA_DATASET_IDS_REQUIRED
  emit('update:modelValue', {
    selection_mode: 'explicit',
    dataset_filter: {
      ...props.modelValue.dataset_filter,
      subjects,
      sessions,
      tasks,
      runs,
      _ui_exclude_subjects,
      _ui_exclude_sessions,
      _ui_exclude_tasks,
      _ui_exclude_runs,
    },
    dataset_ids: [...selectedFileIds.value],
  })
}

function restoreStateFromParams(params: LoadDataParams) {
  suspendEmit = true
  try {
    includes.value = {
      subject: new Set<string>(),
      exp: new Set<string>(),
    }
    excludes.value = {
      subject: new Set<string>(),
      exp: new Set<string>(),
    }
    selectedFileIds.value = []
    fileListSelected.value = new Set()
    selectedListSelected.value = new Set()

    // 无论 filter 还是 explicit 模式，dataset_filter 里都存了 include 状态
    const f = params.dataset_filter
    if (Array.isArray(f.subjects)) {
      for (const s of f.subjects) includes.value.subject.add(s)
    }
    if (Array.isArray(f.sessions)) {
      for (const s of f.sessions) includes.value.exp.add(`ses:${s}`)
    }
    if (Array.isArray(f.tasks)) {
      for (const t of f.tasks) includes.value.exp.add(`task:${t}`)
    }
    if (Array.isArray(f.runs)) {
      for (const r of f.runs) includes.value.exp.add(`run:${r}`)
    }

    // 恢复 exclude 状态（_ui_exclude_* 字段）
    if (Array.isArray(f._ui_exclude_subjects)) {
      for (const s of f._ui_exclude_subjects) excludes.value.subject.add(s)
    }
    if (Array.isArray(f._ui_exclude_sessions)) {
      for (const s of f._ui_exclude_sessions) excludes.value.exp.add(`ses:${s}`)
    }
    if (Array.isArray(f._ui_exclude_tasks)) {
      for (const t of f._ui_exclude_tasks) excludes.value.exp.add(`task:${t}`)
    }
    if (Array.isArray(f._ui_exclude_runs)) {
      for (const r of f._ui_exclude_runs) excludes.value.exp.add(`run:${r}`)
    }

    if (params.dataset_ids && params.dataset_ids.length > 0) {
      selectedFileIds.value = [...params.dataset_ids]
    }
    triggerSetMutation()
  } finally {
    suspendEmit = false
  }
}

watch(
  () => props.modelValue,
  (params) => {
    if (params) restoreStateFromParams(params)
  },
  { immediate: true },
)
</script>

<style scoped>
.load-data-panel-v2 {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  flex: 1;
}

.state-text {
  padding: 12px;
  color: var(--c-text-3);
  font-size: 12px;
}
.state-text--error {
  color: var(--c-danger, #c44);
}

/* 主体两栏 */
.ldp-main {
  display: flex;
  flex: 1;
  min-height: 240px;
  max-height: 480px;
  gap: 6px;
  overflow: hidden;
}

.ldp-rules-col {
  width: 150px;
  min-width: 130px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.ldp-files-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* Tab */
.ldp-tabbar {
  display: flex;
  padding: 2px;
  background: var(--c-bg-tint, rgba(0, 0, 0, 0.04));
  border-radius: 6px;
  gap: 2px;
  flex-shrink: 0;
}
.ldp-tab {
  flex: 1;
  padding: 3px 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 11px;
  color: var(--c-text-3);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  min-width: 0;
}
.ldp-tab:hover:not(.is-active) { color: var(--c-text); }
.ldp-tab.is-active {
  background: var(--c-surface, #fff);
  color: var(--c-primary);
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.ldp-tab-badge {
  background: var(--c-primary);
  color: #fff;
  font-size: 9px;
  padding: 0 4px;
  border-radius: 8px;
  min-width: 14px;
  text-align: center;
}

/* 搜索框 */
.ldp-search { flex-shrink: 0; }
.ldp-search .control {
  width: 100%;
  padding: 4px 6px;
  font-size: 11px;
  min-height: 24px;
  border: 1px solid var(--c-border);
  border-radius: 4px;
  background: var(--c-bg-tint);
  color: var(--c-text);
  outline: none;
}
.ldp-search .control:focus { border-color: var(--c-primary); }

/* 规则区 */
.ldp-rule-section {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  overflow: hidden;
  flex: 1;
  min-height: 80px;
}

.ldp-rule-header {
  padding: 3px 6px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
  border-bottom: 1px solid var(--c-border);
}

.ldp-rule-section--include .ldp-rule-header {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.ldp-rule-section--exclude .ldp-rule-header {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.ldp-rule-count {
  font-size: 9px;
  padding: 0 4px;
  background: var(--c-surface, #fff);
  border-radius: 8px;
  font-weight: 500;
  min-width: 16px;
  text-align: center;
}

.ldp-clear-btn {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
  font-size: 9px;
  text-decoration: underline;
  padding: 0;
  margin-left: auto;
}
.ldp-clear-btn:hover { opacity: 1; }

.ldp-listbox {
  flex: 1;
  overflow-y: auto;
  background: var(--c-surface, #fff);
  outline: none;
  transition: background 0.18s, box-shadow 0.18s;
}

.ldp-rule-section--include .ldp-listbox:focus {
  box-shadow: inset 3px 0 0 #10b981;
  background: linear-gradient(to right, rgba(16, 185, 129, 0.05), transparent 60%);
}
.ldp-rule-section--exclude .ldp-listbox:focus {
  box-shadow: inset 3px 0 0 #ef4444;
  background: linear-gradient(to right, rgba(239, 68, 68, 0.05), transparent 60%);
}

.ldp-list-item {
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  user-select: none;
  border-left: 3px solid transparent;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ldp-list-item:hover:not(.is-disabled) {
  background: var(--c-bg-tint, rgba(0, 0, 0, 0.04));
}

.ldp-rule-section--include .ldp-list-item.is-selected {
  background: rgba(16, 185, 129, 0.16);
  color: #047857;
  border-left-color: #10b981;
  font-weight: 500;
}
.ldp-rule-section--exclude .ldp-list-item.is-selected {
  background: rgba(239, 68, 68, 0.16);
  color: #b91c1c;
  border-left-color: #ef4444;
  font-weight: 500;
}

.ldp-list-item.is-disabled {
  color: var(--c-text-3);
  cursor: not-allowed;
  font-style: italic;
  opacity: 0.55;
}
.ldp-list-item.is-disabled:hover { background: transparent; }

.ldp-empty-hint {
  padding: 12px 10px;
  font-size: 11px;
  color: var(--c-text-3);
  text-align: center;
  font-style: italic;
}

/* Selected File 空时的醒目提示 —— 用户必须从上面挑文件加入这里 */
.ldp-empty-hint--required {
  padding: 16px 14px;
  font-size: 12px;
  color: #b45309;
  font-style: normal;
  font-weight: 500;
  line-height: 1.6;
}

.ldp-selected-section.is-empty-required {
  border-color: rgba(245, 158, 11, 0.45);
  border-style: dashed;
  background: rgba(245, 158, 11, 0.03);
}

.ldp-required-flag {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  color: #b45309;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.35);
}

.ldp-coming-hint {
  padding: 6px 8px;
  font-size: 10px;
  color: var(--c-text-3);
  background: var(--c-bg-tint, rgba(0, 0, 0, 0.04));
  border-radius: 4px;
  border: 1px dashed var(--c-border);
}

/* 文件列表 */
.ldp-files-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  overflow: hidden;
  min-height: 0;
}

.ldp-section-header {
  padding: 4px 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--c-text-2);
  background: var(--c-bg-tint, rgba(0, 0, 0, 0.03));
  border-bottom: 1px solid var(--c-border);
  flex-shrink: 0;
}

.ldp-section-header strong {
  font-size: 12px;
  color: var(--c-text);
  font-weight: 600;
}

.ldp-section-count {
  font-size: 10px;
  padding: 0 6px;
  background: var(--c-surface, #fff);
  border-radius: 8px;
}

.ldp-group-select {
  margin-left: auto;
  padding: 1px 4px;
  font-size: 10px;
  border: 1px solid var(--c-border);
  border-radius: 3px;
  background: var(--c-surface);
  cursor: pointer;
}

.ldp-files-content {
  flex: 1;
  overflow: auto;
  background: var(--c-surface, #fff);
  outline: none;
  transition: background 0.18s, box-shadow 0.18s;
}

.ldp-files-content:focus {
  box-shadow: inset 3px 0 0 var(--c-primary);
  background: linear-gradient(to right, rgba(47, 95, 143, 0.04), transparent 60%);
}

.ldp-files-section:has(.ldp-files-content:focus) > .ldp-section-header {
  background: rgba(47, 95, 143, 0.08);
  color: var(--c-primary);
  box-shadow: inset 3px 0 0 var(--c-primary);
}

.ldp-file-group-header {
  padding: 3px 10px;
  background: var(--c-bg-tint, rgba(0, 0, 0, 0.04));
  font-size: 10px;
  color: var(--c-text-3);
  font-weight: 500;
  position: sticky;
  top: 0;
  left: 0;
  border-bottom: 1px solid var(--c-border);
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  min-width: 100%;
  width: max-content;
}

.ldp-file-group-header .ldp-group-count {
  margin-left: auto;
  color: var(--c-text-3);
}

.ldp-file-item {
  padding: 2px 8px 2px 20px;
  font-family: var(--ff-mono, "Consolas", "Monaco", monospace);
  font-size: 10px;
  cursor: pointer;
  user-select: none;
  border-left: 3px solid transparent;
  line-height: 1.6;
  white-space: nowrap;
  min-width: max-content;
}

/* 平铺模式：没有分组头，文件名贴左对齐，去掉为缩进留的左 padding */
.ldp-file-item.is-flat {
  padding-left: 10px;
}

.ldp-file-item:hover {
  background: var(--c-bg-tint, rgba(0, 0, 0, 0.04));
}

.ldp-file-item.is-selected {
  background: rgba(47, 95, 143, 0.16);
  border-left-color: var(--c-primary);
}

.ldp-file-item.is-in-selected {
  color: var(--c-primary);
  font-weight: 500;
}
.ldp-file-item.is-in-selected::after {
  content: "";
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-left: 6px;
  border-radius: 50%;
  background: #10b981;
  vertical-align: middle;
}

.ldp-file-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  border-top: 1px solid var(--c-border);
  background: var(--c-bg-tint, rgba(0, 0, 0, 0.03));
  flex-shrink: 0;
}

.ldp-file-hint {
  font-size: 10px;
  color: var(--c-text-3);
}

.ldp-action-btn {
  margin-left: auto;
  padding: 3px 8px;
  font-size: 11px;
  border: 1px solid var(--c-border);
  background: var(--c-surface);
  color: var(--c-text);
  border-radius: 3px;
  cursor: pointer;
  white-space: nowrap;
}
.ldp-action-btn:hover:not(:disabled) {
  background: var(--c-bg-tint);
  border-color: var(--c-primary);
  color: var(--c-primary);
}
.ldp-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ldp-action-btn--primary {
  background: var(--c-primary);
  color: #fff;
  border-color: var(--c-primary);
}
.ldp-action-btn--primary:hover:not(:disabled) {
  background: var(--c-primary-dark, #234e7c);
  color: #fff;
}

/* Selected File 区（横跨底部）*/
.ldp-selected-section {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  min-height: 100px;
  max-height: 180px;
}

.ldp-icon-actions {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.ldp-icon-btn {
  width: 22px;
  height: 22px;
  border: 1px solid var(--c-border);
  background: var(--c-surface);
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
  color: var(--c-text-2);
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.ldp-icon-btn:hover:not(:disabled) {
  background: var(--c-bg-tint);
  color: var(--c-text);
}
.ldp-icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.ldp-icon-btn--danger:hover:not(:disabled) {
  color: #ef4444;
  border-color: #ef4444;
}

.ldp-selected-list {
  flex: 1;
  overflow: auto;
  background: var(--c-surface, #fff);
  outline: none;
  transition: background 0.18s, box-shadow 0.18s;
}

.ldp-selected-list:focus {
  box-shadow: inset 3px 0 0 var(--c-primary);
  background: linear-gradient(to right, rgba(47, 95, 143, 0.04), transparent 60%);
}

.ldp-selected-section:has(.ldp-selected-list:focus) > .ldp-section-header {
  background: rgba(47, 95, 143, 0.08);
  color: var(--c-primary);
  box-shadow: inset 3px 0 0 var(--c-primary);
}

.ldp-selected-item {
  padding: 2px 8px;
  font-family: var(--ff-mono, "Consolas", "Monaco", monospace);
  font-size: 10px;
  cursor: pointer;
  user-select: none;
  border-left: 3px solid transparent;
  line-height: 1.6;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  min-width: max-content;
}
.ldp-selected-item:hover {
  background: var(--c-bg-tint, rgba(0, 0, 0, 0.04));
}
.ldp-selected-item.is-selected {
  background: rgba(47, 95, 143, 0.16);
  border-left-color: var(--c-primary);
}
.ldp-selected-idx {
  color: var(--c-text-3);
  font-size: 9px;
  min-width: 22px;
}
.ldp-selected-name {
  white-space: nowrap;
}

.ldp-hint {
  margin: 2px 2px 0;
  font-size: 10px;
  color: var(--c-text-3);
  line-height: 1.4;
  flex-shrink: 0;
}
</style>
