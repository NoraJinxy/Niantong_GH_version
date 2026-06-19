<template>
  <div class="results-page">
      <!-- ❶ Header -->
      <header class="page__header results-header">
        <div class="results-header__title">
          <h1 class="page__title">结果</h1>
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
                清理未保存的结果
              </button>
            </div>
          </div>
        </div>
      </header>

      <!-- 未选研究项：大空状态 -->
      <section v-if="!selectedStudyId" class="empty results-empty-stage">
        <div class="empty__icon"><AppIcon name="figure" :size="26" /></div>
        <strong>先选择一个研究项</strong>
        <p>结果按研究项组织。选择右上角的研究项就能浏览它产出的所有结果。</p>
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
            {{ formatDataType(opt) }} <small>{{ countByType(opt) }}</small>
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
                  {{ formatDataType(opt) }}
                </span>
              </label>
            </div>
          </details>

          <details class="filter-dd">
            <summary>
              工作流
              <span v-if="filters.workflows.length" class="filter-dd__count">{{ filters.workflows.length }}</span>
              <span class="filter-dd__caret">▾</span>
            </summary>
            <div class="filter-dd__panel filter-dd__panel--wide">
              <div v-if="!workflowOptions.length" class="filter-dd__empty">还没有工作流产出的结果</div>
              <label v-for="opt in workflowOptions" :key="'dd-wf-' + opt.key" class="filter-dd__opt">
                <input type="checkbox" :checked="filters.workflows.includes(opt.key)" @change="toggleFilter('workflows', opt.key)" />
                <span class="wf-opt">
                  <span class="wf-opt__name">{{ opt.label }}</span>
                  <small class="wf-opt__count">{{ opt.count }}</small>
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
            <span class="results-select-hint" aria-hidden="true">单击选 · Ctrl 加选 · Shift 连选</span>
            <button
              class="btn btn--sm btn--ghost"
              type="button"
              :disabled="!filtered.length"
              title="全选当前筛选结果（Ctrl/⌘ + A）"
              @click="selectAll"
            >全选</button>

            <transition name="results-toolbar-bulk">
              <div v-if="selectedIds.size" class="results-toolbar__bulk">
                <span class="results-toolbar__selection">已选 {{ selectedIds.size }} 项</span>
                <button
                  class="btn btn--sm btn--primary"
                  type="button"
                  :title="selectedObserveGroupCount > 1 ? '勾选里有多种类型，将按类型分别打开观察页' : '把勾选的结果叠加到观察页一起看'"
                  @click="observeSelected"
                >
                  <AppIcon name="figure" :size="12" />一起观察<span v-if="selectedObserveGroupCount > 1" class="results-toolbar__obs-split">· {{ selectedObserveGroupCount }} 类</span>
                </button>
                <span class="results-toolbar__bulk-sep" aria-hidden="true"></span>
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
          <div class="results-list" @keydown="onListKeydown">
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
              <strong>这个研究项还没有结果</strong>
              <p>执行一个工作流试试，输出结果会在这里汇总。</p>
              <RouterLink class="btn btn--primary btn--sm" :to="`/studies/${selectedStudyId}/pipeline`" target="_blank" rel="noopener">
                <AppIcon name="pipeline" :size="14" />
                进入工作流
              </RouterLink>
            </div>

            <!-- Empty: no match -->
            <div v-else-if="!filtered.length" class="results-empty-inline">
              <div class="results-empty-inline__icon"><AppIcon name="search" :size="28" /></div>
              <strong>没有符合条件的结果</strong>
              <p>试着调整筛选条件，或清空当前筛选。</p>
              <button class="btn btn--sm" type="button" @click="resetFilters">重置筛选</button>
            </div>

            <!-- 工作流文件夹树：filtered 之后按「工作流·版本」分组；单组退化为非折叠面包屑 -->
            <template v-else>
              <section
                v-for="g in groups"
                :key="g.key"
                class="rtree-folder"
                :class="{ 'is-open': isFolderOpen(g), 'is-orphan': g.isOrphan, 'is-solo': groups.length === 1 }"
              >
                <header
                  class="rtree-folder__head"
                  :class="{ 'is-static': groups.length === 1 }"
                  @click="onFolderHeadClick(g, $event)"
                >
                  <button
                    v-if="groups.length > 1"
                    class="rtree-folder__caret"
                    type="button"
                    tabindex="-1"
                    :aria-expanded="expandedKeys.has(g.key)"
                    aria-label="展开 / 折叠文件夹"
                  >
                    <AppIcon name="chevron-right" :size="12" />
                  </button>
                  <AppIcon class="rtree-folder__icon" name="folder" :size="16" />
                  <span v-if="g.label" class="result-row__wf">
                    <AppIcon name="pipeline" :size="11" />{{ g.label }}
                  </span>
                  <span v-else class="rtree-folder__orphan">未归属工作流（历史结果）</span>
                  <span class="rtree-folder__stats">
                    {{ g.rows.length }} 条 · {{ g.typeCount }} 类 · {{ g.subjectCount }} 被试
                    · <em class="is-kept">保存 {{ g.keptCount }}</em> · {{ formatSize(g.totalSize) }}
                  </span>
                  <button
                    class="rtree-folder__observe"
                    type="button"
                    title="把这个工作流的结果一起观察"
                    @click.stop="observeFolder(g)"
                  >
                    <AppIcon name="figure" :size="12" />
                  </button>
                  <span class="rtree-folder__time">{{ formatTime(g.latest) }}</span>
                </header>

                <div v-show="isFolderOpen(g)" class="rtree-folder__body">
                  <article
                    v-for="row in g.rows"
                    :key="row.id"
                    class="rtree-row"
                    :class="{ 'is-active': activeId === row.id, 'is-selected': selectedIds.has(row.id), 'is-deleted': !!row.deleted_at }"
                    tabindex="0"
                    title="单击选中 · Ctrl 点加选 · Shift 点连选 · 双击打开观察"
                    @click="onRowClick(row, $event)"
                    @dblclick="openObserve(row)"
                    @keydown.enter="openObserve(row)"
                  >
                    <span class="rtree-row__indent" aria-hidden="true"></span>
                    <span class="data-type-tag" :class="dataTypeClass(row.data_type)">
                      {{ formatDataType(row.data_type) }}
                    </span>
                    <strong class="rtree-row__name" :title="rowDisplayName(row)">{{ rowDisplayName(row) }}</strong>
                    <span class="rtree-row__facets">
                      <template v-if="row.bids_subject_id">{{ row.bids_subject_id }}</template>
                      <template v-if="row.condition"> · {{ row.condition }}</template>
                      <em v-if="row.tags && row.tags.length" class="rtree-row__tagn" :title="row.tags.join(', ')">#{{ row.tags.length }}</em>
                    </span>
                    <span class="rtree-row__right">
                      <i
                        v-if="retentionBadgeShown(row)"
                        class="rtree-row__keep"
                        :class="retentionDotClass(row)"
                        :title="retentionLabel(row)"
                      ></i>
                      <span class="rtree-row__size">{{ formatSize(row.file_size) }}</span>
                    </span>
                  </article>
                </div>
              </section>
            </template>
          </div>

          <!-- ❻ Detail Drawer -->
          <aside v-if="activeRow" class="result-detail">
            <header class="result-detail__hero">
              <div class="result-detail__hero-top">
                <span class="data-type-tag data-type-tag--lg" :class="dataTypeClass(activeRow.data_type)">
                  <AppIcon :name="dataTypeIcon(activeRow.data_type)" :size="12" />
                  {{ formatDataType(activeRow.data_type) }}
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
              <button class="btn btn--sm" type="button" @click="openObserve(activeRow)">打开观察</button>
              <RouterLink
                v-if="activeRow.produced_by_execution_id"
                class="btn btn--sm"
                :to="{ path: `/studies/${selectedStudyId}/pipeline`, query: { execution_id: activeRow.produced_by_execution_id } }"
                target="_blank"
                rel="noopener"
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
                <div class="result-detail__grid-wide"><dt>工作流</dt><dd>{{ workflowLabel(activeRow) || '—' }}</dd></div>
                <div><dt>运行</dt><dd>{{ activeRow.execution_seq != null ? `第 ${activeRow.execution_seq} 次` : '—' }}</dd></div>
                <div><dt>产出步骤</dt><dd>{{ activeRow.produced_by_node_type || '—' }}</dd></div>
                <div><dt>被试</dt><dd>{{ activeRow.bids_subject_id || '—' }}</dd></div>
                <div><dt>采集任务</dt><dd>{{ activeRow.task || '—' }}</dd></div>
                <div><dt>会话</dt><dd>{{ activeRow.session || '—' }}</dd></div>
                <div><dt>实验条件</dt><dd>{{ activeRow.condition || '—' }}</dd></div>
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
                <div><dt>结果 ID</dt><dd>{{ activeRow.id }}</dd></div>
                <div v-if="activeRow.produced_by_execution_id"><dt>来源运行 ID</dt><dd>{{ activeRow.produced_by_execution_id }}</dd></div>
                <div v-if="activeRow.produced_by_job_id"><dt>节点任务 ID</dt><dd>{{ activeRow.produced_by_job_id }}</dd></div>
                <div v-if="activeRow.data_type"><dt>数据类型枚举</dt><dd>{{ activeRow.data_type }}</dd></div>
                <div><dt>保存</dt><dd>{{ activeRow.keep ? '是' : '否' }}</dd></div>
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
          <strong>给 {{ selectedIds.size }} 条结果加标签</strong>
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
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import TechnicalFold from '@/components/TechnicalFold.vue'
import { pipelineApi } from '@/api/pipelines'
import { formatDataType } from '@/composables/pipeline/pipelineFormatters'
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
const router = useRouter()
const selectedStudyId = computed(() => String(route.params.studyId || ''))
const datasets = ref<StudyOutput[]>([])
// 结果页只展示有意义的输出：保存 / 缓存 / 回收站；滤掉「纯临时」（不保存、系统也不缓存的跑完即清中间废料）
const visibleDatasets = computed(() =>
  datasets.value.filter((d) => d.keep || d.cache_eligible || Boolean(d.deleted_at)),
)
const loading = ref(false)
const error = ref('')

