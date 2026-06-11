<template>
  <div class="load-data-panel-v2">
    <!-- 加载/错误状态 -->
    <div v-if="loading" class="state-text">正在读取研究项数据...</div>
    <div v-else-if="error" class="state-text state-text--error">{{ error }}</div>
    <div v-else-if="!studyDatasets.length" class="state-text">当前研究项还没有可用数据。</div>

    <template v-else>
      <!-- 模式切换：动态筛选 vs 锁定列表 -->
      <div class="ldp-mode">
        <button
          type="button"
          class="ldp-mode-btn"
          :class="{ 'is-active': mode === 'filter' }"
          @click="setMode('filter')"
        >动态筛选</button>
        <button
          type="button"
          class="ldp-mode-btn"
          :class="{ 'is-active': mode === 'explicit' }"
          @click="setMode('explicit')"
        >锁定列表</button>
      </div>
      <p class="ldp-mode-hint">
        <template v-if="mode === 'filter'">按条件筛选，执行时实时匹配；数据集后续新增被试会自动纳入。</template>
        <template v-else>锁定当前匹配到的 {{ matched.length }} 条记录，之后数据集变化也不影响（用于复现某次分析）。</template>
      </p>

      <!-- 快捷场景 -->
      <div class="ldp-scenarios">
        <span class="ldp-scenarios-label">快捷：</span>
        <button type="button" class="ldp-chip-btn" @click="scenarioAll">全部数据</button>
        <button
          type="button"
          class="ldp-chip-btn"
          :disabled="!subjectOptions.length"
          @click="scenarioSingleSubject"
        >单被试·全条件</button>
        <button
          type="button"
          class="ldp-chip-btn"
          :disabled="!taskOptions.length"
          @click="scenarioAllSubjectsOneTask"
        >全被试·单任务</button>
      </div>

      <!-- 四个维度 -->
      <div class="ldp-dims">
        <div v-for="dim in DIMENSIONS" :key="dim.key" class="ldp-dim">
          <div class="ldp-dim-head">
            <strong>{{ dim.label }}</strong>
            <button
              type="button"
              class="ldp-all-btn"
              :class="{ 'is-active': isAll(dim.key) }"
              @click="clearDim(dim.key)"
            >全部</button>
          </div>
          <div v-if="!optionsOf(dim.key).length" class="ldp-empty-hint">无可选值</div>
          <div v-else class="ldp-chips">
            <button
              v-for="opt in optionsOf(dim.key)"
              :key="opt"
              type="button"
              class="ldp-value-chip"
              :class="{ 'is-on': selOf(dim.key).has(opt) }"
              @click="toggleValue(dim.key, opt)"
            >{{ opt }}</button>
          </div>
        </div>
      </div>

      <label class="ldp-require-fif">
        <input type="checkbox" :checked="requireFif" @change="onRequireFifChange($event)" />
        <span>只载入已转 FIF 的记录</span>
      </label>

      <!-- 实时匹配预览 -->
      <div class="ldp-preview">
        <div class="ldp-preview-head">
          <strong>{{ mode === 'explicit' ? '锁定' : '匹配' }} {{ matched.length }} 条</strong>
          <span v-if="blockedCount" class="ldp-preview-warn">其中 {{ blockedCount }} 条状态异常将被跳过</span>
        </div>
        <div v-if="!matched.length" class="ldp-empty-hint">当前条件没有匹配到任何记录。</div>
        <ul v-else class="ldp-preview-list">
          <li v-for="rec in previewItems" :key="rec.id" class="ldp-preview-item">
            <span class="ldp-preview-entity">{{ entityLabel(rec) }}</span>
            <span class="ldp-qa" :class="qaClass(rec.qa_status)">{{ rec.qa_status || '—' }}</span>
          </li>
        </ul>
        <p v-if="extraCount > 0" class="ldp-preview-more">及另 {{ extraCount }} 条…</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { Recording } from '@/types'

// 与 PipelinePage.vue 的 LoadDataFilter / LoadDataParams 结构一致，保证 modelValue/emit 双向可赋值。
type DatasetFilterValue = string | null

interface LoadDataFilter {
  subjects: DatasetFilterValue[] | 'all'
  sessions: DatasetFilterValue[] | 'all'
  tasks: DatasetFilterValue[] | 'all'
  runs: DatasetFilterValue[] | 'all'
  qa_status: string[] | 'all'
  dataset_asset_id?: string | null
  dataset_asset_ids?: string[] | 'all'
  mount_id?: string | null
  mount_name?: string | null
  require_fif: boolean
}

interface LoadDataParams {
  selection_mode: 'filter' | 'explicit'
  dataset_filter: LoadDataFilter
  dataset_ids: string[]
}

type DimKey = 'subjects' | 'sessions' | 'tasks' | 'runs'

