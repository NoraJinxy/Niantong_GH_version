<template>
  <div class="results-page">
      <!-- ❶ Header -->
      <header class="page__header results-header">
        <div class="results-header__title">
          <h1 class="page__title">派生数据</h1>
          <p class="page__subtitle">
            这里列出本研究项里所有由工作流产出的数据。可以搜索、筛选、改名、加标签、改保存策略。
          </p>
        </div>
        <div class="results-header__actions">
          <button
            class="btn btn--icon"
            type="button"
            :disabled="loading || !selectedStudyId"
            title="刷新"
            aria-label="刷新"
            @click="reload"
          >
            <span v-if="loading" class="spinner spinner--dark"></span>
            <AppIcon v-else name="refresh" :size="16" />
          </button>
          <div class="results-more" :class="{ 'is-open': moreOpen }">
            <button
              class="btn btn--icon"
              type="button"
              :disabled="!selectedStudyId"
              title="更多"
              aria-label="更多"
              @click="moreOpen = !moreOpen"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <circle cx="5" cy="12" r="1.4" fill="currentColor" />
                <circle cx="12" cy="12" r="1.4" fill="currentColor" />
                <circle cx="19" cy="12" r="1.4" fill="currentColor" />
              </svg>
            </button>
            <div v-if="moreOpen" class="results-more__menu" @click.self="moreOpen = false">
              <button type="button" :disabled="cleanupLoading" @click="onCleanupAndClose">
                <AppIcon name="trash" :size="14" />
                清理缓存 / 临时数据
              </button>
            </div>
          </div>
        </div>
      </header>

      <!-- 未选研究项：大空状态 -->
      <section v-if="!selectedStudyId" class="empty results-empty-stage">
        <div class="empty__icon"><AppIcon name="figure" :size="26" /></div>
        <strong>先选择一个研究项</strong>
        <p>派生数据按研究项组织。选择右上角的研究项就能浏览它产出的所有结果。</p>
      </section>

      <template v-else>
        <!-- ❷ Summary Strip - 可点击筛选 -->
        <section class="results-summary" aria-label="保存状态概览">
          <button
            v-for="card in summaryCards"
            :key="card.key"
            type="button"
            class="results-summary-card"
            :class="[`is-${card.tone}`, { 'is-active': isSummaryActive(card.key) }]"
            @click="toggleSummaryFilter(card.key)"
          >
            <span class="results-summary-card__label">{{ card.label }}</span>
            <strong class="results-summary-card__value">{{ card.value }}</strong>
          </button>
        </section>

        <!-- UI Phase (docs_v2/6-05) P1-3: 数据类型快速筛选 chip -->
        <section v-if="dataTypeOptions.length" class="results-type-chips" aria-label="按结果类型筛选">
          <button
            type="button"
            class="type-chip"
            :class="{ 'is-active': !filters.data_types.length }"
            @click="filters.data_types = []"
          >
            <span class="type-chip__icon"><AppIcon name="dashboard" :size="14" /></span>
            全部 <small>{{ datasets.length }}</small>
          </button>
          <button
            v-for="opt in dataTypeOptions"
            :key="'tc-' + opt"
            type="button"
            class="type-chip"
            :class="[{ 'is-active': filters.data_types.includes(opt) }, dataTypeClass(opt)]"
            @click="toggleFilter('data_types', opt)"
          >
            <span class="type-chip__icon"><AppIcon :name="dataTypeIcon(opt)" :size="14" /></span>
            {{ opt }} <small>{{ countByType(opt) }}</small>
          </button>
        </section>

        <!-- ❸ Filter Bar -->
        <section class="results-filter-bar" aria-label="筛选">
          <label class="results-search">
            <AppIcon name="search" :size="14" />
            <input
              v-model.trim="searchText"
              type="search"
              placeholder="搜索名称 / 编码 / 被试 / 运行..."
            />
            <button
              v-if="searchText"
              type="button"
              class="results-search__clear"
              aria-label="清空搜索"
              @click="searchText = ''"
            >
              ×
            </button>
          </label>

          <details ref="ddType" class="filter-dd">
            <summary>
              数据类型
              <span v-if="filters.data_types.length" class="filter-dd__count">{{ filters.data_types.length }}</span>
              <span class="filter-dd__caret">▾</span>
            </summary>
            <div class="filter-dd__panel">
              <div v-if="!dataTypeOptions.length" class="filter-dd__empty">无可筛选项</div>
              <label v-for="opt in dataTypeOptions" :key="'dd-dt-' + opt" class="filter-dd__opt">
                <input type="checkbox" :checked="filters.data_types.includes(opt)" @change="toggleFilter('data_types', opt)" />
                <span class="data-type-tag" :class="dataTypeClass(opt)">
                  {{ opt }}
                </span>
              </label>
            </div>
          </details>

          <details ref="ddSubject" class="filter-dd">
            <summary>
              被试
              <span v-if="filters.bids_subject_ids.length" class="filter-dd__count">{{ filters.bids_subject_ids.length }}</span>
              <span class="filter-dd__caret">▾</span>
            </summary>
            <div class="filter-dd__panel">
              <div v-if="!subjectOptions.length" class="filter-dd__empty">无可筛选项</div>
              <label v-for="opt in subjectOptions" :key="'dd-sub-' + opt" class="filter-dd__opt">
                <input type="checkbox" :checked="filters.bids_subject_ids.includes(opt)" @change="toggleFilter('bids_subject_ids', opt)" />
                <span>{{ opt }}</span>
              </label>
            </div>
          </details>

          <details ref="ddTask" class="filter-dd">
            <summary>
              Task
              <span v-if="filters.tasks.length" class="filter-dd__count">{{ filters.tasks.length }}</span>
              <span class="filter-dd__caret">▾</span>
            </summary>
            <div class="filter-dd__panel">
              <div v-if="!taskOptions.length" class="filter-dd__empty">无可筛选项</div>
              <label v-for="opt in taskOptions" :key="'dd-task-' + opt" class="filter-dd__opt">
                <input type="checkbox" :checked="filters.tasks.includes(opt)" @change="toggleFilter('tasks', opt)" />
                <span>{{ opt }}</span>
              </label>
            </div>
          </details>

          <details ref="ddTag" class="filter-dd">
            <summary>
              标签
              <span v-if="filters.tags.length" class="filter-dd__count">{{ filters.tags.length }}</span>
              <span class="filter-dd__caret">▾</span>
            </summary>
            <div class="filter-dd__panel">
              <div v-if="!tagOptions.length" class="filter-dd__empty">还没人加过标签</div>
              <label v-for="opt in tagOptions" :key="'dd-tag-' + opt" class="filter-dd__opt">
                <input type="checkbox" :checked="filters.tags.includes(opt)" @change="toggleFilter('tags', opt)" />
                <span>#{{ opt }}</span>
              </label>
            </div>
          </details>

          <button
            v-if="hasActiveFilters"
            type="button"
            class="results-filter-reset"
            @click="resetFilters"
          >
            重置筛选
          </button>
        </section>

        <!-- ❹ Toolbar -->
        <section class="results-toolbar">
          <div class="results-toolbar__count">
            <strong>{{ filtered.length }}</strong>
            <span class="muted">/ 共 {{ datasets.length }} 条</span>
            <span v-if="loading" class="muted">· 读取中…</span>
            <span v-if="error" class="results-toolbar__error">· {{ error }}</span>
            <span v-if="datasets.length >= 1000" class="muted">· 仅展示前 1000 条</span>
          </div>

          <div class="results-toolbar__right">
            <label class="results-select-all">
              <input
                type="checkbox"
                :checked="allChecked"
                :indeterminate.prop="partialChecked"
                :disabled="!filtered.length"
                @change="toggleAllChecked($event)"
              />
              <span>全选</span>
            </label>

            <transition name="results-toolbar-bulk">
              <div v-if="selectedIds.size" class="results-toolbar__bulk">
                <span class="results-toolbar__selection">已选 {{ selectedIds.size }} 项</span>
                <button class="btn btn--sm" type="button" @click="bulkSetKeep(true)">
                  <AppIcon name="check" :size="12" />保存
                </button>
                <button class="btn btn--sm" type="button" @click="bulkSetKeep(false)">设为不保存</button>
                <button class="btn btn--sm" type="button" @click="openBulkTagDialog">
                  <AppIcon name="plus" :size="12" />加标签
                </button>
                <button class="btn btn--sm btn--ghost" type="button" @click="bulkDelete">
                  <AppIcon name="trash" :size="12" />删除
                </button>
                <button class="btn btn--sm btn--ghost" type="button" @click="clearSelection">取消</button>
              </div>
            </transition>
          </div>
        </section>

        <!-- ❺ List + ❻ Detail -->
        <section class="results-body" :class="{ 'has-detail': activeRow }">
          <div class="results-list" :class="`results-list--${viewMode}`">
            <!-- Loading skeleton -->
            <div v-if="loading && !datasets.length" class="results-skeleton">
              <div v-for="i in 5" :key="'sk-' + i" class="results-skeleton-row">
                <div class="results-skeleton-row__check"></div>
                <div class="results-skeleton-row__tag"></div>
                <div class="results-skeleton-row__body">
                  <div class="results-skeleton-row__line results-skeleton-row__line--lg"></div>
                  <div class="results-skeleton-row__line results-skeleton-row__line--md"></div>
                </div>
              </div>
            </div>

            <!-- Empty: no data at all -->
            <div v-else-if="!datasets.length" class="results-empty-inline">
              <div class="results-empty-inline__icon"><AppIcon name="figure" :size="28" /></div>
              <strong>这个研究项还没有派生数据</strong>
              <p>执行一个工作流试试，输出结果会在这里汇总。</p>
              <RouterLink class="btn btn--primary btn--sm" :to="`/studies/${selectedStudyId}/workflow`">
                <AppIcon name="pipeline" :size="14" />
                进入工作流
              </RouterLink>
            </div>

            <!-- Empty: no match -->
            <div v-else-if="!filtered.length" class="results-empty-inline">
              <div class="results-empty-inline__icon"><AppIcon name="search" :size="28" /></div>
              <strong>没有符合条件的派生数据</strong>
              <p>试着调整筛选条件，或清空当前筛选。</p>
              <button class="btn btn--sm" type="button" @click="resetFilters">重置筛选</button>
            </div>

            <!-- Rows -->
            <article
              v-for="row in filtered"
              v-else
              :key="row.id"
              class="result-row"
              :class="{ 'is-active': activeId === row.id, 'is-checked': selectedIds.has(row.id) }"
              tabindex="0"
              @click="setActive(row.id)"
              @keydown.enter="setActive(row.id)"
            >
              <!-- UI Phase (docs_v2/6-05) P1-3: 卡片视图顶部预览占位 -->
              <div v-if="viewMode === 'grid'" class="result-row__preview" :class="dataTypeClass(row.data_type)">
                <span class="result-row__preview-emoji"><AppIcon :name="dataTypeIcon(row.data_type)" :size="40" /></span>
                <span class="result-row__preview-meta" v-if="previewSummaryFor(row)">{{ previewSummaryFor(row) }}</span>
              </div>
              <label class="result-row__check" @click.stop>
                <input
                  type="checkbox"
                  :checked="selectedIds.has(row.id)"
                  @change="toggleRowChecked(row.id, $event)"
                />
              </label>

              <span class="data-type-tag data-type-tag--lg" :class="dataTypeClass(row.data_type)">
                <AppIcon :name="dataTypeIcon(row.data_type)" :size="12" />
                {{ row.data_type }}
              </span>

              <div class="result-row__main">
                <div class="result-row__title">
                  <strong>{{ rowDisplayName(row) }}</strong>
                  <span class="badge" :class="retentionBadgeClass(row)">
                    {{ retentionLabel(row) }}
                  </span>
                </div>
                <div class="result-row__meta">
                  <span v-if="row.bids_subject_id" class="result-row__meta-item">
                    <em>被试</em>{{ row.bids_subject_id }}
                  </span>
                  <span v-if="row.task" class="result-row__meta-item">
                    <em>Task</em>{{ row.task }}
                  </span>
                  <span v-if="row.session" class="result-row__meta-item">
                    <em>Ses</em>{{ row.session }}
                  </span>
                  <span v-if="row.produced_by_execution_id" class="result-row__meta-item result-row__meta-item--mono">
                    <em>运行</em>{{ shortId(row.produced_by_execution_id) }}
                  </span>
                  <span v-if="row.produced_by_node_type" class="result-row__meta-item">
                    <em>节点</em>{{ row.produced_by_node_type }}
                  </span>
                </div>
                <div v-if="row.tags && row.tags.length" class="result-row__tags">
                  <span v-for="tag in row.tags.slice(0, 4)" :key="'rt-' + row.id + '-' + tag" class="result-row__tag">#{{ tag }}</span>
                  <span v-if="row.tags.length > 4" class="result-row__tag-more">+{{ row.tags.length - 4 }}</span>
                </div>
              </div>

              <div class="result-row__right">
                <span class="result-row__size">{{ formatSize(row.file_size) }}</span>
                <span class="result-row__time">{{ formatTime(row.created_at) }}</span>
              </div>
            </article>
          </div>

          <!-- ❻ Detail Drawer -->
          <aside v-if="activeRow" class="result-detail">
            <header class="result-detail__hero">
              <div class="result-detail__hero-top">
                <span class="data-type-tag data-type-tag--lg" :class="dataTypeClass(activeRow.data_type)">
                  <AppIcon :name="dataTypeIcon(activeRow.data_type)" :size="12" />
                  {{ activeRow.data_type }}
                </span>
                <button class="btn btn--icon btn--ghost" type="button" aria-label="关闭" @click="activeId = ''">×</button>
              </div>
              <div class="result-detail__title">
                <input
                  v-if="renamingActive"
                  ref="renameInput"
                  v-model="renameDraft"
                  type="text"
                  class="input"
                  @keydown.enter="commitRename"
                  @keydown.esc="cancelRename"
                  @blur="commitRename"
                />
                <template v-else>
                  <strong @click="startRename" :title="activeRow.display_name || ''">
                    {{ activeRow.display_name || '(未命名)' }}
                  </strong>
                  <button type="button" class="result-detail__rename" @click="startRename">改名</button>
                </template>
              </div>
              <div class="result-detail__retention">
                <span class="result-detail__retention-label">保存</span>
                <select
                  class="input input--sm"
                  :value="activeRow.keep ? 'keep' : 'discard'"
                  @change="setRowKeep(activeRow, ($event.target as HTMLSelectElement).value === 'keep')"
                >
                  <option v-for="opt in keepOptions" :key="'sd-' + opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
                <button
                  v-if="!activeRow.deleted_at"
                  class="btn btn--sm btn--ghost"
                  type="button"
                  @click="setRowDeleted(activeRow, true)"
                >删除</button>
                <button
                  v-else
                  class="btn btn--sm btn--ghost"
                  type="button"
                  :disabled="!!activeRow.purged_at"
                  :title="activeRow.purged_at ? '已物理清盘、文件不可恢复' : ''"
                  @click="setRowDeleted(activeRow, false)"
                >{{ activeRow.purged_at ? '已清盘' : '恢复' }}</button>
              </div>
            </header>

            <div class="result-detail__quick-actions">
              <button class="btn btn--primary btn--sm" type="button" @click="downloadRow(activeRow)">
                <AppIcon name="import" :size="14" />下载
              </button>
              <RouterLink
                v-if="activeRow.produced_by_execution_id"
                class="btn btn--sm"
                :to="{ path: `/studies/${selectedStudyId}/workflow`, query: { execution_id: activeRow.produced_by_execution_id } }"
              >
                <AppIcon name="pipeline" :size="14" />跳转工作流
              </RouterLink>
              <button class="btn btn--sm" type="button" :title="activeRow.id" @click="copyId(activeRow.id)">
                <AppIcon name="copy" :size="14" />
                {{ copyHint || '复制 ID' }}
              </button>
            </div>

            <!-- UI Phase (docs_v2/6-05): 概览 L1 - 用户日常关心的"是什么" -->
            <section class="result-detail__section">
              <h3>概要</h3>
              <dl class="result-detail__grid">
                <div><dt>被试</dt><dd>{{ activeRow.bids_subject_id || '—' }}</dd></div>
                <div><dt>采集任务</dt><dd>{{ activeRow.task || '—' }}</dd></div>
                <div><dt>会话</dt><dd>{{ activeRow.session || '—' }}</dd></div>
                <div><dt>实验条件</dt><dd>{{ activeRow.condition || '—' }}</dd></div>
                <div><dt>产出步骤</dt><dd>{{ activeRow.produced_by_node_type || '—' }}</dd></div>
                <div><dt>文件大小</dt><dd>{{ formatSize(activeRow.file_size) }}</dd></div>
                <div class="result-detail__grid-wide"><dt>创建时间</dt><dd>{{ formatTime(activeRow.created_at) }}</dd></div>
              </dl>
            </section>

            <!-- UI Phase (docs_v2/6-05): 数据预览 L1 - preview_json 的关键数字 -->
            <section v-if="previewSummaryFor(activeRow)" class="result-detail__section">
              <h3>数据预览</h3>
              <div class="result-detail__preview-stats">{{ previewSummaryFor(activeRow) }}</div>
            </section>

            <section class="result-detail__section">
              <h3>标签</h3>
              <div class="result-detail__tags">
                <span v-for="tag in activeRow.tags || []" :key="'dt-' + tag" class="result-detail__tag">
                  #{{ tag }}
                  <button type="button" class="result-detail__tag-remove" aria-label="移除" @click="removeTag(activeRow, tag)">×</button>
                </span>
                <input
                  type="text"
                  class="result-detail__tag-input"
                  placeholder="+ 加标签 (回车)"
                  :value="tagDraft"
                  @input="tagDraft = ($event.target as HTMLInputElement).value"
                  @keydown.enter="commitTagDraft"
                />
              </div>
            </section>

            <section class="result-detail__section">
              <h3>来源链</h3>
              <ol v-if="lineageItems.length" class="result-detail__lineage">
                <li v-for="(item, idx) in lineageItems" :key="'ln-' + idx" :class="{ 'is-current': item.current }">
                  <span class="result-detail__lineage-dot" :class="{ 'is-current': item.current }"></span>
                  <div class="result-detail__lineage-body">
                    <span class="result-detail__lineage-label">{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                </li>
              </ol>
              <p v-else class="result-detail__lineage-empty">没有上游记录。</p>
            </section>

            <!-- UI Phase (docs_v2/6-05) L3: 技术信息折叠 -->
            <TechnicalFold title="技术信息" hint="ID / 内部状态 / 存储路径">
              <dl>
                <div><dt>派生数据 ID</dt><dd>{{ activeRow.id }}</dd></div>
                <div v-if="activeRow.produced_by_execution_id"><dt>来源运行 ID</dt><dd>{{ activeRow.produced_by_execution_id }}</dd></div>
                <div v-if="activeRow.produced_by_job_id"><dt>节点任务 ID</dt><dd>{{ activeRow.produced_by_job_id }}</dd></div>
                <div v-if="activeRow.data_type"><dt>数据类型枚举</dt><dd>{{ activeRow.data_type }}</dd></div>
                <div><dt>保存</dt><dd>{{ activeRow.keep ? '是' : '否' }}</dd></div>
                <div><dt>系统缓存</dt><dd>{{ activeRow.cache_eligible ? '是' : '否' }}</dd></div>
                <div v-if="activeRow.storage_uri"><dt>存储 URI</dt><dd>{{ activeRow.storage_uri }}</dd></div>
                <div v-if="activeRow.sha256"><dt>SHA-256</dt><dd>{{ activeRow.sha256 }}</dd></div>
                <div v-if="activeRow.mime_type"><dt>MIME 类型</dt><dd>{{ activeRow.mime_type }}</dd></div>
              </dl>
            </TechnicalFold>
          </aside>
        </section>
      </template>
    </div>

    <!-- 批量加标签弹层 -->
    <div v-if="bulkTagOpen" class="modal-overlay" @click.self="bulkTagOpen = false">
      <section class="bulk-tag-dialog" role="dialog">
        <header class="bulk-tag-dialog__head">
          <strong>给 {{ selectedIds.size }} 条派生数据加标签</strong>
          <button class="btn btn--icon btn--ghost" type="button" @click="bulkTagOpen = false">×</button>
        </header>
        <p class="bulk-tag-dialog__hint">用逗号分隔多个标签，例如 <code>for-paper-1, 控制组</code></p>
        <input
          v-model="bulkTagDraft"
          type="text"
          class="input"
          placeholder="for-paper-1, 控制组"
          @keydown.enter="commitBulkTag"
        />
        <footer class="bulk-tag-dialog__actions">
          <button class="btn" type="button" @click="bulkTagOpen = false">取消</button>
          <button class="btn btn--primary" type="button" :disabled="!bulkTagDraft.trim()" @click="commitBulkTag">应用</button>
        </footer>
      </section>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import TechnicalFold from '@/components/TechnicalFold.vue'
import { pipelineApi } from '@/api/pipelines'
import type {
  StudyOutput,
  StudyOutputListQuery,
} from '@/types'

type StatusFilter = 'all' | 'kept' | 'transient' | 'deleted'

const keepOptions: Array<{ value: 'keep' | 'discard'; label: string }> = [
  { value: 'keep', label: '保存' },
  { value: 'discard', label: '不保存' },
]

const route = useRoute()
const selectedStudyId = computed(() => String(route.params.studyId || ''))
const datasets = ref<StudyOutput[]>([])
// 结果页只展示有意义的输出：保存 / 缓存 / 回收站；滤掉「纯临时」（不保存、系统也不缓存的跑完即清中间废料）
const visibleDatasets = computed(() =>
  datasets.value.filter((d) => d.keep || d.cache_eligible || Boolean(d.deleted_at)),
)
const loading = ref(false)
const error = ref('')

const searchText = ref('')
// UI Phase (docs_v2/6-05) P1-3: 视图模式 + 类型 chip 辅助
type ResultsViewMode = 'list' | 'grid'
const viewMode = ref<ResultsViewMode>('list')

function countByType(typeName: string): number {
  return visibleDatasets.value.filter((d) => d.data_type === typeName).length
}

// 从 preview_json 里抽几个关键数字作占位预览描述
function previewSummaryFor(row: { preview_json?: Record<string, unknown> | null }): string {
  const p = (row.preview_json ?? {}) as Record<string, unknown>
  const parts: string[] = []
  const ch = (p.n_channels ?? p.channels) as number | undefined
  const sf = (p.sfreq ?? p.sampling_rate) as number | undefined
  const dur = (p.duration_seconds ?? p.duration) as number | undefined
  const ne = (p.n_events ?? p.n_epochs) as number | undefined
  if (typeof ch === 'number' && ch > 0) parts.push(`${ch} 通道`)
  if (typeof sf === 'number' && sf > 0) parts.push(`${sf} Hz`)
  if (typeof dur === 'number' && dur > 0) parts.push(`${Math.round(dur)} 秒`)
  if (typeof ne === 'number' && ne > 0) parts.push(`${ne} 段`)
  return parts.slice(0, 3).join(' · ')
}

const filters = reactive({
  data_types: [] as string[],
  bids_subject_ids: [] as string[],
  tasks: [] as string[],
  status: 'all' as StatusFilter,
  tags: [] as string[],
})

const selectedIds = reactive(new Set<string>())
const activeId = ref('')
const renamingActive = ref(false)
const renameDraft = ref('')
const renameInput = ref<HTMLInputElement | null>(null)
const tagDraft = ref('')

const bulkTagOpen = ref(false)
const bulkTagDraft = ref('')
const cleanupLoading = ref(false)
const moreOpen = ref(false)
const copyHint = ref('')

// === computed ===
const activeRow = computed(() => datasets.value.find((d) => d.id === activeId.value) || null)

const dataTypeOptions = computed(() => uniqueSorted(visibleDatasets.value.map((d) => d.data_type)))
const subjectOptions = computed(() => uniqueSorted(visibleDatasets.value.map((d) => d.bids_subject_id || '').filter(Boolean)))
const taskOptions = computed(() => uniqueSorted(visibleDatasets.value.map((d) => d.task || '').filter(Boolean)))
const tagOptions = computed(() => {
  const set = new Set<string>()
  for (const d of visibleDatasets.value) for (const t of d.tags || []) set.add(t)
  return Array.from(set).sort()
})

const filtered = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  return visibleDatasets.value.filter((d) => {
    if (filters.data_types.length && !filters.data_types.includes(d.data_type)) return false
    if (filters.bids_subject_ids.length && !filters.bids_subject_ids.includes(d.bids_subject_id || '')) return false
    if (filters.tasks.length && !filters.tasks.includes(d.task || '')) return false
    const deleted = Boolean(d.deleted_at)
    if (filters.status === 'deleted') {
      if (!deleted) return false
    } else if (deleted) {
      // 默认不显示已删除，除非用户主动选「已删除」
      return false
    } else if (filters.status === 'kept' && !d.keep) {
      return false
    } else if (filters.status === 'transient' && d.keep) {
      return false
    }
    if (filters.tags.length && !filters.tags.some((t) => (d.tags || []).includes(t))) return false
    if (q) {
      const hay = [
        d.display_name || '',
        d.data_type || '',
        d.bids_subject_id || '',
        d.task || '',
        d.session || '',
        d.condition || '',
        d.produced_by_execution_id || '',
        d.produced_by_node_type || '',
        d.id || '',
        ...(d.tags || []),
      ].join(' ').toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const summaryCards = computed(() => {
  let all = 0, kept = 0, transient = 0, deleted = 0
  for (const d of visibleDatasets.value) {
    all++
    if (d.deleted_at) deleted++
    else if (d.keep) kept++
    else transient++
  }
  return [
    { key: 'all', label: '总数', value: all, tone: 'neutral' },
    { key: 'kept', label: '保存', value: kept, tone: 'success' },
    { key: 'transient', label: '不保存', value: transient, tone: 'muted' },
    { key: 'deleted', label: '已删除', value: deleted, tone: 'danger' },
  ]
})

const hasActiveFilters = computed(() =>
  Boolean(
    searchText.value
    || filters.data_types.length
    || filters.bids_subject_ids.length
    || filters.tasks.length
    || filters.status !== 'all'
    || filters.tags.length,
  ),
)

const allChecked = computed(() => filtered.value.length > 0 && filtered.value.every((row) => selectedIds.has(row.id)))
const partialChecked = computed(() => {
  if (!filtered.value.length) return false
  const n = filtered.value.filter((row) => selectedIds.has(row.id)).length
  return n > 0 && n < filtered.value.length
})

const lineageItems = computed(() => {
  if (!activeRow.value) return [] as Array<{ label: string; value: string; current?: boolean }>
  const items: Array<{ label: string; value: string; current?: boolean }> = []
  for (const rid of activeRow.value.upstream_recording_ids || []) {
    items.push({ label: '原始 Recording', value: shortId(rid) })
  }
  for (const did of activeRow.value.upstream_dataset_ids || []) {
    items.push({ label: '上游派生', value: shortId(did) })
  }
  if (items.length) {
    items.push({ label: '当前', value: activeRow.value.display_name || activeRow.value.data_type, current: true })
  }
  return items
})

// === watchers ===
watch(selectedStudyId, async () => {
  selectedIds.clear()
  activeId.value = ''
  resetFiltersSilent()
  searchText.value = ''
  await reload()
})

// === lifecycle ===
onMounted(() => {
  // studyId 来自容器路由参数；computed 初值不触发 watch，首屏显式拉一次
  if (selectedStudyId.value) void reload()
  document.addEventListener('click', onGlobalClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onGlobalClick)
})

function onGlobalClick(event: MouseEvent) {
  if (moreOpen.value) {
    const target = event.target as HTMLElement
    if (!target.closest('.results-more')) {
      moreOpen.value = false
    }
  }
}

// === actions ===
async function reload() {
  if (!selectedStudyId.value) {
    datasets.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const query: StudyOutputListQuery = {
      include_deleted: true,
      limit: 1000,
      offset: 0,
    }
    const res = await pipelineApi.listStudyOutputs(selectedStudyId.value, query)
    datasets.value = res.data.study_outputs
  } catch (err) {
    datasets.value = []
    error.value = describeError(err, '派生数据读取失败')
  } finally {
    loading.value = false
  }
}

function toggleFilter<K extends keyof typeof filters>(key: K, value: string) {
  const arr = filters[key]
  if (!Array.isArray(arr)) return
  const idx = (arr as string[]).indexOf(value)
  if (idx >= 0) (arr as string[]).splice(idx, 1)
  else (arr as string[]).push(value)
}

function resetFilters() {
  resetFiltersSilent()
  searchText.value = ''
}

function resetFiltersSilent() {
  filters.data_types = []
  filters.bids_subject_ids = []
  filters.tasks = []
  filters.status = 'all'
  filters.tags = []
}

function isSummaryActive(key: string): boolean {
  return filters.status === key
}

function toggleSummaryFilter(key: string) {
  if (key === 'all') {
    filters.status = 'all'
    return
  }
  filters.status = filters.status === key ? 'all' : (key as StatusFilter)
}

function toggleRowChecked(id: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  if (checked) selectedIds.add(id)
  else selectedIds.delete(id)
}

function toggleAllChecked(event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  if (checked) {
    for (const row of filtered.value) selectedIds.add(row.id)
  } else {
    selectedIds.clear()
  }
}

function clearSelection() {
  selectedIds.clear()
}

function setActive(id: string) {
  activeId.value = id
  renamingActive.value = false
  copyHint.value = ''
}

async function bulkSetKeep(keep: boolean) {
  if (!selectedStudyId.value || !selectedIds.size) return
  try {
    const res = await pipelineApi.batchUpdateStudyOutputs(selectedStudyId.value, {
      ids: Array.from(selectedIds),
      update: { keep, reason: 'results_page_bulk' },
    })
    const map = new Map(res.data.study_outputs.map((d) => [d.id, d]))
    datasets.value = datasets.value.map((d) => map.get(d.id) || d)
    selectedIds.clear()
  } catch (err) {
    error.value = describeError(err, '批量操作失败')
  }
}

async function bulkDelete() {
  if (!selectedStudyId.value || !selectedIds.size) return
  try {
    const res = await pipelineApi.batchUpdateStudyOutputs(selectedStudyId.value, {
      ids: Array.from(selectedIds),
      update: { deleted: true, reason: 'results_page_bulk' },
    })
    const map = new Map(res.data.study_outputs.map((d) => [d.id, d]))
    datasets.value = datasets.value.map((d) => map.get(d.id) || d)
    selectedIds.clear()
  } catch (err) {
    error.value = describeError(err, '批量删除失败')
  }
}

function openBulkTagDialog() {
  bulkTagDraft.value = ''
  bulkTagOpen.value = true
}

async function commitBulkTag() {
  if (!selectedStudyId.value || !selectedIds.size) return
  const tags = bulkTagDraft.value.split(',').map((s) => s.trim()).filter(Boolean)
  if (!tags.length) return
  try {
    const res = await pipelineApi.batchUpdateStudyOutputs(selectedStudyId.value, {
      ids: Array.from(selectedIds),
      update: { tags, reason: 'results_page_bulk_tag' },
    })
    const map = new Map(res.data.study_outputs.map((d) => [d.id, d]))
    datasets.value = datasets.value.map((d) => map.get(d.id) || d)
    bulkTagOpen.value = false
  } catch (err) {
    error.value = describeError(err, '批量加标签失败')
  }
}

async function setRowKeep(row: StudyOutput, keep: boolean) {
  if (!selectedStudyId.value) return
  try {
    const res = await pipelineApi.updateStudyOutput(selectedStudyId.value, row.id, { keep })
    datasets.value = datasets.value.map((d) => (d.id === row.id ? res.data : d))
  } catch (err) {
    error.value = describeError(err, '保存设置修改失败')
  }
}

async function setRowDeleted(row: StudyOutput, deleted: boolean) {
  if (!selectedStudyId.value) return
  try {
    const res = await pipelineApi.updateStudyOutput(selectedStudyId.value, row.id, { deleted })
    datasets.value = datasets.value.map((d) => (d.id === row.id ? res.data : d))
  } catch (err) {
    error.value = describeError(err, deleted ? '删除失败' : '恢复失败')
  }
}

function startRename() {
  if (!activeRow.value) return
  renamingActive.value = true
  renameDraft.value = activeRow.value.display_name || ''
  nextTick(() => renameInput.value?.focus())
}

function cancelRename() {
  renamingActive.value = false
  renameDraft.value = ''
}

async function commitRename() {
  if (!renamingActive.value || !activeRow.value || !selectedStudyId.value) return
  const next = renameDraft.value.trim()
  const previous = (activeRow.value.display_name || '').trim()
  renamingActive.value = false
  if (next === previous) return
  try {
    const res = await pipelineApi.updateStudyOutput(selectedStudyId.value, activeRow.value.id, {
      display_name: next || null,
    })
    datasets.value = datasets.value.map((d) => (d.id === res.data.id ? res.data : d))
  } catch (err) {
    error.value = describeError(err, '改名失败')
  }
}

async function commitTagDraft() {
  if (!activeRow.value || !selectedStudyId.value) return
  const draft = tagDraft.value.trim()
  if (!draft) return
  if ((activeRow.value.tags || []).includes(draft)) {
    tagDraft.value = ''
    return
  }
  const next = [...(activeRow.value.tags || []), draft]
  try {
    const res = await pipelineApi.updateStudyOutput(selectedStudyId.value, activeRow.value.id, { tags: next })
    datasets.value = datasets.value.map((d) => (d.id === res.data.id ? res.data : d))
    tagDraft.value = ''
  } catch (err) {
    error.value = describeError(err, '加标签失败')
  }
}

async function removeTag(row: StudyOutput, tag: string) {
  if (!selectedStudyId.value) return
  const next = (row.tags || []).filter((t) => t !== tag)
  try {
    const res = await pipelineApi.updateStudyOutput(selectedStudyId.value, row.id, { tags: next })
    datasets.value = datasets.value.map((d) => (d.id === res.data.id ? res.data : d))
  } catch (err) {
    error.value = describeError(err, '移除标签失败')
  }
}

async function downloadRow(row: StudyOutput) {
  if (!selectedStudyId.value) return
  try {
    const res = await pipelineApi.downloadStudyOutput(selectedStudyId.value, row.id)
    const url = URL.createObjectURL(res.data)
    const link = document.createElement('a')
    link.href = url
    link.download = (row.display_name || row.data_type).replace(/[\\/:*?"<>|]/g, '_')
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    error.value = describeError(err, '下载失败')
  }
}

async function copyId(id: string) {
  try {
    await navigator.clipboard.writeText(id)
    copyHint.value = '已复制'
    setTimeout(() => { copyHint.value = '' }, 1400)
  } catch {
    copyHint.value = '复制失败'
    setTimeout(() => { copyHint.value = '' }, 1400)
  }
}

async function onCleanupAndClose() {
  moreOpen.value = false
  await onCleanup()
}

async function onCleanup() {
  if (!selectedStudyId.value || cleanupLoading.value) return
  if (!confirm('确认清理本研究项里所有不保存且已过期的输出吗？')) return
  cleanupLoading.value = true
  try {
    await pipelineApi.cleanupStudyOutputs(selectedStudyId.value, {
      dry_run: false,
      limit: 500,
      reason: 'results_page_cleanup',
    })
    await reload()
  } catch (err) {
    error.value = describeError(err, '清理任务创建失败')
  } finally {
    cleanupLoading.value = false
  }
}

// === helpers ===
function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean))).sort()
}

function shortId(value: string): string {
  return value.length > 8 ? value.slice(0, 8) : value
}

function rowDisplayName(row: StudyOutput): string {
  return row.display_name || `${row.data_type}${row.bids_subject_id ? ' · ' + row.bids_subject_id : ''}`
}

function formatTime(value?: string | null): string {
  if (!value) return '—'
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    const now = new Date()
    const sameYear = date.getFullYear() === now.getFullYear()
    return date.toLocaleString('zh-CN', {
      hour12: false,
      year: sameYear ? undefined : '2-digit',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return value
  }
}

function formatSize(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function retentionLabel(row: StudyOutput): string {
  if (row.purged_at) return '已清盘'
  if (row.deleted_at) return '已删除'
  if (row.keep) return '保存'
  if (row.cache_eligible) return '缓存'
  return '临时'
}

function retentionBadgeClass(row: StudyOutput): string {
  if (row.purged_at) return 'badge--muted'
  if (row.deleted_at) return 'badge--danger'
  if (row.keep) return 'badge--success'
  if (row.cache_eligible) return 'badge--outline'
  return 'badge--warning'
}

function dataTypeClass(type?: string | null): string {
  const t = String(type || '').toLowerCase()
  if (t.includes('ica')) return 'is-ica'
  if (t.includes('psd')) return 'is-psd'
  if (t.includes('tfr')) return 'is-tfr'
  if (t.includes('source')) return 'is-source'
  if (t.includes('micro')) return 'is-microstate'
  if (t.includes('connect')) return 'is-connectivity'
  if (t.includes('erp')) return 'is-erp'
  if (t.includes('ml') || t.includes('model')) return 'is-ml'
  return 'is-default'
}

function dataTypeIcon(type?: string | null): string {
  const t = String(type || '').toLowerCase()
  if (t.includes('ica') || t.includes('component')) return 'brain'
  if (t.includes('psd') || t.includes('spectrum')) return 'spectrum'
  if (t.includes('tfr') || (t.includes('time') && t.includes('freq'))) return 'heatmap'
  if (t.includes('source')) return 'source'
  if (t.includes('micro')) return 'network'
  if (t.includes('connect') || t.includes('network')) return 'network'
  if (t.includes('epoch')) return 'layers'
  if (t.includes('evoked') || t.includes('erp')) return 'wave'
  if (t.includes('raw') || t.includes('clean') || t.includes('filter')) return 'pulse'
  if (t.includes('ml') || t.includes('model')) return 'ai'
  return 'file'
}

function describeError(err: unknown, fallback: string): string {
  const maybe = err as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = maybe.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const message = (detail as { message?: string }).message
    if (message) return message
  }
  return maybe.message || fallback
}
</script>

<style scoped>
/* WorkbenchShell .page 已有 padding 与版心(.page--narrow)，这里不再自己定宽/居中 */
.results-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--c-text);
}

/* ===== ❶ Header ===== */
.results-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 0;
  flex-wrap: wrap;
}