const searchText = ref('')

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
  // 来源工作流筛选：每项是 workflowKey(row) = `pipeline_name pipeline_version`，
  // 即「某工作流的某一版」。这样筛选直接回答「哪个工作流哪一版报出来的结果」。
  workflows: [] as string[],
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

// 按 data_type 路由到对应观察页（参数统一 studyId + study_output_id）
function observeRoute(row: { id: string; data_type?: string | null; display_name?: string | null }) {
  const dt = String(row.data_type || '').toLowerCase()
  const query: Record<string, string> = {
    studyId: selectedStudyId.value,
    study_output_id: row.id,
    name: row.display_name || row.data_type || '结果',
  }
  if (dt === 'tfr') return { path: '/observe/tfr', query }
  // psd 与 grand average 都是频域功率谱 → 频域观察页（grand average 复用 /psd，渲染均值曲线）
  if (dt === 'psd' || dt === 'psd_grandavg') return { path: '/observe/psd', query }
  return { path: '/observe/waveform', query: { ...query, type: row.data_type || '' } }
}

// 在新标签页打开一个 href（与画布节点双击一致）。用 <a target="_blank"> 模拟点击，
// 比 window.open 更可靠——浏览器按「新标签」处理、可拖进标签栏并排，而非独立弹窗。
function openHrefInNewTab(href: string) {
  const link = document.createElement('a')
  link.href = href
  link.target = '_blank'
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

// 查看单条结果：打开它对应模态的观察页。
function openObserve(row: { id: string; data_type?: string | null; display_name?: string | null } | null) {
  if (!row) return
  openHrefInNewTab(router.resolve(observeRoute(row)).href)
}

// 多选「一起观察」：把勾选的结果按观察页（模态）分组——同模态的拼成逗号串
// study_output_id 叠加进同一页（观察页原生支持多产物对比）；跨模态则各开一页。
function observeSelected() {
  const rows = datasets.value.filter((d) => selectedIds.has(d.id) && !d.deleted_at)
  if (!rows.length) return
  const groups = new Map<string, StudyOutput[]>()
  for (const row of rows) {
    const path = observeRoute(row).path
    const arr = groups.get(path)
    if (arr) arr.push(row)
    else groups.set(path, [row])
  }
  for (const group of groups.values()) {
    const base = observeRoute(group[0])
    const query = {
      ...(base.query as Record<string, string>),
      study_output_id: group.map((r) => r.id).join(','),
      name: group.length > 1 ? `${group.length} 个结果对比` : (group[0].display_name || group[0].data_type),
    }
    openHrefInNewTab(router.resolve({ path: base.path, query }).href)
  }
}

// 勾选里横跨几种观察模态（>1 时「一起观察」会分多页打开，按钮上给出提示）。
const selectedObserveGroupCount = computed(() => {
  const paths = new Set<string>()
  for (const d of datasets.value) {
    if (selectedIds.has(d.id) && !d.deleted_at) paths.add(observeRoute(d).path)
  }
  return paths.size
})

// === 来源工作流（pipeline 名 · 版本）===
// 一条结果的来源标识：同一工作流的不同版本视为不同来源。用   当分隔避免与名称里的字符撞。
function workflowKey(row: { pipeline_name?: string | null; pipeline_version?: number | null }): string {
  return `${row.pipeline_name || ''} ${row.pipeline_version ?? ''}`
}

// 行内/详情展示用：「工作流名 · v版本」。两者都缺时返回空串（调用方自行隐藏胶囊）。
function workflowLabel(row: { pipeline_name?: string | null; pipeline_version?: number | null }): string {
  const name = row.pipeline_name?.trim()
  const ver = row.pipeline_version
  if (!name && ver == null) return ''
  const verPart = ver == null ? '' : ` · v${ver}`
  return `${name || '工作流'}${verPart}`
}

// 筛选下拉的工作流选项：去重的 (名, 版本) 对，带计数；按名升序、同名版本降序（新版本在前）。
const workflowOptions = computed(() => {
  const map = new Map<string, { key: string; label: string; name: string; version: number | null; count: number }>()
  for (const d of visibleDatasets.value) {
    if (!d.pipeline_name && d.pipeline_version == null) continue
    const key = workflowKey(d)
    const existing = map.get(key)
    if (existing) existing.count++
    else map.set(key, {
      key,
      label: workflowLabel(d) || '未知工作流',
      name: d.pipeline_name || '',
      version: d.pipeline_version ?? null,
      count: 1,
    })
  }
  return Array.from(map.values()).sort((a, b) =>
    a.name.localeCompare(b.name) || (b.version ?? -1) - (a.version ?? -1),
  )
})

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
    if (filters.workflows.length && !filters.workflows.includes(workflowKey(d))) return false
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
    || filters.workflows.length
    || filters.bids_subject_ids.length
    || filters.tasks.length
    || filters.status !== 'all'
    || filters.tags.length,
  ),
)