const DIMENSIONS: { key: DimKey; label: string }[] = [
  { key: 'subjects', label: '被试' },
  { key: 'sessions', label: 'Session' },
  { key: 'tasks', label: '任务' },
  { key: 'runs', label: 'Run' },
]

const PREVIEW_LIMIT = 20
const BLOCKED_QA = new Set(['failed', 'deleted', 'rejected'])

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

const mode = ref<'filter' | 'explicit'>('filter')
const requireFif = ref(true)
// 每个维度一个 Set：空 = 全部（与后端 _normalize_filter_value 的「空列表 → all」一致）。
const sel = reactive<Record<DimKey, Set<string>>>({
  subjects: new Set(),
  sessions: new Set(),
  tasks: new Set(),
  runs: new Set(),
})
let suspendEmit = false

// === 维度候选值（从已加载的 studyDatasets 派生）===
function uniqueValues(pick: (r: Recording) => string | null | undefined): string[] {
  const set = new Set<string>()
  for (const r of props.studyDatasets) {
    const v = pick(r)
    if (v) set.add(v)
  }
  return [...set].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
}
const subjectOptions = computed(() => uniqueValues((r) => r.bids_subject_id))
const sessionOptions = computed(() => uniqueValues((r) => r.session))
const taskOptions = computed(() => uniqueValues((r) => r.task))
const runOptions = computed(() => uniqueValues((r) => r.run))

function optionsOf(key: DimKey): string[] {
  if (key === 'subjects') return subjectOptions.value
  if (key === 'sessions') return sessionOptions.value
  if (key === 'tasks') return taskOptions.value
  return runOptions.value
}
function selOf(key: DimKey): Set<string> {
  return sel[key]
}
function valueOf(key: DimKey, r: Recording): string | null | undefined {
  if (key === 'subjects') return r.bids_subject_id
  if (key === 'sessions') return r.session
  if (key === 'tasks') return r.task
  return r.run
}
function isAll(key: DimKey): boolean {
  return sel[key].size === 0
}

// === 客户端实时匹配（预览即所选）===
function dimMatches(key: DimKey, r: Recording): boolean {
  const set = sel[key]
  if (set.size === 0) return true
  const v = valueOf(key, r)
  return v != null && set.has(String(v))
}
const matched = computed<Recording[]>(() =>
  props.studyDatasets.filter((r) => DIMENSIONS.every((d) => dimMatches(d.key, r))),
)
const previewItems = computed(() => matched.value.slice(0, PREVIEW_LIMIT))
const extraCount = computed(() => Math.max(0, matched.value.length - PREVIEW_LIMIT))
const blockedCount = computed(
  () => matched.value.filter((r) => BLOCKED_QA.has(String(r.qa_status || '').toLowerCase())).length,
)

function entityLabel(r: Recording): string {
  const parts = [r.bids_subject_id]
  if (r.session) parts.push(r.session)
  if (r.task) parts.push(r.task)
  if (r.run) parts.push(r.run)
  return parts.join(' · ')
}
function qaClass(status?: string | null): string {
  const s = String(status || '').toLowerCase()
  if (BLOCKED_QA.has(s)) return 'is-bad'
  if (s === 'converted' || s === 'passed') return 'is-ok'
  return ''
}

// === 交互 ===
function toggleValue(key: DimKey, value: string) {
  const set = sel[key]
  if (set.has(value)) set.delete(value)
  else set.add(value)
  emitChange()
}
function clearDim(key: DimKey) {
  if (sel[key].size === 0) return
  sel[key].clear()
  emitChange()
}
function setMode(next: 'filter' | 'explicit') {
  if (mode.value === next) return
  mode.value = next
  emitChange()
}
function onRequireFifChange(event: Event) {
  requireFif.value = (event.target as HTMLInputElement).checked
  emitChange()
}

// 快捷场景：设一个起点维度组合，用户再细调。
function scenarioAll() {
  for (const d of DIMENSIONS) sel[d.key].clear()
  emitChange()
}
function scenarioSingleSubject() {
  const first = subjectOptions.value[0]
  if (!first) return
  for (const d of DIMENSIONS) sel[d.key].clear()
  sel.subjects.add(first)
  emitChange()
}
function scenarioAllSubjectsOneTask() {
  const first = taskOptions.value[0]
  if (!first) return
  for (const d of DIMENSIONS) sel[d.key].clear()
  sel.tasks.add(first)
  emitChange()
}