.results-header__title .eyebrow {
  margin: 0 0 6px;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.results-header__title h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.25;
  color: var(--c-text);
}

.results-header__title p {
  margin: 8px 0 0;
  max-width: 760px;
  color: var(--c-text-2);
  font-size: 13px;
  line-height: 1.7;
}

.results-header__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.results-study-select {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--c-text-2);
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  transition: border-color var(--t-fast);
}
.results-study-select:hover {
  border-color: var(--c-border-strong);
}
.results-study-select select {
  border: 0;
  outline: none;
  background: transparent;
  color: var(--c-text);
  font-size: 13px;
  font-weight: 500;
  min-width: 180px;
  cursor: pointer;
}

.results-more {
  position: relative;
}
.results-more__menu {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: 30;
  min-width: 200px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  box-shadow: var(--shadow-md);
  padding: 4px;
}
.results-more__menu button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: 0;
  background: transparent;
  border-radius: var(--r-sm);
  color: var(--c-text);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
}
.results-more__menu button:hover {
  background: var(--c-bg-tint);
}
.results-more__menu button:disabled {
  opacity: .5;
  cursor: not-allowed;
}

/* ===== Empty stage (no study) ===== */
.results-empty-stage {
  min-height: 280px;
  padding: var(--s-6) var(--s-5);
}
.results-empty-stage strong {
  color: var(--c-text);
  font-size: 15px;
  font-weight: 800;
}
.results-empty-stage p {
  max-width: 360px;
  margin: 0;
  color: var(--c-text-3);
  font-size: 13px;
  line-height: 1.6;
}