// === 结果文件夹分组（按「工作流·版本」收成文件夹树：更紧凑、一眼见来源）===
interface ResultFolder {
  key: string
  label: string
  rows: StudyOutput[]
  latest: string
  totalSize: number
  typeCount: number
  subjectCount: number
  keptCount: number
  isOrphan: boolean
}

// 在 filtered 之上再聚合一层：一个文件夹 = 一个 (pipeline_name, pipeline_version)。
// 真实工作流按最近产出时间倒序（刚跑完的置顶），无归属的历史结果永远沉底。
const groups = computed<ResultFolder[]>(() => {
  const map = new Map<string, StudyOutput[]>()
  for (const row of filtered.value) {
    const k = workflowKey(row)
    const arr = map.get(k)
    if (arr) arr.push(row)
    else map.set(k, [row])
  }
  const out: ResultFolder[] = []
  for (const [key, rows] of map) {
    const head = rows[0]
    out.push({
      key,
      label: workflowLabel(head),
      rows,
      isOrphan: !head.pipeline_name && head.pipeline_version == null,
      latest: rows.reduce((m, r) => (r.created_at && r.created_at > m ? r.created_at : m), ''),
      totalSize: rows.reduce((s, r) => s + (r.file_size || 0), 0),
      typeCount: new Set(rows.map((r) => r.data_type)).size,
      subjectCount: new Set(rows.map((r) => r.bids_subject_id).filter(Boolean)).size,
      keptCount: rows.filter((r) => r.keep && !r.deleted_at).length,
    })
  }
  return out.sort((a, b) =>
    (a.isOrphan ? 1 : 0) - (b.isOrphan ? 1 : 0)
    || (b.latest < a.latest ? -1 : b.latest > a.latest ? 1 : 0),
  )
})