// === 与 modelValue 双向同步 ===
function setToFilter(set: Set<string>): string[] | 'all' {
  return set.size ? [...set] : 'all'
}
function emitChange() {
  if (suspendEmit) return
  const dataset_filter: LoadDataFilter = {
    ...props.modelValue.dataset_filter,
    subjects: setToFilter(sel.subjects),
    sessions: setToFilter(sel.sessions),
    tasks: setToFilter(sel.tasks),
    runs: setToFilter(sel.runs),
    require_fif: requireFif.value,
  }
  // filter 模式：存规则，dataset_ids 留空，执行时后端按 filter 实时展开（数据集加被试自动纳入）。
  // explicit 模式：把当前匹配冻结成固定 recording id 列表，复现某次分析、不随数据集变化。
  emit('update:modelValue', {
    selection_mode: mode.value,
    dataset_filter,
    dataset_ids: mode.value === 'explicit' ? matched.value.map((r) => r.id) : [],
  })
}

function readDim(value: DatasetFilterValue[] | 'all' | undefined): Set<string> {
  if (Array.isArray(value)) {
    return new Set(value.filter((v): v is string => typeof v === 'string' && v !== ''))
  }
  return new Set()
}
function restoreStateFromParams(params: LoadDataParams) {
  suspendEmit = true
  try {
    mode.value = params.selection_mode === 'explicit' ? 'explicit' : 'filter'
    const f = params.dataset_filter || ({} as LoadDataFilter)
    sel.subjects = readDim(f.subjects)
    sel.sessions = readDim(f.sessions)
    sel.tasks = readDim(f.tasks)
    sel.runs = readDim(f.runs)
    requireFif.value = f.require_fif !== false
  } finally {
    suspendEmit = false
  }
}

watch(
  () => props.modelValue,
  (params) => {
    if (params) restoreStateFromParams(params)
  },
  { immediate: true, deep: true },
)
</script>

<style scoped>
.load-data-panel-v2 {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  flex: 1;
}

.state-text {
  padding: 12px;
  color: var(--color-text-secondary, #6b7280);
  font-size: 13px;
}
.state-text--error {
  color: var(--color-danger, #dc2626);
}

/* 模式切换 */
.ldp-mode {
  display: inline-flex;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 6px;
  overflow: hidden;
  align-self: flex-start;
}
.ldp-mode-btn {
  padding: 5px 14px;
  font-size: 13px;
  border: none;
  background: var(--color-surface, #fff);
  color: var(--color-text-secondary, #6b7280);
  cursor: pointer;
}
.ldp-mode-btn.is-active {
  background: var(--color-primary, #2e6bff);
  color: #fff;
}
.ldp-mode-hint {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-secondary, #6b7280);
  line-height: 1.5;
}

/* 快捷场景 */
.ldp-scenarios {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.ldp-scenarios-label {
  font-size: 12px;
  color: var(--color-text-secondary, #6b7280);
}
.ldp-chip-btn {
  padding: 3px 10px;
  font-size: 12px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 12px;
  background: var(--color-surface, #fff);
  color: var(--color-text, #111827);
  cursor: pointer;
}
.ldp-chip-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ldp-chip-btn:not(:disabled):hover {
  border-color: var(--color-primary, #2e6bff);
}

/* 维度 */
.ldp-dims {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ldp-dim {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ldp-dim-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ldp-dim-head strong {
  font-size: 13px;
}
.ldp-all-btn {
  padding: 2px 10px;
  font-size: 12px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 12px;
  background: var(--color-surface, #fff);
  color: var(--color-text-secondary, #6b7280);
  cursor: pointer;
}
.ldp-all-btn.is-active {
  background: var(--color-primary-soft, #e6efff);
  border-color: var(--color-primary, #2e6bff);
  color: var(--color-primary, #2e6bff);
}
.ldp-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ldp-value-chip {
  padding: 3px 10px;
  font-size: 12px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 12px;
  background: var(--color-surface, #fff);
  color: var(--color-text, #111827);
  cursor: pointer;
}
.ldp-value-chip.is-on {
  background: var(--color-primary, #2e6bff);
  border-color: var(--color-primary, #2e6bff);
  color: #fff;
}

.ldp-require-fif {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary, #6b7280);
}

/* 预览 */
.ldp-preview {
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--color-surface-muted, #f9fafb);
}
.ldp-preview-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.ldp-preview-head strong {
  font-size: 13px;
}
.ldp-preview-warn {
  font-size: 11px;
  color: var(--color-warning, #b45309);
}
.ldp-preview-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 220px;
  overflow-y: auto;
}
.ldp-preview-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  padding: 2px 0;
}
.ldp-preview-entity {
  font-variant-numeric: tabular-nums;
}
.ldp-qa {
  font-size: 11px;
  color: var(--color-text-secondary, #6b7280);
}
.ldp-qa.is-ok {
  color: var(--color-success, #15803d);
}
.ldp-qa.is-bad {
  color: var(--color-danger, #dc2626);
}
.ldp-preview-more {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--color-text-secondary, #6b7280);
}
.ldp-empty-hint {
  font-size: 12px;
  color: var(--color-text-secondary, #9ca3af);
  padding: 4px 0;
}
</style>