/* ===== ❷ Summary Strip ===== */
.results-summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}
@media (max-width: 960px) {
  .results-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

.results-summary-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  color: var(--c-text);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--t-fast), background var(--t-fast), box-shadow var(--t-fast);
}
.results-summary-card:hover {
  border-color: var(--c-border-strong);
  box-shadow: var(--shadow-sm);
}
.results-summary-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 2px;
  border-radius: 999px;
  background: var(--card-tone, var(--c-border-strong));
}

.results-summary-card.is-neutral { --card-tone: var(--c-text-3); }
.results-summary-card.is-primary { --card-tone: var(--c-primary); }
.results-summary-card.is-success { --card-tone: var(--c-success); }
.results-summary-card.is-warning { --card-tone: var(--c-warning); }
.results-summary-card.is-danger { --card-tone: var(--c-danger); }
.results-summary-card.is-muted { --card-tone: var(--c-border-strong); }

.results-summary-card__label {
  display: block;
  color: var(--c-text-3);
  font-size: 13px;
}
.results-summary-card__value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
  color: var(--c-text);
  font-variant-numeric: tabular-nums;
  letter-spacing: -.01em;
}

.results-summary-card.is-active {
  border-color: var(--card-tone);
  background: color-mix(in srgb, var(--card-tone) 6%, var(--c-surface));
}
.results-summary-card.is-active .results-summary-card__value,
.results-summary-card.is-active .results-summary-card__label {
  color: var(--card-tone);
}
.results-summary-card.is-active::before {
  width: 3px;
  top: 12px;
  bottom: 12px;
}