// 文件夹展开态。智能默认：结果少 / 组少时全展开（小研究项免折腾），否则只展开最新一组；
// 搜索或任意筛选激活时强制展开所有命中文件夹（否则「搜了却看见一排折叠文件夹」=搜索失效）。
const expandedKeys = reactive(new Set<string>())
const userTouchedExpand = ref(false)

const forcedExpandKeys = computed<Set<string>>(() => {
  if (!hasActiveFilters.value) return new Set<string>()
  return new Set(groups.value.map((g) => g.key))
})

function computeDefaultExpanded(gs: ResultFolder[]): Set<string> {
  const keys = new Set<string>()
  if (!gs.length) return keys
  if (hasActiveFilters.value || gs.length <= 2 || filtered.value.length <= 12) {
    for (const g of gs) keys.add(g.key)
  } else {
    keys.add(gs[0].key)
  }
  return keys
}

// groups / 筛选态变化时：用户没手动开合过就重算默认；手动过则只「并集」补上命中即展开，不覆盖用户意图。
watch(
  [groups, forcedExpandKeys],
  () => {
    if (!userTouchedExpand.value) {
      const def = computeDefaultExpanded(groups.value)
      expandedKeys.clear()
      for (const k of def) expandedKeys.add(k)
    } else {
      for (const k of forcedExpandKeys.value) expandedKeys.add(k)
    }
  },
  { immediate: true },
)