/* ===== ❸ Filter Bar ===== */
.results-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
}

.results-search {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 220px;
  height: 34px;
  padding: 0 8px 0 10px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
  color: var(--c-text-3);
  transition: border-color var(--t-fast), background var(--t-fast);
}
.results-search:focus-within {
  border-color: var(--c-primary);
  background: var(--c-surface);
  box-shadow: 0 0 0 3px var(--c-primary-soft);
}
.results-search input {
  flex: 1;
  height: 100%;
  border: 0;
  background: transparent;
  outline: none;
  color: var(--c-text);
  font-size: 13px;
}
.results-search input::-webkit-search-cancel-button { display: none; }
.results-search__clear {
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 50%;
  background: var(--c-bg-tint);
  color: var(--c-text-2);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.results-search__clear:hover { background: var(--c-border-2); color: var(--c-text); }

.filter-dd {
  position: relative;
}
.filter-dd > summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  color: var(--c-text);
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  list-style: none;
  white-space: nowrap;
}
.filter-dd > summary::-webkit-details-marker { display: none; }
.filter-dd > summary:hover {
  border-color: var(--c-border-strong);
  background: var(--c-bg-tint);
}
.filter-dd[open] > summary {
  border-color: var(--c-primary);
  color: var(--c-primary);
  background: var(--c-primary-soft);
}
.filter-dd__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--r-pill);
  background: var(--c-primary);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}
.filter-dd__caret {
  font-size: 10px;
  color: var(--c-text-3);
}
.filter-dd[open] .filter-dd__caret { transform: rotate(180deg); }

.filter-dd__panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 30;
  min-width: 220px;
  max-width: 320px;
  max-height: 320px;
  overflow-y: auto;
  padding: 6px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  box-shadow: var(--shadow-md);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.filter-dd__empty {
  padding: 12px;
  text-align: center;
  color: var(--c-text-3);
  font-size: 12px;
}
.filter-dd__opt {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--r-sm);
  font-size: 13px;
  color: var(--c-text);
  cursor: pointer;
  transition: background var(--t-fast);
}
.filter-dd__opt:hover { background: var(--c-bg-tint); }
.filter-dd__opt input { accent-color: var(--c-primary); }

.results-filter-reset {
  height: 34px;
  padding: 0 10px;
  border: 0;
  background: transparent;
  color: var(--c-primary);
  font-size: 12px;
  cursor: pointer;
  border-radius: var(--r-sm);
}
.results-filter-reset:hover { background: var(--c-primary-soft); }

/* ===== ❹ Toolbar ===== */
.results-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 4px;
  margin-bottom: 8px;
  min-height: 32px;
}

.results-toolbar__count {
  font-size: 13px;
}
.results-toolbar__count strong {
  font-size: 16px;
  color: var(--c-text);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.results-toolbar__count .muted {
  color: var(--c-text-3);
  font-size: 12px;
  margin-left: 4px;
}
.results-toolbar__error {
  color: var(--c-danger);
  font-size: 12px;
  margin-left: 4px;
}

.results-toolbar__right {
  display: flex;
  align-items: center;
  gap: var(--s-3);
  flex-wrap: wrap;
}

.results-select-all {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--c-text-2);
  cursor: pointer;
  user-select: none;
}
.results-select-all input { accent-color: var(--c-primary); }