// 单组时恒展开、无折叠外壳的折叠概念，所以视为「常开」。
function isFolderOpen(g: ResultFolder): boolean {
  return groups.value.length === 1 || expandedKeys.has(g.key)
}

function toggleExpand(key: string) {
  userTouchedExpand.value = true
  if (expandedKeys.has(key)) expandedKeys.delete(key)
  else expandedKeys.add(key)
}

// 普通点文件夹头 = 展开/折叠；Ctrl/⌘ 或 Shift 点 = 选中整组（替代被去掉的整组复选框）。
function onFolderHeadClick(g: ResultFolder, event: MouseEvent) {
  if (event.ctrlKey || event.metaKey || event.shiftKey) {
    for (const r of g.rows) selectedIds.add(r.id)
    const last = g.rows[g.rows.length - 1]
    if (last) {
      // 折叠中的组没有可见锚点供后续 Shift 连选，置空避免下次 Shift 落到隐形锚点
      selectionAnchorId.value = isFolderOpen(g) ? last.id : ''
      setActive(last.id)
    }
    return
  }
  if (groups.value.length === 1) return
  toggleExpand(g.key)
}

// 整组一起观察：复用现成 selectedIds 与 observeSelected，批量条逻辑零改。
function observeFolder(g: ResultFolder) {
  for (const r of g.rows) if (!r.deleted_at) selectedIds.add(r.id)
  observeSelected()
}