.results-toolbar__bulk {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 4px 10px;
  border-radius: var(--r);
  background: var(--c-primary-soft);
  border: 1px solid color-mix(in srgb, var(--c-primary) 22%, transparent);
}
.results-toolbar__selection {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-primary);
  white-space: nowrap;
}
.results-toolbar__bulk .btn {
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
}

.results-toolbar-bulk-enter-from,
.results-toolbar-bulk-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.results-toolbar-bulk-enter-active,
.results-toolbar-bulk-leave-active {
  transition: opacity var(--t-fast), transform var(--t-fast);
}

/* ===== ❺ Body / List ===== */
.results-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--s-3);
  align-items: start;
}
.results-body.has-detail {
  grid-template-columns: minmax(0, 1fr) 380px;
}
@media (max-width: 1100px) {
  .results-body.has-detail { grid-template-columns: minmax(0, 1fr); }
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

/* UI Phase (docs_v2/6-05) P1-3: 视图模式 */
.results-list--list {
  /* 维持现有列表样式 */
}
.results-list--grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.results-list--grid .result-row {
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
  padding: 14px;
  border-radius: 10px;
}
.results-list--grid .result-row__right {
  flex-direction: row;
  justify-content: space-between;
  text-align: left;
}

/* UI Phase (docs_v2/6-05): 卡片视图顶部预览占位 */
.result-row__preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 100px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--c-primary-soft) 0%, var(--c-bg-tint) 100%);
  position: relative;
  overflow: hidden;
}
.result-row__preview::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 30%, rgba(63, 94, 143, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 80% 70%, rgba(94, 123, 168, 0.06) 0%, transparent 50%);
  pointer-events: none;
}
.result-row__preview-emoji {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  color: var(--c-primary);
  z-index: 1;
}
.result-row__preview-meta {
  font-size: 12px;
  color: var(--c-text-2);
  z-index: 1;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.result-detail__preview-stats {
  background: var(--c-bg-soft);
  border-radius: 8px;
  padding: 12px 14px;
  color: var(--c-text);
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* 数据类型 chip 横排 */
.results-type-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: var(--c-surface);
  color: var(--c-text-2);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.type-chip:hover {
  border-color: var(--c-primary);
  color: var(--c-primary);
}
.type-chip.is-active {
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
  color: var(--c-primary);
}
.type-chip__icon {
  display: inline-flex;
  align-items: center;
  color: currentColor;
}
.type-chip small {
  color: var(--c-text-3);
  font-size: 11px;
  font-weight: 500;
}
.type-chip.is-active small {
  color: var(--c-primary);
  opacity: 0.8;
}

/* 视图切换 */
.view-mode-switch {
  display: inline-flex;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  overflow: hidden;
}
.view-mode-switch__btn {
  padding: 6px 12px;
  background: var(--c-surface);
  color: var(--c-text-2);
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}
.view-mode-switch__btn:not(:last-child) {
  border-right: 1px solid var(--c-border);
}
.view-mode-switch__btn.is-active {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

/* skeleton */
.results-skeleton {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.results-skeleton-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
}
.results-skeleton-row__check {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: var(--c-bg-tint);
}
.results-skeleton-row__tag {
  width: 60px;
  height: 20px;
  border-radius: var(--r-sm);
  background: var(--c-bg-tint);
}
.results-skeleton-row__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.results-skeleton-row__line {
  height: 12px;
  border-radius: 4px;
  background: var(--c-bg-tint);
}
.results-skeleton-row__line--lg { width: 60%; }
.results-skeleton-row__line--md { width: 40%; }
.results-skeleton-row__line,
.results-skeleton-row__tag,
.results-skeleton-row__check {
  animation: results-pulse 1.4s ease-in-out infinite;
}
@keyframes results-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .55; }
}

/* inline empty */
.results-empty-inline {
  min-height: 200px;
}

/* rows */
.result-row {
  display: grid;
  grid-template-columns: 28px auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  cursor: pointer;
  position: relative;
  transition: border-color var(--t-fast), background var(--t-fast), box-shadow var(--t-fast);
}
.result-row:hover {
  border-color: var(--c-border-strong);
  background: #fafbfd;
}
.result-row:focus-visible {
  outline: none;
  border-color: var(--c-primary);
  box-shadow: 0 0 0 3px var(--c-primary-soft);
}
.result-row.is-active {
  border-color: rgba(63, 94, 143, .42);
  background: var(--c-primary-soft);
  box-shadow: inset 3px 0 0 var(--c-primary), 0 8px 18px rgba(63, 94, 143, .08);
}
.result-row.is-checked {
  background: var(--c-primary-soft);
}

.result-row__check {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.result-row__check input { accent-color: var(--c-primary); }

.result-row__main { min-width: 0; }

.result-row__title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.result-row__title strong {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  line-height: 1.25;
}

.result-row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 12px;
  color: var(--c-text-2);
}
.result-row__meta-item em {
  color: var(--c-text-3);
  font-style: normal;
  font-size: 11px;
  margin-right: 4px;
  font-weight: 500;
}
.result-row__meta-item--mono em + * {
  font-family: var(--ff-mono);
}

.result-row__tags {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.result-row__tag,
.result-row__tag-more {
  height: 18px;
  padding: 0 6px;
  border-radius: var(--r-sm);
  background: var(--c-bg-tint);
  color: var(--c-text-2);
  font-size: 11px;
  font-weight: 500;
  line-height: 18px;
}
.result-row__tag-more {
  background: transparent;
  color: var(--c-text-3);
}

.result-row__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  color: var(--c-text-3);
  font-size: 11px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.result-row__size {
  color: var(--c-text-2);
  font-weight: 500;
  font-size: 12px;
}

/* data type tags */
.data-type-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--r-sm);
  font-size: 11px;
  font-weight: 600;
  background: var(--c-bg-tint);
  color: var(--c-text-2);
  white-space: nowrap;
  flex-shrink: 0;
}
.data-type-tag--lg {
  height: 24px;
  padding: 0 10px;
  font-size: 12px;
}
/* 数据类型标签：颜色给状态、不给分类（铁律 3）——8 种类型一律走中性 .data-type-tag 基样式，靠文字区分，不再每类一色 */

/* ===== ❻ Detail ===== */
.result-detail {
  position: sticky;
  top: 12px;
  display: flex;
  flex-direction: column;
  gap: var(--s-3);
  padding: var(--s-5);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-sm);
  max-height: calc(100vh - 140px);
  overflow-y: auto;
}

.result-detail__hero {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: var(--s-3);
  border-bottom: 1px solid var(--c-border);
}
.result-detail__hero-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-detail__hero-top .btn--icon {
  width: 28px;
  height: 28px;
  font-size: 18px;
  line-height: 1;
}

.result-detail__title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.result-detail__title strong {
  font-size: 16px;
  font-weight: 700;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
  cursor: text;
}
.result-detail__rename {
  border: 0;
  background: transparent;
  color: var(--c-primary);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--r-sm);
}
.result-detail__rename:hover { background: var(--c-primary-soft); }
.result-detail__title .input {
  height: 32px;
  font-size: 14px;
  font-weight: 600;
}

.result-detail__retention {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--c-text-2);
}
.result-detail__retention-label {
  color: var(--c-text-3);
}
.result-detail__retention .input {
  height: 28px;
  padding: 0 8px;
  font-size: 12px;
  min-width: 110px;
  flex: 1;
}

.result-detail__quick-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.result-detail__quick-actions .btn--sm {
  height: 30px;
  font-size: 12px;
}