// 保留徽标只在「非默认态」显示（保存=默认态不显徽标，降噪；已删除/不保存才点一个状态色点）。
function retentionBadgeShown(row: StudyOutput): boolean {
  return Boolean(row.deleted_at) || Boolean(row.purged_at) || !row.keep
}
function retentionDotClass(row: StudyOutput): string {
  if (row.deleted_at || row.purged_at) return 'is-deleted'
  return 'is-transient'
}

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
  expandedKeys.clear()
  userTouchedExpand.value = false
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
      // 只拉「有意义」的结果（keep/cache/已删除）；隐藏的纯临时中间产物（filtered_raw/raw/中间 psd 等）
      // 本就不展示也不计数，服务端先滤掉，避免拉回上百行废料拖慢加载。
      visible_only: true,
      limit: 1000,
      offset: 0,
    }
    const res = await pipelineApi.listStudyOutputs(selectedStudyId.value, query)
    datasets.value = res.data.study_outputs
  } catch (err) {
    datasets.value = []
    error.value = describeError(err, '结果读取失败')
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
  filters.workflows = []
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

// 文件管理器式选择：单击=只选此项；Ctrl/⌘ 点=加选/减选；Shift 点=从锚点连选（按可见顺序）。
const selectionAnchorId = ref('')
// 当前可见（已展开文件夹内）行的显示顺序，供 Shift 连选取区间。
const visibleRowIds = computed<string[]>(() => {
  const ids: string[] = []
  for (const g of groups.value) {
    if (isFolderOpen(g)) for (const r of g.rows) ids.push(r.id)
  }
  return ids
})

function onRowClick(row: StudyOutput, event: MouseEvent) {
  const additive = event.ctrlKey || event.metaKey
  if (event.shiftKey && selectionAnchorId.value) {
    const order = visibleRowIds.value
    const a = order.indexOf(selectionAnchorId.value)
    const b = order.indexOf(row.id)
    if (a !== -1 && b !== -1) {
      if (!additive) selectedIds.clear()
      for (let i = Math.min(a, b); i <= Math.max(a, b); i++) selectedIds.add(order[i])
    } else {
      selectedIds.clear()
      selectedIds.add(row.id)
      selectionAnchorId.value = row.id
    }
    // Shift 连选保持锚点不动：连续 Shift 点从同一锚点扩 / 缩选区
  } else if (additive) {
    if (selectedIds.has(row.id)) selectedIds.delete(row.id)
    else selectedIds.add(row.id)
    selectionAnchorId.value = row.id
  } else {
    selectedIds.clear()
    selectedIds.add(row.id)
    selectionAnchorId.value = row.id
  }
  setActive(row.id)
}

function selectAll() {
  for (const row of filtered.value) selectedIds.add(row.id)
}

function onListKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && (event.key === 'a' || event.key === 'A')) {
    event.preventDefault()
    selectAll()
  } else if (event.key === 'Escape') {
    clearSelection()
  }
}

function clearSelection() {
  selectedIds.clear()
  selectionAnchorId.value = ''
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
  // 缓存/临时是内部保留态，对用户统一收敛成「不保存」（与筛选标签同口径）
  return '不保存'
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

/* 工作流名可能较长，给这个面板更宽的上限 */
.filter-dd__panel--wide {
  min-width: 260px;
  max-width: 380px;
}
.wf-opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.wf-opt__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wf-opt__count {
  flex-shrink: 0;
  color: var(--c-text-3);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

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
/* 「一起观察」与其余批量操作之间的细分隔 */
.results-toolbar__bulk-sep {
  width: 1px;
  height: 18px;
  background: color-mix(in srgb, var(--c-primary) 24%, transparent);
}
.results-toolbar__obs-split {
  margin-left: 4px;
  font-weight: 500;
  opacity: .85;
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

/* 来源工作流胶囊：折叠头一眼看清「哪个工作流 · 哪一版」。中性底色 + 主色文字，不抢标题。 */
.result-row__wf {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex-shrink: 0;
  max-width: 240px;
  height: 19px;
  padding: 0 7px;
  border-radius: var(--r-sm);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.result-row__wf :deep(svg) { flex-shrink: 0; opacity: .85; }

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

/* ===== 结果文件夹树（按工作流·版本分组，紧凑） ===== */
.rtree-folder {
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  overflow: hidden;
}
.rtree-folder.is-orphan { background: var(--c-bg-soft); }

/* 折叠头 40px · sticky 吸顶（超多组滚动时当前文件夹身份不丢） */
.rtree-folder__head {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 12px;
  background: var(--c-surface);
  border-bottom: 1px solid transparent;
  cursor: pointer;
  user-select: none;
}
.rtree-folder.is-open .rtree-folder__head { border-bottom-color: var(--c-border); }
.rtree-folder__head:hover { background: var(--c-bg-tint); }
.rtree-folder__head.is-static,
.rtree-folder__head.is-static:hover { cursor: default; background: var(--c-surface); }

.rtree-folder__caret {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: 0;
  background: transparent;
  color: var(--c-text-3);
  cursor: pointer;
  flex-shrink: 0;
  transition: transform var(--t-fast);
}
.rtree-folder.is-open .rtree-folder__caret { transform: rotate(90deg); }

.rtree-folder__icon { color: var(--c-text-3); flex-shrink: 0; }

.rtree-folder__orphan {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-3);
  flex-shrink: 0;
}

/* 折叠态摘要名片：全程中性文字（铁律3：颜色给状态不给分类），唯一彩色是「保存 N」的状态色 */
.rtree-folder__stats {
  min-width: 0;
  color: var(--c-text-3);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rtree-folder__stats .is-kept {
  color: var(--c-success);
  font-style: normal;
  font-weight: 600;
}

.rtree-folder__observe {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  margin-left: auto;
  border: 0.5px solid transparent;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--c-text-2);
  cursor: pointer;
  opacity: 0;
  flex-shrink: 0;
  transition: opacity var(--t-fast), background var(--t-fast), color var(--t-fast);
}
.rtree-folder__head:hover .rtree-folder__observe { opacity: 1; }
.rtree-folder__observe:hover {
  background: var(--c-primary-soft);
  color: var(--c-primary);
  border-color: var(--c-border);
}

.rtree-folder__time {
  color: var(--c-text-3);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  flex-shrink: 0;
}

.rtree-folder__body { display: flex; flex-direction: column; }

/* 展开后单行 32px · 缩进列里一条竖向 guide line 给「树」的隶属感 */
.rtree-row {
  display: grid;
  grid-template-columns: 18px auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  height: 32px;
  padding: 0 12px;
  border-top: 1px solid color-mix(in srgb, var(--c-border) 55%, transparent);
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  transition: background var(--t-fast);
}
.rtree-folder__body > .rtree-row:first-child { border-top: 0; }
.rtree-row:hover { background: #fafbfd; }
.rtree-row:focus-visible { outline: none; background: var(--c-primary-soft); }
.rtree-row.is-active { background: var(--c-primary-soft); box-shadow: inset 3px 0 0 var(--c-primary); }
.rtree-row.is-selected { background: var(--c-primary-soft); }
.rtree-row.is-deleted { opacity: 0.6; }

.rtree-row__indent {
  align-self: stretch;
  justify-self: center;
  width: 1px;
  background: var(--c-border);
}

.rtree-row .data-type-tag { height: 18px; padding: 0 7px; font-size: 11px; }

.rtree-row__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.rtree-row__facets {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 240px;
  min-width: 0;
  color: var(--c-text-2);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rtree-row__tagn { font-style: normal; color: var(--c-text-3); }

.rtree-row__right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-self: end;
  color: var(--c-text-2);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.rtree-row__keep {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--c-text-3);
}
.rtree-row__keep.is-deleted { background: var(--c-danger); }
.rtree-row__keep.is-transient { background: var(--c-text-3); }

.results-select-hint {
  font-size: 11px;
  color: var(--c-text-3);
  white-space: nowrap;
}

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