.result-detail__section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.result-detail__section h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text-2);
}

.result-detail__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: 0;
}
.result-detail__grid > div {
  padding: 8px 10px;
  background: var(--c-bg-soft);
  border-radius: var(--r-sm);
  min-width: 0;
}
.result-detail__grid-wide { grid-column: 1 / -1; }
.result-detail__grid dt {
  font-size: 11px;
  color: var(--c-text-3);
  margin: 0 0 2px;
}
.result-detail__grid dd {
  margin: 0;
  font-size: 13px;
  color: var(--c-text);
  font-weight: 500;
  overflow-wrap: anywhere;
}

.result-detail__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.result-detail__tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 4px 0 8px;
  border-radius: var(--r-pill);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 500;
}
.result-detail__tag-remove {
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--c-primary);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.result-detail__tag-remove:hover {
  background: var(--c-primary);
  color: #fff;
}
.result-detail__tag-input {
  height: 24px;
  min-width: 100px;
  padding: 0 8px;
  border: 1px dashed var(--c-border-2);
  border-radius: var(--r-pill);
  background: transparent;
  outline: none;
  font-size: 12px;
}
.result-detail__tag-input:focus {
  border-style: solid;
  border-color: var(--c-primary);
  background: var(--c-surface);
}

.result-detail__lineage {
  list-style: none;
  margin: 0;
  padding: 0;
  position: relative;
}
.result-detail__lineage::before {
  content: "";
  position: absolute;
  left: 5px;
  top: 12px;
  bottom: 12px;
  width: 1px;
  background: var(--c-border-2);
}
.result-detail__lineage li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
  position: relative;
}
.result-detail__lineage-dot {
  width: 11px;
  height: 11px;
  margin-top: 4px;
  border-radius: 50%;
  background: var(--c-surface);
  border: 2px solid var(--c-border-2);
  flex-shrink: 0;
  z-index: 1;
}
.result-detail__lineage-dot.is-current {
  border-color: var(--c-primary);
  background: var(--c-primary);
  box-shadow: 0 0 0 4px var(--c-primary-soft);
}
.result-detail__lineage-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.result-detail__lineage-label {
  font-size: 11px;
  color: var(--c-text-3);
}
.result-detail__lineage-body strong {
  font-size: 13px;
  color: var(--c-text);
  font-family: var(--ff-mono);
  overflow-wrap: anywhere;
}
.result-detail__lineage li.is-current .result-detail__lineage-body strong {
  font-family: var(--ff-sans);
  color: var(--c-primary);
}
.result-detail__lineage-empty {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-3);
  padding: 6px 0;
}

/* ===== Bulk tag dialog ===== */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(20, 32, 52, .42);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(2px);
}

.bulk-tag-dialog {
  width: min(440px, 92vw);
  background: var(--c-surface);
  border-radius: var(--r-md);
  padding: var(--s-5);
  display: flex;
  flex-direction: column;
  gap: var(--s-3);
  box-shadow: var(--shadow-lg);
}

.bulk-tag-dialog__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.bulk-tag-dialog__head strong {
  font-size: 15px;
  font-weight: 600;
}
.bulk-tag-dialog__hint {
  margin: 0;
  color: var(--c-text-3);
  font-size: 12px;
}
.bulk-tag-dialog__hint code {
  background: var(--c-bg-tint);
  padding: 1px 6px;
  border-radius: var(--r-sm);
  color: var(--c-text-2);
}
.bulk-tag-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
