<template>
  <div class="pipeline-page" @pointerdown="closePipelineContextMenu">
      <!-- 拖宽手柄:放在抽屉外、跨在「抽屉↔画布」的缝上,避开抽屉 overflow 裁剪与滚动条争点击 -->
      <div
        v-if="libraryVisible"
        class="drawer-handle drawer-handle--seam-left"
        :class="{ 'is-dragging': drawerDragging === 'library' }"
        :style="{ left: libraryWidth + 'px' }"
        title="拖动调整左侧节点库宽度"
        @mousedown="startDrawerDrag('library', $event)"
      ></div>
      <aside
        class="library"
        :class="{ 'is-hidden': !libraryVisible }"
        :style="{ width: libraryWidth + 'px' }"
      >
        <section class="panel panel--fill">
          <div class="panel__title">
            节点库
            <span>{{ filteredNodeSpecs.length }}</span>
          </div>
          <div class="search">
            <AppIcon name="search" :size="14" />
            <input v-model="nodeSearch" type="search" placeholder="搜索节点" />
          </div>

          <div v-if="loadingNodes" class="state-text">正在加载节点定义...</div>
          <div v-else-if="nodeLoadError" class="state-text state-text--error">{{ nodeLoadError }}</div>
          <div v-else class="node-groups">
            <div v-for="group in groupedNodeSpecs" :key="group.category" class="node-group">
              <button class="group-head" type="button" @click="toggleGroup(group.category)">
                <span class="group-dot" :style="{ background: categoryColor(group.category) }"></span>
                <span>{{ group.category }}</span>
                <small>{{ group.nodes.length }}</small>
              </button>
              <div v-show="groupOpen[group.category] !== false" class="group-body">
                <button
                  v-for="spec in group.nodes"
                  :key="spec.type"
                  class="node-template"
                  type="button"
                  draggable="true"
                  title="拖到画布添加（或双击）"
                  @dblclick="addNode(spec)"
                  @dragstart="handleNodeDragStart(spec, $event)"
                >
                  <span class="node-template__title">{{ spec.title }}</span>
                  <span class="node-template__desc">{{ spec.description }}</span>
                </button>
              </div>
            </div>
          </div>
        </section>
      </aside>

      <main
        class="editor"
        :style="{
          paddingLeft: libraryVisible ? libraryWidth + 'px' : '0px',
          paddingRight: inspectorVisible ? inspectorWidth + 'px' : '0px'
        }"
      >
        <header class="toolbar">
          <div class="toolbar-row toolbar-row--context">
            <label class="toolbar-select">
              <span>工作流</span>
              <select
                :value="selectedPipelineId"
                :disabled="!selectedStudyId || loadingPipelines"
                @change="handlePipelineChange"
              >
                <option value="">新建工作流</option>
                <option v-for="pipeline in pipelines" :key="pipeline.id" :value="String(pipeline.id)">
                  {{ pipeline.name }} v{{ pipeline.version }}
                </option>
              </select>
            </label>
            <button class="button button--subtle" type="button" :disabled="!selectedStudyId" @click="startNewPipeline()">
              <AppIcon name="plus" :size="14" />
              新建工作流
            </button>
          </div>

          <div class="toolbar-row toolbar-row--actions">
            <button
              class="button toolbar-toggle"
              :class="{ 'is-active': libraryVisible }"
              type="button"
              title="切换节点库"
              @click="toggleLibrary"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
                <line x1="5.5" y1="2.5" x2="5.5" y2="13.5" stroke="currentColor" stroke-width="1.2"/>
                <rect x="2" y="3" width="3" height="10" fill="currentColor" opacity="0.25"/>
              </svg>
            </button>
            <div class="workflow-name">
              <AppIcon name="pipeline" :size="16" />
              <input
                v-model="pipelineName"
                class="name-input"
                type="text"
                placeholder="工作流名称"
                @input="markDirty"
              />
              <span v-if="dirty" class="badge badge--warn">未保存</span>
              <span v-else-if="currentPipeline" class="badge">版本 {{ currentPipeline.version }}</span>
              <span v-if="currentPipeline" class="badge">{{ formatPipelineStatus(currentPipeline.status) }}</span>
            </div>

            <div class="toolbar-actions">
              <button class="button" type="button" :disabled="!canSave || saving" @click="savePipeline">
                <AppIcon name="check" :size="14" />
                保存
              </button>
              <button class="button" type="button" :disabled="!selectedStudyId || saving" @click="validatePipeline">
                校验
              </button>
              <button
                class="button button--primary"
                type="button"
                :disabled="!canOpenRunDialog"
                :title="runDisabledReason"
                @click="openRunDialog"
              >
                运行
              </button>
              <button
                class="button button--subtle"
                type="button"
                :disabled="!latestPipelineExecution"
                :title="latestPipelineExecution ? '查看运行详情' : '暂无运行记录'"
                @click="runDrawerOpen = !runDrawerOpen"
              >
                <template v-if="latestPipelineExecution">
                  运行 #{{ latestPipelineExecution.execution_seq }}
                </template>
                <template v-else>暂无运行</template>
              </button>
              <button class="button button--danger" type="button" :disabled="!selectedNode" @click="deleteSelectedNode">
                <AppIcon name="trash" :size="14" />
                删除节点
              </button>
              <button
                class="button toolbar-toggle"
                :class="{ 'is-active': inspectorVisible }"
                type="button"
                title="切换参数面板"
                @click="toggleInspector"
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
                  <line x1="10.5" y1="2.5" x2="10.5" y2="13.5" stroke="currentColor" stroke-width="1.2"/>
                  <rect x="11" y="3" width="3" height="10" fill="currentColor" opacity="0.25"/>
                </svg>
              </button>
            </div>
          </div>
        </header>

        <section class="canvas">
          <div
            ref="liteGraphShell"
            class="litegraph-shell"
            @dragover.prevent
            @drop.prevent="handleCanvasDrop"
          >
            <canvas ref="liteGraphCanvasEl" class="litegraph-canvas"></canvas>
            <div
              v-if="pipelineContextMenu.open"
              class="pipeline-context-menu"
              :style="{ left: `${pipelineContextMenu.x}px`, top: `${pipelineContextMenu.y}px` }"
              @pointerdown.stop
              @click.stop
              @contextmenu.prevent.stop
            >
              <button
                v-for="item in pipelineContextMenu.items"
                :key="item.key"
                class="pipeline-context-menu__item"
                :class="{ 'is-danger': item.danger }"
                type="button"
                :disabled="item.disabled"
                @click="runPipelineContextAction(item)"
              >
                {{ item.label }}
              </button>
            </div>
            <div v-if="liteGraphReady" class="canvas-overlay">
              <div class="canvas-overlay__meta">
                <span>{{ definition.graph.nodes.length }} 节点</span>
                <span>{{ definition.graph.links.length }} 连线</span>
              </div>
              <div class="canvas-overlay__actions">
                <button class="canvas-tool" type="button" title="自动排列节点并适应屏幕" @click="autoArrangeGraph({ markAsDirty: true })">整理布局</button>
                <button class="canvas-tool" type="button" title="缩放到全部节点可见" @click="fitGraphToView()">适应</button>
                <button class="canvas-tool" type="button" title="缩放回 100%" @click="resetLiteGraphZoom">100%</button>
                <button class="canvas-tool" type="button" title="导出为静态 HTML 文件" @click="exportPipelineHtml">导出</button>
              </div>
            </div>
            <div v-if="!liteGraphReady" class="empty-canvas">
              <strong>正在初始化画布</strong>
              <span>节点画布加载完成后即可拖拽、缩放和连线。</span>
            </div>
            <div v-else-if="definition.graph.nodes.length === 0" class="empty-canvas">
              <strong>从左侧添加节点</strong>
              <span>从左侧拖动节点到画布（或双击节点），再从输出端口拖到输入端口建立连线。</span>
            </div>
          </div>
        </section>

        <footer class="status-panel">
          <div class="status-panel__summary">
            <span>节点 {{ definition.graph.nodes.length }}</span>
            <span>连线 {{ definition.graph.links.length }}</span>
            <span v-if="statusMessage">{{ statusMessage }}</span>
          </div>
          <div v-if="validation" class="validation">
            <span :class="validation.valid ? 'ok' : 'error'">
              {{ validation.valid ? '校验通过' : '校验未通过' }}
            </span>
            <span v-for="issue in [...validation.errors, ...validation.warnings]" :key="issue.code + issue.message">
              {{ issue.severity }} · {{ issue.message }}
            </span>
          </div>
          <div v-if="latestPipelineExecution" class="validation">
            <span :class="latestPipelineExecution.status === 'completed' ? 'ok' : latestPipelineExecution.status === 'waiting_user_input' ? 'warn' : 'error'">
              运行 #{{ latestPipelineExecution.execution_seq }} {{ formatPipelineExecutionStatus(latestPipelineExecution.status) }}
            </span>
            <span>{{ latestPipelineExecution.node_count }} 节点 · {{ latestPipelineExecution.dataset_count }} 数据集</span>
            <span v-if="runPolling">轮询中</span>
            <span v-if="runArtifacts.length">{{ runArtifacts.length }} 个产物</span>
            <span v-for="issue in latestPipelineExecutionIssues" :key="issue">{{ issue }}</span>
          </div>
          <div v-if="runPollingError" class="validation">
            <span class="error">{{ runPollingError }}</span>
          </div>
          <!-- UI Phase (docs_v2/6-05) P1-2: 步骤进度可视化 -->
          <div v-if="executionPanelJobRows.length" class="run-stepbar">
            <ol class="run-stepbar__list">
              <li
                v-for="(job, idx) in executionPanelJobRows"
                :key="job.id"
                class="run-stepbar__step"
                :class="`is-${stepVisualState(job.status)}`"
                :title="`${job.node_title || job.node_id} · ${formatJobStatus(job.status)}`"
              >
                <span class="run-stepbar__dot">{{ stepIcon(job.status) }}</span>
                <span class="run-stepbar__label">{{ job.node_title || job.node_id }}</span>
                <span
                  v-if="idx < executionPanelJobRows.length - 1"
                  class="run-stepbar__connector"
                  :class="{ 'is-done': isStepDone(job.status) }"
                ></span>
              </li>
            </ol>
          </div>

          <details v-if="executionPanelJobRows.length" class="run-panel-details">
            <summary>步骤详情</summary>
            <div class="run-panel">
              <div v-for="job in executionPanelJobRows" :key="job.id" class="run-node-row">
                <span class="run-node-row__title">{{ job.node_title || job.node_id }}</span>
                <span class="status-pill" :class="jobStatusClass(job.status)">
                  {{ formatJobStatus(job.status) }}
                </span>
                <span>{{ formatDurationMs(job.duration_ms) }}</span>
                <span>{{ artifactCountForJob(job.id) }} 个产物</span>
                <span v-if="jobErrorMessage(job)" class="run-node-row__error">
                  {{ jobErrorMessage(job) }}
                </span>
              </div>
            </div>
          </details>
        </footer>
      </main>

      <div v-if="runDialogOpen" class="modal-overlay" @click.self="closeRunDialog">
        <section class="run-dialog" aria-modal="true" role="dialog">
          <header class="run-dialog__head">
            <div>
              <h3>创建运行</h3>
              <p>{{ pipelineName || '未命名工作流' }} · {{ formatPipelineStatus(currentPipelineStatus) }}</p>
            </div>
            <button class="icon-button" type="button" aria-label="关闭" @click="closeRunDialog">×</button>
          </header>

          <div class="run-dialog__grid">
            <label class="field">
              <span>运行模式</span>
              <select v-model="executionMode" class="control">
                <option v-for="option in EXECUTION_MODE_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <small>{{ executionModeDescription }}</small>
            </label>
          </div>

          <div class="run-dialog__notice" :class="{ 'is-error': !executionModeAllowed }">
            <strong>{{ executionModeAllowed ? '可以创建运行' : '当前状态不允许运行' }}</strong>
            <span>{{ runDisabledReason || runDialogSummary }}</span>
          </div>

          <div class="run-dialog__override">
            <strong>运行数据覆盖</strong>
            <span>{{ runSelectionOverrideSummaryText }}</span>
            <div v-if="runSelectionOverrideItems.length" class="run-dialog__override-list">
              <article v-for="item in runSelectionOverrideItems" :key="item.nodeId">
                <div>
                  <strong>{{ item.nodeTitle }}</strong>
                  <small>{{ item.sourceLabel }}</small>
                </div>
                <span>
                  {{ item.datasetCount }} datasets
                  <template v-if="item.fileCount"> · {{ item.fileCount }} files</template>
                </span>
              </article>
            </div>
          </div>

          <footer class="run-dialog__actions">
            <button class="button" type="button" @click="closeRunDialog">取消</button>
            <button class="button button--primary" type="button" :disabled="!canSubmitRun" @click="submitRunDialog">
              创建运行
            </button>
          </footer>
        </section>
      </div>

      <aside v-if="runDrawerOpen && latestPipelineExecution" class="run-drawer">
        <header class="run-drawer__head">
          <strong>运行 #{{ latestPipelineExecution.execution_seq }}</strong>
          <span class="status-pill" :class="jobStatusClass(latestPipelineExecution.status)">
            {{ formatPipelineExecutionStatus(latestPipelineExecution.status) }}
          </span>
          <button class="icon-button" type="button" @click="runDrawerOpen = false" aria-label="关闭">×</button>
        </header>
        <section class="panel run-detail-panel">
          <div class="panel__title">
            运行记录
            <span>运行 #{{ latestPipelineExecution.execution_seq }}</span>
          </div>
          <div class="run-detail-summary">
            <span class="status-pill" :class="jobStatusClass(latestPipelineExecution.status)">
              {{ formatPipelineExecutionStatus(latestPipelineExecution.status) }}
            </span>
            <small>{{ formatExecutionMode(latestPipelineExecution.execution_mode) }}</small>
          </div>
          <div class="run-action-strip">
            <button
              class="button button--subtle"
              type="button"
              :disabled="!canCancelLatestExecution || Boolean(executionActionLoading)"
              :title="latestExecutionActionHint"
              @click="cancelLatestExecution"
            >
              取消运行
            </button>
            <button
              class="button button--subtle"
              type="button"
              :disabled="!canRetryLatestExecution || Boolean(executionActionLoading)"
              :title="latestExecutionActionHint"
              @click="retryLatestExecution"
            >
              重试运行
            </button>
          </div>
          <div class="state-text">{{ runLockSummary }}</div>
          <div class="run-detail-tabs">
            <button
              v-for="tab in executionDetailTabs"
              :key="tab.key"
              type="button"
              :class="{ 'is-active': executionDetailTab === tab.key }"
              @click="selectExecutionDetailTab(tab.key)"
            >
              {{ tab.label }}
            </button>
          </div>

          <div v-if="executionDetailTab === 'summary'" class="run-detail-body">
            <div class="run-kv">
              <span>状态</span><strong>{{ formatPipelineExecutionStatus(latestPipelineExecution.status) }}</strong>
              <span>节点</span><strong>{{ latestPipelineExecution.node_count }}</strong>
              <span>输入</span><strong>{{ activeExecutionDetail?.inputs?.length || latestPipelineExecution.dataset_count }}</strong>
              <span>Artifact</span><strong>{{ runArtifacts.length }}</strong>
            </div>
            <div class="state-text">运行记录保存了定义快照、输入快照、任务事件和输出索引；普通详情和血缘分开读取。</div>
          </div>

          <div v-else-if="executionDetailTab === 'inputs'" class="run-detail-body">
            <div v-if="!activeExecutionDetail?.inputs?.length" class="state-text">暂无输入快照。</div>
            <div v-for="input in activeExecutionDetail?.inputs || []" :key="input.id" class="compact-row">
              <strong>{{ input.node_id || input.input_slot }}</strong>
              <span>{{ input.input_kind }} · {{ input.file_role || 'file' }}</span>
              <small>{{ input.logical_path || input.storage_uri || input.dataset_file_id || input.dataset_id || '-' }}</small>
            </div>
          </div>

          <div v-else-if="executionDetailTab === 'jobs'" class="run-detail-body">
            <div v-for="job in executionPanelJobRows" :key="job.id" class="compact-row">
              <strong>{{ job.node_title || job.node_id }}</strong>
              <span>{{ formatJobStatus(job.status) }} · {{ formatDurationMs(job.duration_ms) }}</span>
              <small>{{ artifactCountForJob(job.id) }} 个产物</small>
            </div>
          </div>

          <div v-else-if="executionDetailTab === 'tasks'" class="run-detail-body">
            <div v-if="!activeExecutionDetail?.tasks?.length" class="state-text">暂无任务事件。</div>
            <div v-for="task in activeExecutionDetail?.tasks || []" :key="task.id" class="compact-row compact-row--task">
              <div class="compact-row__main">
                <strong>{{ task.task_type }}</strong>
                <span>{{ formatTaskStatus(task.status) }} · {{ Number(task.progress || 0).toFixed(0) }}%</span>
                <small>
                  {{ taskEventsForTask(task).length }} events · {{ shortId(task.id) }}
                  <template v-if="isPipelineExecutionTask(task)"> · 工作流执行任务请通过运行重试</template>
                </small>
              </div>
              <div class="task-actions">
                <button type="button" :disabled="!canCancelTask(task) || Boolean(taskActionLoading[task.id])" @click="cancelTask(task)">
                  取消任务
                </button>
                <button type="button" :disabled="!canRetryTask(task) || Boolean(taskActionLoading[task.id])" @click="retryTask(task)">
                  重试任务
                </button>
                <button type="button" :disabled="Boolean(taskActionLoading[task.id])" @click="loadTaskEvents(task)">
                  刷新事件
                </button>
              </div>
              <div v-if="taskEventsForTask(task).length" class="task-event-list">
                <span v-for="event in taskEventsForTask(task).slice(-3)" :key="event.id">
                  {{ formatTaskStatus(event.status || event.event_type) }} · {{ event.message || event.event_type }}
                </span>
              </div>
            </div>
          </div>

          <div v-else-if="executionDetailTab === 'artifacts'" class="run-detail-body">
            <div class="artifact-toolbar">
              <button class="button button--subtle" type="button" :disabled="artifactCleanupLoading" @click="cleanupCachedArtifacts">
                清理缓存数据
              </button>
              <small>当前运行产出的结果；可编辑名称、加标签、改保留方式。</small>
            </div>
            <div v-if="!runArtifacts.length" class="state-text">本次运行还没有结果。</div>
            <article
              v-for="artifact in runArtifacts"
              :key="artifact.id"
              class="derived-row"
            >
              <header class="derived-row__head">
                <button
                  class="derived-row__title"
                  type="button"
                  :title="artifact.id"
                  @click="openArtifactPreview(artifact)"
                >
                  <strong v-if="editingDisplayId !== artifact.id" @click.stop="startEditDisplayName(artifact)">
                    {{ artifact.display_name || artifactLabel(artifact) }}
                  </strong>
                  <input
                    v-else
                    ref="displayNameInput"
                    type="text"
                    class="derived-row__rename"
                    :value="displayNameDraft"
                    @click.stop
                    @input="displayNameDraft = ($event.target as HTMLInputElement).value"
                    @keydown.enter="commitDisplayName(artifact)"
                    @keydown.esc="cancelEditDisplayName"
                    @blur="commitDisplayName(artifact)"
                  />
                </button>
                <span class="derived-row__type">{{ artifact.data_type }}</span>
                <span class="status-pill" :class="derivedRetentionPillClass(artifact)">
                  {{ formatArtifactRetention(artifact) }}
                </span>
              </header>

              <div class="derived-row__tags">
                <span v-for="tag in artifact.tags || []" :key="tag" class="chip chip--active">
                  {{ tag }}
                  <button
                    type="button"
                    class="chip__remove"
                    aria-label="移除标签"
                    :disabled="!!artifactActionLoading[artifact.id]"
                    @click="removeDerivedTag(artifact, tag)"
                  >
                    ×
                  </button>
                </span>
                <input
                  type="text"
                  class="derived-row__tag-input"
                  placeholder="+ 标签"
                  :value="tagDraftFor(artifact.id)"
                  @input="setTagDraft(artifact.id, ($event.target as HTMLInputElement).value)"
                  @keydown.enter="commitTagDraft(artifact)"
                />
              </div>

              <small class="derived-row__meta">
                {{ formatFileSize(artifact.file_size) }}
                <template v-if="artifact.bids_subject_id"> · {{ artifact.bids_subject_id }}</template>
                <template v-if="artifact.task"> · task-{{ artifact.task }}</template>
                <template v-if="artifact.condition"> · {{ artifact.condition }}</template>
              </small>

              <div class="artifact-actions">
                <button type="button" :disabled="isArtifactActionLoading(artifact, 'pin')" @click="setArtifactRetentionAction(artifact, 'pin')">
                  保留
                </button>
                <button type="button" :disabled="isArtifactActionLoading(artifact, 'unpin')" @click="setArtifactRetentionAction(artifact, 'unpin')">
                  设为不保留
                </button>
                <button type="button" :disabled="isArtifactActionLoading(artifact, 'hide')" @click="setArtifactRetentionAction(artifact, 'hide')">
                  删除
                </button>
                <button type="button" :disabled="isArtifactActionLoading(artifact, 'download')" @click="downloadArtifact(artifact)">
                  下载
                </button>
              </div>
            </article>
          </div>

          <div v-else-if="executionDetailTab === 'manifest'" class="run-detail-body">
            <div v-if="executionManifestLoading" class="state-text">正在读取清单...</div>
            <div v-else-if="executionManifestError" class="state-text state-text--error">{{ executionManifestError }}</div>
            <div v-else class="run-kv">
              <span>输入</span><strong>{{ manifestArrayCount('inputs') }}</strong>
              <span>输出</span><strong>{{ manifestOutputCount }}</strong>
              <span>任务</span><strong>{{ manifestArrayCount('tasks') }}</strong>
              <span>警告</span><strong>{{ manifestArrayCount('warnings') }}</strong>
            </div>
          </div>

          <div v-else-if="executionDetailTab === 'lineage'" class="run-detail-body">
            <div v-if="executionLineageLoading" class="state-text">正在读取血缘关系...</div>
            <div v-else-if="executionLineageError" class="state-text state-text--error">{{ executionLineageError }}</div>
            <template v-else>
              <div class="run-kv">
                <span>上游运行</span><strong>{{ activeExecutionLineage?.upstream_executions.length || 0 }}</strong>
                <span>下游运行</span><strong>{{ activeExecutionLineage?.downstream_executions.length || 0 }}</strong>
                <span>图节点</span><strong>{{ activeExecutionLineage?.graph_nodes.length || 0 }}</strong>
                <span>图边</span><strong>{{ activeExecutionLineage?.graph_edges.length || 0 }}</strong>
              </div>
              <div class="state-text">lineage 接口用于依赖图、清理阻断提示和结果溯源面板。</div>
            </template>
          </div>
        </section>
      </aside>

      <aside
        class="inspector"
        :class="{ 'is-hidden': !inspectorVisible }"
        :style="{ width: inspectorWidth + 'px' }"
        @click.stop
      >
        <!-- 手柄在 inspector 内部，随 inspector 左边缘自动移动，无需外部 right 绑定 -->
        <div
          class="drawer-handle drawer-handle--seam-right"
          :class="{ 'is-dragging': drawerDragging === 'inspector' }"
          title="拖动调整右侧检查器宽度"
          @mousedown="startDrawerDrag('inspector', $event)"
        ></div>
        <div class="inspector-inner">
        <div v-if="!selectedNode || !selectedNodeSpec" class="inspector-empty">
          <div class="inspector-empty-icon" aria-hidden="true">
            <IconLine name="clipboard" :size="36" :stroke-width="1.4" />
          </div>
          <div class="inspector-empty-title">未选择节点</div>
          <div class="inspector-empty-hint">点击画布上的节点即可查看与编辑参数</div>
          <div class="inspector-empty-kbd">
            <span class="kbd">Esc</span> 收起 ·
            <span class="kbd kbd--icon"><IconLine name="pin" :size="11" /></span> 钉住保持显示
          </div>
        </div>
        <section v-else class="panel panel--fill">
          <!-- 节点名输入升级为参数面板主标题；spec.title + description 作为副标题 -->
          <div class="panel__title panel__title--node">
            <input
              class="panel__title-input"
              type="text"
              :value="selectedNode.title || selectedNodeSpec.title"
              :placeholder="selectedNodeSpec.title"
              :title="`节点 ID: ${selectedNode.id}（影响 display_name 模板的 {node_title} 占位符）`"
              @input="handleNodeTitleInput"
            />
            <div class="inspector-header-actions">
              <button
                class="inspector-header-btn"
                :class="{ 'is-active': inspectorPinned }"
                type="button"
                title="钉住面板（不自动收起）"
                @click="toggleInspectorPin"
              ><IconLine name="pin" :size="14" /></button>
              <button
                class="inspector-header-btn"
                type="button"
                title="关闭面板 (Esc)"
                @click="forceCloseInspector"
              ><IconLine name="x" :size="14" /></button>
            </div>
          </div>
          <div class="node-detail node-detail--subtitle">
            <small>
              <strong>{{ selectedNodeSpec.title }}</strong>
              <template v-if="selectedNodeSpec.description"> · {{ selectedNodeSpec.description }}</template>
            </small>
          </div>

          <div v-if="selectedJob" class="node-run-summary">
            <div class="node-run-summary__head">
              <strong>最近运行</strong>
              <span class="status-pill" :class="jobStatusClass(selectedJob.status)">
                {{ formatJobStatus(selectedJob.status) }}
              </span>
            </div>
            <div class="node-run-summary__grid">
              <span>耗时</span>
              <strong>{{ formatDurationMs(selectedJob.duration_ms) }}</strong>
              <span>产物</span>
              <strong>{{ selectedNodeArtifactCount }}</strong>
            </div>
            <div v-if="selectedJobError" class="state-text state-text--error">{{ selectedJobError }}</div>
            <div v-if="cacheHitDebug" class="node-run-summary__debug">{{ cacheHitDebug }}</div>
          </div>

          <div v-if="selectedNodeArtifacts.length" class="artifact-list">
            <button
              v-if="selectedNodeArtifacts.length > 1"
              class="artifact-summary"
              type="button"
              :aria-expanded="artifactListExpanded"
              @click="artifactListExpanded = !artifactListExpanded"
            >
              <span>{{ artifactSummaryText }}</span>
              <small>{{ artifactListExpanded ? '收起 ▴' : '展开全部 ▾' }}</small>
            </button>
            <template v-if="selectedNodeArtifacts.length === 1 || artifactListExpanded">
              <button
                v-for="artifact in selectedNodeArtifacts"
                :key="artifact.id"
                class="artifact-row"
                :class="{ 'is-active': selectedArtifactPreview?.study_output_id === artifact.id }"
                type="button"
                @click="openArtifactPreview(artifact)"
              >
                <span>{{ artifactFriendlyLabel(artifact) }}</span>
                <small>{{ formatDataType(artifact.data_type) }}</small>
              </button>
            </template>
          </div>

          <div v-if="artifactPreviewOpen" class="artifact-preview-panel">
            <div class="artifact-preview-panel__head">
              <strong>{{ artifactPreviewTitle }}</strong>
              <button class="icon-button" type="button" @click="resetArtifactPreview">×</button>
            </div>
            <div v-if="artifactPreviewLoading" class="state-text">正在读取产物预览...</div>
            <div v-else-if="artifactPreviewError" class="state-text state-text--error">{{ artifactPreviewError }}</div>
            <template v-else-if="selectedArtifactPreview">
              <div v-if="artifactPreviewMetrics.length" class="artifact-preview-metrics">
                <div v-for="metric in artifactPreviewMetrics" :key="metric.label">
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.value }}</strong>
                </div>
              </div>
              <div v-if="artifactPreviewEvents.length" class="artifact-preview-events">
                <span v-for="event in artifactPreviewEvents" :key="event.name">{{ event.name }} × {{ event.count }}</span>
              </div>
              <div v-if="artifactPreviewCurves.length" class="artifact-preview-curves">
                <span v-for="curve in artifactPreviewCurves" :key="curve">{{ curve }}</span>
              </div>
              <RouterLink class="artifact-preview-panel__link" :to="artifactPreviewObserveTarget">
                打开观察页
              </RouterLink>
            </template>
          </div>

          <div v-if="showIcaInteractionPanel" class="ica-interaction-panel">
            <div class="ica-interaction-panel__head">
              <strong>ICA 成分确认</strong>
              <small>Decision v{{ icaInteraction?.decision_version || 1 }}</small>
            </div>
            <div v-if="icaInteractionLoading" class="state-text">正在读取 ICA 成分...</div>
            <div v-else-if="icaInteractionError" class="state-text state-text--error">{{ icaInteractionError }}</div>
            <template v-else>
              <label
                v-for="component in icaInteractionComponents"
                :key="component.index"
                class="ica-component-row"
              >
                <input
                  type="checkbox"
                  :checked="icaExcludedComponents.includes(component.index)"
                  @change="toggleIcaComponent(component.index, $event)"
                />
                <span>{{ icaComponentLabel(component) }}</span>
                <small>{{ icaComponentMetric(component) }}</small>
              </label>
              <div v-if="!icaInteractionComponents.length" class="state-text">暂无可展示的 ICA 成分。</div>
              <div class="ica-interaction-panel__actions">
                <a
                  v-if="icaReviewerHref"
                  class="button"
                  :href="icaReviewerHref"
                  target="_blank"
                  rel="noopener"
                  title="在 ICA 审阅台查看地形图 / 时序 / 频谱并提交剔除"
                >
                  审阅台打开 ↗
                </a>
                <button
                  class="button"
                  type="button"
                  :disabled="icaDecisionSubmitting || !icaInteraction"
                  @click="submitIcaDecision"
                >
                  确认选择
                </button>
                <button
                  class="button button--primary"
                  type="button"
                  :disabled="icaResuming || !icaInteraction?.decision"
                  @click="resumeIcaNode"
                >
                  继续运行
                </button>
              </div>
            </template>
          </div>

          <!-- LoadData 数据选择面板 v2: 抽离为独立组件 (LoadDataPanel.vue) -->
          <LoadDataPanel
            v-if="isLoadDataNode && selectedNode"
            :study-datasets="studyDatasets"
            :model-value="ensureLoadDataParams(selectedNode)"
            :loading="loadingDatasets"
            :error="datasetLoadError"
            @update:model-value="onLoadDataParamsUpdate"
          />

          <div v-else-if="selectedNodeSpec.properties.length" class="property-list">
            <template v-for="prop in visibleBasicProperties" :key="prop.name">
              <!-- event_select 类型：根据上游 LoadData 的事件标签做多选 chip -->
              <div v-if="prop.type === 'event_select'" class="field event-select" :data-param="prop.name">
                <div class="event-select__head">
                  <span>
                    {{ prop.label }}
                    <small v-if="prop.unit">({{ prop.unit }})</small>
                  </span>
                  <span class="event-select__meta">
                    <small v-if="eventLabelsLoading">读取事件中…</small>
                    <small v-else-if="!availableEventLabels.length">上游加载节点暂无可用事件</small>
                    <small v-else>共 {{ availableEventLabels.length }} 种事件</small>
                    <button
                      v-if="getEventIdArray(prop).length"
                      type="button"
                      class="link-button"
                      @click="clearEventIds(prop)"
                    >
                      清空
                    </button>
                  </span>
                </div>

                <div
                  v-if="getEventIdArray(prop).length"
                  class="chip-row chip-row--selected"
                >
                  <button
                    v-for="label in getEventIdArray(prop)"
                    :key="'esel-' + label"
                    type="button"
                    class="chip chip--active"
                    title="点击移除"
                    @click="toggleEventId(prop, label)"
                  >
                    {{ label }}
                    <span class="chip__remove" aria-hidden="true">×</span>
                  </button>
                </div>

                <div v-if="availableEventLabels.length" class="chip-row chip-row--pool">
                  <button
                    v-for="entry in availableEventLabels"
                    :key="'eopt-' + entry.label"
                    type="button"
                    class="chip"
                    :class="{ 'chip--active': isEventIdSelected(prop, entry.label) }"
                    :title="`${entry.count} 次出现 · ${entry.datasets} 个数据集`"
                    @click="toggleEventId(prop, entry.label)"
                  >
                    {{ entry.label }}
                    <span class="chip__count">{{ entry.count }}</span>
                  </button>
                </div>
                <small v-if="prop.description || prop.help" class="help-text">{{ prop.description || prop.help }}</small>
              </div>

              <!-- channel_list：从上游 LoadData 推断通道，listbox 多选（单选=单通道参考 / 多选=平均参考 / 全选=共同平均参考）
                   交互：单击 toggle / Shift+点击范围加入 / Ctrl+A 全选可见 / Delete 移除已选 -->
              <div v-else-if="prop.type === 'channel_list'" class="field channel-list-field" :data-param="prop.name">
                <div class="channel-list__head">
                  <span>
                    {{ prop.label }}
                    <small v-if="prop.unit">({{ prop.unit }})</small>
                  </span>
                  <small class="channel-list__count">
                    <template v-if="!upstreamChannels.length">上游加载节点暂无通道信息</template>
                    <template v-else>已选 {{ getChannelListArray(prop).length }} / {{ upstreamChannels.length }}</template>
                  </small>
                </div>
                <div v-if="upstreamChannels.length" class="channel-list__toolbar">
                  <input
                    type="text"
                    class="control channel-list__search"
                    :value="channelFilterFor(prop)"
                    placeholder="过滤通道…"
                    @input="setChannelFilter(prop, ($event.target as HTMLInputElement).value)"
                  />
                  <button type="button" class="chip" @click="selectAllChannels(prop)">全选</button>
                  <button type="button" class="chip" @click="clearChannels(prop)">清空</button>
                  <button type="button" class="chip" @click="invertChannels(prop)">反选</button>
                </div>
                <div
                  v-show="upstreamChannels.length"
                  class="channel-list__box"
                  tabindex="0"
                  @keydown="handleChannelListKeydown($event, prop)"
                >
                  <div
                    v-for="(ch, idx) in filteredChannelOptions(prop)"
                    :key="'chl-' + ch"
                    class="channel-list__item"
                    :class="{ 'is-selected': isChannelSelected(prop, ch) }"
                    @click="handleChannelListClick($event, prop, idx, ch)"
                  >
                    {{ ch }}
                  </div>
                  <div v-if="filteredChannelOptions(prop).length === 0" class="channel-list__empty">
                    无匹配通道
                  </div>
                </div>
                <div
                  v-if="upstreamChannels.length && getChannelListArray(prop).length === upstreamChannels.length"
                  class="channel-list__hint"
                >
                  已全选 → 共同平均参考 (common average reference)
                </div>
                <small v-if="upstreamChannels.length" class="channel-list__shortcut-hint">
                  单击切换 · Shift+单击范围选 · Ctrl+A 全选 · Delete 移除已选
                </small>
                <small v-if="prop.description || prop.help" class="help-text">{{ prop.description || prop.help }}</small>
              </div>

              <!-- tags_input：用户自由打标签的 chip 输入 -->
              <div v-else-if="prop.type === 'tags_input'" class="field tags-input-field" :data-param="prop.name">
                <span>
                  {{ prop.label }}
                  <small v-if="prop.unit">({{ prop.unit }})</small>
                </span>
                <div class="chip-row chip-row--selected" v-if="getTagsArray(prop).length">
                  <button
                    v-for="tag in getTagsArray(prop)"
                    :key="'tag-' + tag"
                    type="button"
                    class="chip chip--active"
                    title="点击移除"
                    @click="toggleParamTag(prop, tag)"
                  >
                    {{ tag }}
                    <span class="chip__remove" aria-hidden="true">×</span>
                  </button>
                </div>
                <input
                  type="text"
                  class="control"
                  :value="paramTagDraftFor(prop)"
                  placeholder="输入后回车添加 (支持逗号一次多条)"
                  @input="setParamTagDraft(prop, ($event.target as HTMLInputElement).value)"
                  @keydown.enter.prevent="commitParamTagDraft(prop)"
                />
                <small v-if="prop.description || prop.help" class="help-text">{{ prop.description || prop.help }}</small>
              </div>

              <!-- montage_picker：从「本研究项数据集已上传的电极文件」里选一个（custom montage）。
                   上传入口在数据集详情页 → 数据文件 → 电极位置文件；这里只负责选。 -->
              <div v-else-if="prop.type === 'montage_picker'" class="field montage-picker-field" :data-param="prop.name">
                <span>
                  {{ prop.label }}
                  <small v-if="prop.unit">({{ prop.unit }})</small>
                </span>
                <div class="montage-picker__row">
                  <select
                    class="control"
                    :value="String(selectedNode.params[prop.name] ?? '')"
                    @change="handleParamInput(prop, $event)"
                  >
                    <option value="">— 选择电极文件 —</option>
                    <option v-for="m in studyMontages" :key="m.id" :value="m.id">
                      {{ m.name }}（{{ m.n_electrodes ?? '?' }} 电极 · .{{ m.file_format }}）
                    </option>
                  </select>
                  <button type="button" class="chip" title="刷新列表" @click="loadStudyMontages">↻</button>
                </div>
                <small v-if="!studyMontages.length" class="help-text">
                  本研究项的数据集里还没有电极文件。去「数据集详情页 → 数据文件 → 电极位置文件」上传后点 ↻ 刷新。
                </small>
                <small v-else-if="prop.description || prop.help" class="help-text">{{ prop.description || prop.help }}</small>
              </div>

              <label v-else class="field" :class="{ 'field--half': prop.type === 'number' || prop.type === 'integer' }" :data-param="prop.name">
                <span>
                  {{ prop.label }}
                  <small v-if="prop.unit">({{ prop.unit }})</small>
                </span>
                <input
                  v-if="prop.type === 'boolean'"
                  class="checkbox"
                  type="checkbox"
                  :checked="Boolean(selectedNode.params[prop.name])"
                  @change="handleParamCheckbox(prop, $event)"
                />
                <select
                  v-else-if="prop.type === 'select'"
                  class="control"
                  :value="String(selectedNode.params[prop.name] ?? prop.default ?? '')"
                  @change="handleParamInput(prop, $event)"
                >
                  <option v-for="option in prop.options || []" :key="String(option.value)" :value="String(option.value)">
                    {{ option.label }}
                  </option>
                </select>
                <input
                  v-else
                  class="control"
                  :type="prop.type === 'number' || prop.type === 'integer' ? 'number' : 'text'"
                  :min="prop.min"
                  :max="prop.max"
                  :step="prop.type === 'integer' ? (prop.step ?? 1) : (prop.step ?? 'any')"
                  :value="formatParamValue(prop)"
                  @change="handleParamInput(prop, $event)"
                />
                <small v-if="prop.description || prop.help" class="help-text">{{ prop.description || prop.help }}</small>
              </label>
            </template>

            <!-- 高级设置：advanced=true 的工程参数折叠在这里（method / phase / order 等） -->
            <details v-if="visibleAdvancedProperties.length" class="advanced-params">
              <summary class="advanced-params__summary">高级设置（{{ visibleAdvancedProperties.length }}）</summary>
              <label v-for="prop in visibleAdvancedProperties" :key="'adv-' + prop.name" class="field">
                <span>
                  {{ prop.label }}
                  <small v-if="prop.unit">({{ prop.unit }})</small>
                </span>
                <input
                  v-if="prop.type === 'boolean'"
                  class="checkbox"
                  type="checkbox"
                  :checked="Boolean(selectedNode.params[prop.name])"
                  @change="handleParamCheckbox(prop, $event)"
                />
                <select
                  v-else-if="prop.type === 'select'"
                  class="control"
                  :value="String(selectedNode.params[prop.name] ?? prop.default ?? '')"
                  @change="handleParamInput(prop, $event)"
                >
                  <option v-for="option in prop.options || []" :key="String(option.value)" :value="String(option.value)">
                    {{ option.label }}
                  </option>
                </select>
                <input
                  v-else
                  class="control"
                  :type="prop.type === 'number' || prop.type === 'integer' ? 'number' : 'text'"
                  :min="prop.min"
                  :max="prop.max"
                  :step="prop.type === 'integer' ? (prop.step ?? 1) : (prop.step ?? 'any')"
                  :value="formatParamValue(prop)"
                  @change="handleParamInput(prop, $event)"
                />
                <small v-if="prop.description || prop.help" class="help-text">{{ prop.description || prop.help }}</small>
              </label>
            </details>
          </div>
          <div v-else class="state-text">该节点暂无可配置参数。</div>

          <!-- 保存设置折叠区：当节点 spec 有 save 子对象时显示（P0 起所有处理节点都有，LoadData/Save 节点没有） -->
          <details v-if="saveSpec" class="save-settings" :open="saveSettingsOpen" @toggle="onSaveSettingsToggle">
            <summary class="save-settings__head">
              <IconLine class="save-settings__icon" name="save" :size="14" />
              <span class="save-settings__title">保存设置</span>
              <label class="save-settings__keep" @click.stop>
                <input
                  type="checkbox"
                  :checked="selectedNodeKeep"
                  :disabled="keepCheckboxDisabled"
                  @change="onToggleKeep"
                />
                <span>保存</span>
              </label>
              <span v-if="isLeafNode" class="save-settings__hint" :title="keepLeafHint">· 必存</span>
            </summary>

            <div class="save-settings__body">
              <!-- 显示名模板 -->
              <label class="field">
                <span>
                  显示名模板
                  <small class="help-text help-text--inline">支持 {{ '{subject} {task} {condition} {node_title}' }} 等占位符</small>
                </span>
                <input
                  class="control"
                  type="text"
                  :value="getSaveSetting('display_name_template')"
                  :placeholder="effectiveNameTemplate"
                  @input="onSaveSettingInput('display_name_template', $event)"
                />
                <small class="help-text">
                  预览：<code class="save-settings__preview">{{ previewDisplayName }}</code>
                </small>
              </label>

              <!-- 标签 -->
              <div class="field save-settings__tags">
                <span>
                  标签
                  <small class="help-text help-text--inline">自动标签由节点 spec 提供 · 自定义标签下面输入</small>
                </span>

                <!-- 自动标签（不可编辑） -->
                <div v-if="autoTagsPreview.length" class="chip-row chip-row--readonly">
                  <span
                    v-for="tag in autoTagsPreview"
                    :key="'auto-' + tag"
                    class="chip chip--readonly"
                    :title="'自动标签（来自节点 spec）'"
                  >{{ tag }}</span>
                </div>

                <!-- 用户标签 -->
                <div v-if="userTagsArray.length" class="chip-row chip-row--selected">
                  <button
                    v-for="tag in userTagsArray"
                    :key="'user-' + tag"
                    type="button"
                    class="chip chip--active"
                    title="点击移除"
                    @click="removeUserTag(tag)"
                  >
                    {{ tag }}
                    <span class="chip__remove" aria-hidden="true">×</span>
                  </button>
                </div>

                <input
                  type="text"
                  class="control"
                  :value="userTagDraft"
                  placeholder="自定义标签，回车添加（支持逗号一次多条）"
                  @input="userTagDraft = ($event.target as HTMLInputElement).value"
                  @keydown.enter.prevent="commitUserTagDraft"
                />
              </div>

              <!-- 内部保存元信息（step_label / data_type / split 等）已对临床用户隐藏；排错看 spec JSON 或 API -->
            </div>
          </details>
        </section>
        </div><!-- /inspector-inner -->
      </aside>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { LGraph, LGraphCanvas, LGraphNode, LiteGraph } from 'litegraph.js'
import 'litegraph.js/css/litegraph.css'
import AppIcon from '@/components/AppIcon.vue'
import LoadDataPanel from '@/components/LoadDataPanel.vue'
import IconLine from '@/components/IconLine.vue'
import { pipelineApi } from '@/api/pipelines'
import { datasetAssetApi } from '@/api/datasetAssets'
import type { DatasetMontage } from '@/types'
import type {
  LoadDataDataInfo,
  NodeSpec,
  Pipeline,
  PipelineDefinitionPayload,
  PipelineGraphLink,
  PipelineGraphNode,
  PipelineJob,
  PipelineValidationResponse,
  StudyOutput,
} from '@/types'
import {
  LOAD_DATA_NODE_TYPE,
  EPOCH_NODE_TYPE,
  ERP_NODE_TYPE,
  ICA_APPLY_NODE_TYPE,
  LITEGRAPH_NODE_ID_PROP,
  LITEGRAPH_HIDPI_EVENT_PROP,
  LITEGRAPH_ORIGINAL_CLIENT_X_PROP,
  LITEGRAPH_ORIGINAL_CLIENT_Y_PROP,
  LITEGRAPH_ENGINE_INFO,
  LINK_DEFAULT_COLOR,
  LINK_HIGHLIGHT_COLOR,
  LINK_CONNECTING_COLOR,
  LINK_HIGHLIGHT_WIDTH_MULT,
  EXECUTION_MODE_OPTIONS,
  NODE_CARD_WIDTH,
  NODE_CARD_MIN_HEIGHT,
  NODE_GAP_X,
  NODE_GAP_Y,
  LITEGRAPH_MIN_ZOOM,
  LITEGRAPH_MAX_ZOOM,
  LITEGRAPH_MAX_PIXEL_RATIO,
  LINK_HIGHLIGHT_PATCH_MARK,
} from '@/composables/pipeline/pipelineConstants'
import {
  pipelinePortColors,
  withAlpha,
  nodeStatusColor,
  nodeStatusSoftColor,
  normalizedJobStatus,
  formatJobStatus,
  jobStatusClass,
  formatDataType,
  stepVisualState,
  stepIcon,
  isStepDone,
  formatFileSize,
  shortId,
  formatDurationMs,
  formatPipelineExecutionStatus,
  formatTaskStatus,
  formatPipelineStatus,
  formatExecutionMode,
  formatArtifactRetention,
  categoryColor,
} from '@/composables/pipeline/pipelineFormatters'
import { useEditorLayout } from '@/composables/pipeline/useEditorLayout'
import { useNodeLibrary } from '@/composables/pipeline/useNodeLibrary'
import { usePipelineEditor } from '@/composables/pipeline/usePipelineEditor'
import { useDraftPersistence } from '@/composables/pipeline/useDraftPersistence'
import { useExecutionTasks } from '@/composables/pipeline/useExecutionTasks'
import { usePipelineEditLock } from '@/composables/pipeline/usePipelineEditLock'
import { useExecutionDetail, type ExecutionDetailTab } from '@/composables/pipeline/useExecutionDetail'
import { useRunExecution } from '@/composables/pipeline/useRunExecution'
import { useRunControl } from '@/composables/pipeline/useRunControl'
import { useIcaInteraction } from '@/composables/pipeline/useIcaInteraction'
import { useArtifactPreview } from '@/composables/pipeline/useArtifactPreview'
import { useArtifactActions } from '@/composables/pipeline/useArtifactActions'
import { useLoadData } from '@/composables/pipeline/useLoadData'
import { useChannelListEditor } from '@/composables/pipeline/useChannelListEditor'
import { useSaveSettingsPanel } from '@/composables/pipeline/useSaveSettingsPanel'
import { useEventSelectEditor } from '@/composables/pipeline/useEventSelectEditor'
import { useTagsInputEditor } from '@/composables/pipeline/useTagsInputEditor'
import { useNodeTopology } from '@/composables/pipeline/useNodeTopology'
import { useNodeParamEditor } from '@/composables/pipeline/useNodeParamEditor'
import { useGraphConnections } from '@/composables/pipeline/useGraphConnections'
import {
  getLiteGraphNodeId,
  setLiteGraphNodeId,
  liteGraphNodes,
  liteGraphReachableFromLoadData,
  drawNodeAccentBar,
  drawNodeStatusBadge,
  drawNodeSaveIcon,
  graphNodeSize,
  computeFlowLayout,
  type LiteGraphNode,
  type LooseLiteGraph,
  type LiteGraphLink,
} from '@/composables/pipeline/litegraphUtils'
import { planNodeWidgets, type NodeWidgetPlan } from '@/composables/pipeline/nodeWidgetPlan'
import { useLiteGraphNodeTypes } from '@/composables/pipeline/useLiteGraphNodeTypes'

// 节点强调色（只读「点击设置」提示用同一种主色，不分类别色）
const NODE_WIDGET_SLIDER_COLOR = '#3B6FB0'
// 只读事实行字体：测量数字 = 全卡唯一的粗体(600/12)；档位词同字号低一档(500/12，秀气不墩)；单位/运算符 500/11 弱化
const FACT_NUM_FONT = '600 12px "Segoe UI", Arial, sans-serif'
const FACT_CAT_FONT = '500 12px "Segoe UI", Arial, sans-serif'
const FACT_UNIT_FONT = '500 11px "Segoe UI", Arial, sans-serif'
type FactRun = { text: string; font: string; fill: string; w: number }
// 「参数面板」(D 方案)几何：标题→端口区→淡色面板(框住所有事实行)→底部保存条留白。面板内行自绘，无 litegraph 逐行 widget。
const PANEL_INSET_X = 8 // 面板距卡左右各 8px
const PANEL_GAP_TOP = 10 // 端口区到面板顶的留白
const PANEL_SAVE_RESERVE = 14 // 面板底到卡底的留白(含 4px 保存条)
const PANEL_PAD_V = 8 // 面板内上下内边距
const PANEL_PAD_L = 11 // 面板内左内边距(标签)
const PANEL_PAD_R = 11 // 面板内右内边距(值右缘)
const PANEL_R = 6 // 面板圆角(与卡片一致)
const PANEL_ROW_H = 18 // 面板内每行行距(自绘,无 litegraph +4)
type ElysFact =
  | { kind: 'fact'; label: string; value: string }
  | { kind: 'line'; text: string; tone: 'default' | 'muted' | 'accent' }

type LooseLiteGraphCanvas = LGraphCanvas & Record<string, any>
type LooseLiteGraphTheme = typeof LiteGraph & Record<string, any>

type LiteGraphContextEvent = MouseEvent & {
  canvasX?: number
  canvasY?: number
}

type PipelineContextMenuItem = {
  key: string
  label: string
  danger?: boolean
  disabled?: boolean
}


defineOptions({ name: 'PipelinePage' })

const route = useRoute()

// 承重墙：图定义 / 选中节点 / 节点规格（状态与基础查询见 composables/pipeline/usePipelineEditor）
const {
  nodeSpecs,
  definition,
  selectedNodeId,
  selectedNode,
  selectedNodeSpec,
  createEmptyDefinition,
  specForNode,
  dirty,
  statusMessage,
  hydrating,
} = usePipelineEditor()
const pipelines = ref<Pipeline[]>([])
const selectedStudyId = computed(() => String(route.params.studyId || ''))
// 自定义电极文件列表（供「通道定位」节点 montage_picker 选择器）：本研究项挂载的数据集里上传的都在这
const studyMontages = ref<DatasetMontage[]>([])
async function loadStudyMontages() {
  const sid = selectedStudyId.value
  if (!sid) {
    studyMontages.value = []
    return
  }
  try {
    const res = await datasetAssetApi.listStudyMontages(sid)
    studyMontages.value = res.data.montages
  } catch {
    studyMontages.value = []
  }
}
const selectedPipelineId = ref('')
const currentPipeline = ref<Pipeline | null>(null)
const pipelineName = ref('未命名工作流')
const pipelineDescription = ref('')
// 节点库（搜索 / 分组 / 折叠）状态与逻辑见 composables/pipeline/useNodeLibrary
const {
  nodeSearch,
  groupOpen,
  filteredNodeSpecs,
  groupedNodeSpecs,
  toggleGroup,
} = useNodeLibrary(nodeSpecs)

// Pipeline 草稿 localStorage 暂存（每次 markDirty 后 debounce 写入；切回页面静默恢复）
// 状态与逻辑见 composables/pipeline/useDraftPersistence

// ========== 阶段 1: 抽屉式布局（状态与逻辑见 composables/pipeline/useEditorLayout）==========
const {
  libraryVisible,
  libraryWidth,
  inspectorVisible,
  inspectorWidth,
  inspectorPinned,
  drawerDragging,
  restoreLayoutState,
  toggleLibrary,
  toggleInspector,
  showInspector,
  forceCloseInspector,
  toggleInspectorPin,
  startDrawerDrag,
  onDrawerDragMove,
  onDrawerDragEnd,
  handleLayoutKeydown,
} = useEditorLayout()
const validation = ref<PipelineValidationResponse | null>(null)
const loadingNodes = ref(false)
const loadingPipelines = ref(false)
const saving = ref(false)
const runningPipeline = ref(false)
const nodeLoadError = ref('')
// 运行态核心（执行加载 / 轮询 / 刷新 / 重置 + 派生 computed）见 composables/pipeline/useRunExecution
// 注：onResetTracking / onRunStateRefreshed 闭包引用下方执行详情 / 任务解构，仅在运行时（非 setup 同步）触发，故无 TDZ。
const {
  latestPipelineExecution,
  activeExecutionId,
  activeExecutionDetail,
  executionJobs,
  runArtifacts,
  runPolling,
  runPollingError,
  latestPipelineExecutionIssues,
  executionJobByNodeId,
  runArtifactsByJobId,
  executionPanelJobRows,
  selectedJob,
  selectedNodeArtifacts,
  selectedNodeArtifactCount,
  selectedJobError,
  loadPipelineExecutions,
  loadPipelineExecutionById,
  refreshRunState,
  startRunPolling,
  stopRunPolling,
  resetRunTracking,
  isTerminalRunStatus,
} = useRunExecution({
  selectedStudyId,
  currentPipeline,
  selectedNode,
  statusMessage,
  describeError,
  applyRunStateToCanvas: applyLiteGraphRunState,
  artifactCountForJob,
  jobErrorMessage,
  onResetTracking: () => {
    activeExecutionManifest.value = null
    activeExecutionLineage.value = null
    executionManifestError.value = ''
    executionLineageError.value = ''
    executionDetailTab.value = 'summary'
    Object.keys(taskEventsByTaskId).forEach((taskId) => delete taskEventsByTaskId[taskId])
    resetArtifactPreview()
    resetIcaInteractionState()
  },
  onRunStateRefreshed: (executionId: string) => {
    if (executionDetailTab.value === 'manifest') void loadExecutionManifest(executionId)
    if (executionDetailTab.value === 'lineage') void loadExecutionLineage(executionId)
  },
})
// LoadData 数据源（数据集加载 / 解析预览 / 参数规范化 / 运行覆盖）见 composables/pipeline/useLoadData。
// 手选右栏 UI 在 LoadDataPanel.vue（独立组件），这里只把解构喂给 <LoadDataPanel>，template 零改。
// markDirty / updateLiteGraphNode 为下方 hoisted 函数，仅在交互回调触发，无 TDZ。
const {
  studyDatasets,
  loadingDatasets,
  datasetLoadError,
  loadDataResolveError,
  loadDataResolving,
  resolvedLoadDataInfos,
  loadDataResolveIssues,
  loadDataInfosByNodeId,
  eventLabelsLoading,
  loadDataExecutionOverrides,
  isLoadDataNode,
  ensureLoadDataParams,
  loadDatasets,
  resolveLoadDataPreview,
  fetchEventLabelsForAllLoadData,
  clearAllLoadDataExecutionOverrides,
  buildRunSelectionOverridePayload,
  onLoadDataParamsUpdate,
} = useLoadData({
  definition,
  selectedNode,
  selectedStudyId,
  describeError,
  markDirty,
  updateLiteGraphNode,
})
// 异步任务事件流（取消 / 重试 / 拉取事件）见 composables/pipeline/useExecutionTasks（解构见下方装配区）
// 编辑锁（获取 / 续期 / 释放）见 composables/pipeline/usePipelineEditLock
const {
  pipelineEditLock,
  pipelineEditLockLoading,
  pipelineEditLockError,
  pipelineEditLockSummary,
  canUsePipelineEditLockActions,
  acquirePipelineEditLock,
  refreshPipelineEditLock,
  releasePipelineEditLock,
} = usePipelineEditLock({
  selectedStudyId,
  currentPipeline,
  statusMessage,
  describeError,
})
// 执行详情（Manifest / Lineage / tab 懒加载）见 composables/pipeline/useExecutionDetail
const {
  activeExecutionManifest,
  activeExecutionLineage,
  executionDetailTab,
  executionManifestLoading,
  executionManifestError,
  executionLineageLoading,
  executionLineageError,
  selectExecutionDetailTab,
  loadExecutionManifest,
  loadExecutionLineage,
} = useExecutionDetail({
  activeExecutionId,
  selectedStudyId,
  describeError,
})
// 产物预览（结果弹窗：指标 / 事件 / 曲线）见 composables/pipeline/useArtifactPreview
const {
  selectedArtifactPreview,
  artifactPreviewOpen,
  artifactPreviewLoading,
  artifactPreviewError,
  artifactPreviewSummary,
  artifactPreviewMetrics,
  artifactPreviewEvents,
  artifactPreviewCurves,
  artifactPreviewTitle,
  artifactPreviewObserveTarget,
  openArtifactPreview,
  resetArtifactPreview,
  artifactLabel,
} = useArtifactPreview({
  selectedStudyId,
  runArtifacts,
  describeError,
})
// 产物管理（改名 / 标签 / 保留 / 下载 / 清理）见 composables/pipeline/useArtifactActions
const {
  artifactActionLoading,
  artifactCleanupLoading,
  editingDisplayId,
  displayNameDraft,
  tagDrafts,
  derivedRetentionPillClass,
  startEditDisplayName,
  cancelEditDisplayName,
  commitDisplayName,
  tagDraftFor,
  setTagDraft,
  commitTagDraft,
  removeDerivedTag,
  setArtifactRetentionAction,
  isArtifactActionLoading,
  cleanupCachedArtifacts,
  downloadArtifact,
} = useArtifactActions({
  selectedStudyId,
  statusMessage,
  describeError,
  runArtifacts,
  activeExecutionId,
  selectedArtifactPreview,
  resetArtifactPreview,
  executionDetailTab,
  loadExecutionLineage,
})
// ICA 成分人工剔除交互见 composables/pipeline/useIcaInteraction
const {
  icaInteraction,
  icaExcludedComponents,
  icaInteractionLoading,
  icaDecisionSubmitting,
  icaResuming,
  icaInteractionError,
  showIcaInteractionPanel,
  icaInteractionComponents,
  icaReviewerHref,
  resetIcaInteractionState,
  loadSelectedIcaInteraction,
  toggleIcaComponent,
  submitIcaDecision,
  resumeIcaNode,
  icaComponentLabel,
  icaComponentMetric,
} = useIcaInteraction({
  selectedJob,
  selectedStudyId,
  activeExecutionId,
  latestPipelineExecution,
  statusMessage,
  describeError,
  refreshRunState,
  isTerminalRunStatus,
  startRunPolling,
})
const liteGraphShell = ref<HTMLElement | null>(null)
const liteGraphCanvasEl = ref<HTMLCanvasElement | null>(null)
const liteGraphReady = ref(false)
const {
  draftJustRestored,
  scheduleDraftSave,
  clearDraft,
  tryRestoreDraft,
} = useDraftPersistence({
  definition,
  pipelineName,
  pipelineDescription,
  selectedStudyId,
  selectedPipelineId,
  currentPipeline,
  dirty,
  statusMessage,
  hydrating,
  syncDefinitionToLiteGraph,
})
const {
  taskActionLoading,
  taskEventsByTaskId,
  isPipelineExecutionTask,
  taskEventsForTask,
  canCancelTask,
  canRetryTask,
  loadTaskEvents,
  cancelTask,
  retryTask,
} = useExecutionTasks({
  selectedStudyId,
  statusMessage,
  activeExecutionId,
  activeExecutionDetail,
  refreshRunState,
  describeError,
})
let nodeCounter = 0
let liteGraph: LGraph | null = null
let liteGraphCanvas: LGraphCanvas | null = null
let resizeObserver: ResizeObserver | null = null
let syncingGraph = false
let pendingGraphSync = 0
// litegraph 节点类型注册 + 自绘类（ElysPipelineNode）见 composables/pipeline/useLiteGraphNodeTypes
// getLiteGraph 注入 liteGraph 实例 getter（自绘里判 LoadData 可达性用）；registerLiteGraphNodeSpecs 由下方 init/createLiteGraphNode 调。
const { registerLiteGraphNodeSpecs } = useLiteGraphNodeTypes({
  nodeSpecs,
  jobForNodeId,
  getLiteGraph: () => liteGraph,
  defaultParams,
})
let draggedNodeType = ''
let liteGraphPixelRatio = 1
// 「加载适应窗口」：加载后短时间内让 resize 改为重新 fit（而非保留旧缩放），用于应对右侧检查器
// 抽屉 0.22s CSS 过渡逐帧挤窄画布——否则 fit 按过渡前的过宽画布算、之后 resize 只保留不重 fit 致溢出。
// 窗口内每次 resize→重 fit；360ms 超时或用户手动复位即退出，绝不覆盖用户手动缩放/摆放。
let pendingFitOnLoad = false
let pendingFitClearTimer = 0
const pipelineContextMenu = reactive<{
  open: boolean
  x: number
  y: number
  nodeId: string
  graphX: number
  graphY: number
  items: PipelineContextMenuItem[]
}>({
  open: false,
  x: 0,
  y: 0,
  nodeId: '',
  graphX: 0,
  graphY: 0,
  items: [],
})

const canSave = computed(() => Boolean(selectedStudyId.value && pipelineName.value.trim()))
// 运行控制（运行对话框 + 创建 / 取消 / 重试 + 准入判定）见 composables/pipeline/useRunControl
const {
  runDialogOpen,
  executionMode,
  executionActionLoading,
  runDrawerOpen,
  currentPipelineStatus,
  pipelineCanCreateExecution,
  executionModeAllowed,
  runDisabledReason,
  canOpenRunDialog,
  canSubmitRun,
  canCancelLatestExecution,
  canRetryLatestExecution,
  latestExecutionActionHint,
  runLockSummary,
  openRunDialog,
  closeRunDialog,
  submitRunDialog,
  runPipeline,
  cancelLatestExecution,
  retryLatestExecution,
} = useRunControl({
  selectedStudyId,
  currentPipeline,
  statusMessage,
  dirty,
  canSave,
  saving,
  runningPipeline,
  describeError,
  latestPipelineExecution,
  activeExecutionId,
  refreshRunState,
  startRunPolling,
  stopRunPolling,
  resetRunTracking,
  isTerminalRunStatus,
  savePipeline,
  buildRunSelectionOverridePayload,
})
// —— 节点参数编辑（条件显示 visible_when / 高级折叠 / 通用读写 / 标题）见 composables/pipeline/useNodeParamEditor ——
const {
  visibleBasicProperties,
  visibleAdvancedProperties,
  formatParamValue,
  handleParamInput,
  handleParamCheckbox,
  handleNodeTitleInput,
} = useNodeParamEditor({
  selectedNode,
  selectedNodeSpec,
  updateLiteGraphNode,
  markDirty,
})
// 节点拓扑与保留（reachableNodeIds / isLeafNode / topologyLabel / keep checkbox）见 composables/pipeline/useNodeTopology
const {
  reachableNodeIds,
  isLeafNode,
  keepLeafHint,
  selectedNodeKeep,
  topologyLabel,
  keepCheckboxDisabled,
  onToggleKeep,
} = useNodeTopology({
  selectedNode,
  definition,
  updateLiteGraphNode,
  markDirty,
})
// [Dead code 已清理] 旧 LoadData chip UI 相关 computed (loadDataSelectionMode/eligibleLoadDataDatasets/matchedLoadDataDatasets/loadData*Options 等) 已全部删除，
// 筛选逻辑迁移到 LoadDataPanel.vue 组件内部。

// === Epoch / ERP 节点：事件标签下拉 === 见 composables/pipeline/useEventSelectEditor
const {
  availableEventLabels,
  getEventIdArray,
  isEventIdSelected,
  toggleEventId,
  clearEventIds,
} = useEventSelectEditor({
  selectedNode,
  definition,
  loadDataSelectedInfos,
  updateLiteGraphNode,
  markDirty,
})

/** 取一个 LoadData 节点真正"选中"的 data_infos。
 *  - LoadData 永远 explicit（task #61），Selected File 列表 = dataset_ids = 真正输入。
 *  - dataset_ids 为空 → 返回空数组（节点没有有效输出，下游不该看到事件）。
 *  - 对 cache 里的 data_info 按 dataset_id 严格过滤 —— 即使 cache 里有脏数据
 *    （比如 selection_mode 还残留 'filter' 时拉到的全集），也只用真正选中的。
 */
function loadDataSelectedInfos(node: PipelineGraphNode): LoadDataDataInfo[] {
  const raw = node.params?.dataset_ids
  const ids = Array.isArray(raw) ? raw.map((v) => String(v)).filter(Boolean) : []
  if (!ids.length) return []
  const set = new Set(ids)
  const cached = loadDataInfosByNodeId[node.id] || []
  return cached.filter((info) => set.has(String(info.dataset_id)))
}

// Epoch/ERP 事件聚合 availableEventLabels + event_select 多选编辑 → composables/pipeline/useEventSelectEditor

// === 保存设置（P4）=== display_name 模板 / auto_tags 预览 / 自定义标签
// 见 composables/pipeline/useSaveSettingsPanel
const {
  saveSettingsOpen,
  userTagDraft,
  saveSpec,
  effectiveNameTemplate,
  previewDisplayName,
  autoTagsPreview,
  userTagsArray,
  getSaveSetting,
  onSaveSettingInput,
  onSaveSettingsToggle,
  removeUserTag,
  commitUserTagDraft,
} = useSaveSettingsPanel({
  selectedNode,
  selectedNodeSpec,
  studyDatasets,
  updateLiteGraphNode,
  markDirty,
})

// isLeafNode（拓扑角色判定）→ composables/pipeline/useNodeTopology（上方解构）

// 保存设置的 splitMode / 模板渲染 / display_name 预览 / auto_tags / 自定义标签编辑 → composables/pipeline/useSaveSettingsPanel

// tags_input 通用属性渲染（用户自由打标签 chip 输入）见 composables/pipeline/useTagsInputEditor
const {
  getTagsArray,
  paramTagDraftFor,
  setParamTagDraft,
  commitParamTagDraft,
  toggleParamTag,
} = useTagsInputEditor({
  selectedNode,
  updateLiteGraphNode,
  markDirty,
})

// === channel_list 类型：从上游 LoadData 通道做 listbox 多选 ===
// 设计语义（与节点 spec.help 一致）：
//   单选 = 单通道做参考；多选 = 这些通道的平均做参考；全选 = 共同平均参考
// channel_list 属性编辑（上游 LoadData 通道交集 + listbox 多选）见 composables/pipeline/useChannelListEditor
const {
  upstreamChannels,
  channelFilterFor,
  setChannelFilter,
  getChannelListArray,
  isChannelSelected,
  selectAllChannels,
  clearChannels,
  invertChannels,
  filteredChannelOptions,
  handleChannelListClick,
  handleChannelListKeydown,
} = useChannelListEditor({
  selectedNode,
  definition,
  loadDataSelectedInfos,
  updateLiteGraphNode,
  markDirty,
})

const runSelectionOverridePayload = computed(() => buildRunSelectionOverridePayload())
const runSelectionOverrideItems = computed(() =>
  Object.entries(runSelectionOverridePayload.value).map(([nodeId, override]) => {
    const node = definition.value.graph.nodes.find((item) => item.id === nodeId)
    const datasetCount = override.dataset_ids?.length || 0
    const fileCount = override.dataset_file_ids?.length || 0
    const source = String(override.selector_json?.source || '')
    return {
      nodeId,
      nodeTitle: node?.title || nodeId,
      datasetCount,
      fileCount,
      sourceLabel: source === 'legacy_pipeline_explicit'
        ? '兼容旧工作流 explicit 列表'
        : '本次运行覆盖，不修改工作流定义',
    }
  }),
)
const runSelectionOverrideSummaryText = computed(() => {
  if (!runSelectionOverrideItems.value.length) return '没有本次覆盖；运行将按工作流中保存的选择规则重新解析。'
  const totalDatasets = runSelectionOverrideItems.value.reduce((sum, item) => sum + item.datasetCount, 0)
  return `${runSelectionOverrideItems.value.length} 个 LoadData 节点携带输入覆盖，合计 ${totalDatasets} 个数据集。`
})
// 运行态派生 computed（executionJobByNodeId / selectedJob / 产物映射等）见 composables/pipeline/useRunExecution（解构见上方装配区）
// 产物预览 computed（指标 / 事件 / 曲线 / 标题 / 观察目标）见 composables/pipeline/useArtifactPreview（解构见上方装配区）
// ICA 面板显隐 / 成分列表 computed 见 composables/pipeline/useIcaInteraction（解构见上方装配区）
const executionModeDescription = computed(() => EXECUTION_MODE_OPTIONS.find((option) => option.value === executionMode.value)?.description || '')
const runDialogSummary = computed(
  () => `${formatExecutionMode(executionMode.value)} · ${definition.value.graph.nodes.length} 节点`,
)
const executionDetailTabs: Array<{ key: ExecutionDetailTab; label: string }> = [
  { key: 'artifacts', label: '结果' },
  { key: 'jobs', label: '节点任务' },
  { key: 'tasks', label: '任务' },
  { key: 'inputs', label: '输入' },
  { key: 'summary', label: '摘要' },
  { key: 'manifest', label: 'Manifest' },
  { key: 'lineage', label: 'Lineage' },
]
const manifestOutputCount = computed(() => {
  const outputs = activeExecutionManifest.value?.outputs
  if (Array.isArray(outputs)) return outputs.length
  if (isRecord(outputs)) {
    const artifacts = outputs.artifacts
    return Array.isArray(artifacts) ? artifacts.length : Object.keys(outputs).length
  }
  return 0
})

// 节点连接管理（入链列表/上游候选/快连/断连）见 composables/pipeline/useGraphConnections
// findLiteGraphNode/syncDefinitionFrom/ToLiteGraph 为下方 hoisted 画布函数，注入。
const {
  upstreamNodeId,
  selectedNodeInputLinks,
  connectableUpstreamCandidates,
  quickConnectUpstream,
  upstreamNodeLabel,
  removeLink,
} = useGraphConnections({
  selectedNode,
  selectedNodeSpec,
  definition,
  statusMessage,
  specForNode,
  markDirty,
  findLiteGraphNode,
  syncDefinitionFromLiteGraph,
  syncDefinitionToLiteGraph,
})

watch(selectedStudyId, async (studyId) => {
  if (hydrating.value || !studyId) return
  await Promise.all([loadPipelines(), loadDatasets(studyId)])
})

watch(
  () => route.query,
  async () => {
    if (hydrating.value || !hasPipelineRouteTarget()) return
    await applyPipelineRouteTarget()
  },
)

watch(selectedNodeId, (id) => {
  upstreamNodeId.value = ''
  resetArtifactPreview()
  void resolveLoadDataPreview()
  void loadSelectedIcaInteraction()
  // 任何"需要上游 LoadData 元信息"的节点（Epoch 看 event_labels，Re-reference 等
  // channel_list 节点看 ch_names）切换到时都拉一遍 —— 涵盖所有非 LoadData 节点比按类型枚举更稳。
  if (selectedNode.value && selectedNode.value.type !== LOAD_DATA_NODE_TYPE) {
    void fetchEventLabelsForAllLoadData()
  }
  // 选中节点时自动打开 Inspector 抽屉
  if (id) showInspector()
})

watch([executionJobs, runArtifacts], () => {
  applyLiteGraphRunState()
  void loadSelectedIcaInteraction()
})

// 数据集列表异步加载完（或变化）时，重画 LoadData 节点卡：建节点那一刻 studyDatasets 可能还没回来，
// 卡上 dataset_ids 查不到 recording → 误显「(数据缺失)」；列表到位后重画即可解析出文件名。
watch(studyDatasets, () => {
  if (!liteGraph) return
  for (const node of liteGraphNodes(liteGraph)) {
    if (String((node as { type?: unknown }).type || '') === LOAD_DATA_NODE_TYPE) applyNodeWidgets(node)
  }
  liteGraphCanvas?.setDirty(true, true)
})

onMounted(async () => {
  restoreLayoutState()
  await nextTick()
  initLiteGraphCanvas()
  hydrating.value = true
  await loadNodeSpecs()
  hydrating.value = false
  if (selectedStudyId.value) {
    await Promise.all([loadPipelines(routeTarget()), loadDatasets(selectedStudyId.value), loadStudyMontages()])
  }
})

// keep-alive：本页在容器 4-tab 中被缓存。切回时重绑快捷键 + 重算画布尺寸（隐藏期 ResizeObserver 不触发，防错位/糊）
onActivated(() => {
  document.addEventListener('keydown', handleLayoutKeydown)
  // 切回本页：画布在就补尺寸；万一画布没了（异常 / HMR）就重建，避免卡在“正在初始化”
  if (liteGraphCanvas) {
    liteGraphReady.value = true
    resizeLiteGraphCanvas()
  } else {
    initLiteGraphCanvas()
  }
})

// 切走时解绑快捷键 + 停运行轮询，避免后台空转
onDeactivated(() => {
  document.removeEventListener('keydown', handleLayoutKeydown)
  stopRunPolling()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleLayoutKeydown)
  document.removeEventListener('mousemove', onDrawerDragMove)
  document.removeEventListener('mouseup', onDrawerDragEnd)
  stopRunPolling()
  if (pendingGraphSync) window.cancelAnimationFrame(pendingGraphSync)
  resizeObserver?.disconnect()
  liteGraphCanvas?.unbindEvents()
  liteGraph?.stop()
  liteGraphCanvas = null
  liteGraph = null
})

// HMR 兜底：热更新会重跑 <script setup>，把 liteGraphReady / definition 重置成初值，
// 但 onMounted 不会在热更新时重跑、旧的 LGraphCanvas 仍绑在同一个 <canvas> 上空转，
// 于是页面卡在“正在初始化画布”。这里在旧模块卸载前停掉旧画布，并在新模块下一帧补一次初始化。
// 仅 dev 生效：生产构建里 import.meta.hot 为假，整段被 Vite 剔除。
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    resizeObserver?.disconnect()
    liteGraphCanvas?.unbindEvents()
    liteGraph?.stop()
    liteGraphCanvas = null
    liteGraph = null
  })
  requestAnimationFrame(() => {
    if (!liteGraphCanvas && liteGraphCanvasEl.value) initLiteGraphCanvas()
  })
}

interface PipelineRouteTarget {
  studyId?: string
  pipelineId?: string
  executionId?: string
}

function routeQueryValue(...keys: string[]) {
  for (const key of keys) {
    const value = route.query[key]
    const first = Array.isArray(value) ? value[0] : value
    if (first !== undefined && first !== null && String(first).trim()) return String(first)
  }
  return ''
}

function routeTarget(): PipelineRouteTarget {
  return {
    studyId: selectedStudyId.value,
    pipelineId: routeQueryValue('pipeline_id', 'pipelineId'),
    executionId: routeQueryValue('execution_id', 'executionId'),
  }
}

function hasPipelineRouteTarget() {
  return Boolean(route.query.pipeline_id || route.query.pipelineId || route.query.execution_id || route.query.executionId)
}

async function applyPipelineRouteTarget() {
  if (!selectedStudyId.value) return
  const target = routeTarget()
  if (target.pipelineId || target.executionId) {
    await loadPipelines(target)
  }
}

function initLiteGraphCanvas() {
  // 已建好画布：确保 ready 标志为真（HMR / 重复调用时把被重置的标志补回来），不重复初始化
  if (liteGraphCanvas) {
    liteGraphReady.value = true
    return
  }
  if (!liteGraphCanvasEl.value) return

  configureLiteGraphTheme()
  liteGraph = new LGraph()
  liteGraphCanvas = new LGraphCanvas(liteGraphCanvasEl.value, liteGraph, { skip_events: true } as ConstructorParameters<
    typeof LGraphCanvas
  >[2])
  const canvas = liteGraphCanvas as LooseLiteGraphCanvas
  const graph = liteGraph as unknown as LooseLiteGraph
  bindHiDpiLiteGraphEvents(liteGraphCanvas, liteGraphCanvasEl.value)
  liteGraphCanvas.bindEvents()
  canvas.render_always = true
  liteGraphCanvas.autoresize = false
  canvas.clear_background_color = '#F7F9FC'
  liteGraphCanvas.background_image = ''
  liteGraphCanvas.render_canvas_border = false
  liteGraphCanvas.render_shadows = false
  // highquality_render 控制 render_connection_arrows + 连线中点抓手圆点的绘制。
  // 我们不显示箭头，也不需要那个抓手 → 关掉，线就干净了。
  liteGraphCanvas.highquality_render = false
  liteGraphCanvas.allow_searchbox = false
  liteGraphCanvas.render_connection_arrows = false
  liteGraphCanvas.render_connections_border = false
  liteGraphCanvas.render_curved_connections = true
  liteGraphCanvas.connections_width = 3.6
  liteGraphCanvas.round_radius = 6
  liteGraphCanvas.node_title_color = '#1F2A37'
  liteGraphCanvas.default_link_color = LINK_DEFAULT_COLOR
  liteGraphCanvas.title_text_font = '600 12px "Segoe UI", Arial, sans-serif'
  liteGraphCanvas.inner_text_font = '12px "Segoe UI", Arial, sans-serif'
  liteGraphCanvas.ds.min_scale = LITEGRAPH_MIN_ZOOM
  liteGraphCanvas.ds.max_scale = LITEGRAPH_MAX_ZOOM
  liteGraphCanvas.default_connection_color = {
    input_off: '#94A3B8',
    input_on: '#2E6BFF',
    output_off: '#94A3B8',
    output_on: '#2E6BFF',
  }
  canvas.default_connection_color_byType = pipelinePortColors()
  canvas.default_connection_color_byTypeOff = pipelinePortColors(0.45)
  liteGraphCanvas.onDrawBackground = drawPipelineCanvasBackground
  liteGraphCanvas.show_info = false // 关掉画布左下角 T/I/N/V/FPS 调试浮层（LiteGraph 默认 true，须显式关）
  canvas.showNodePanel = () => false
  liteGraphCanvas.onShowNodePanel = () => false
  canvas.processContextMenu = (node: LGraphNode | null, event: LiteGraphContextEvent) =>
    showPipelineContextMenu(node as LiteGraphNode | null, event)
  liteGraphCanvas.onNodeSelected = (node) => {
    selectedNodeId.value = getLiteGraphNodeId(node as LiteGraphNode)
    syncDefinitionFromLiteGraph(false)
  }
  liteGraphCanvas.onNodeDeselected = () => {
    const selected = Object.values(liteGraphCanvas?.selected_nodes || {})
    if (!selected.length) selectedNodeId.value = ''
  }
  canvas.onNodeDblClicked = (node: LGraphNode) => openNodeWaveform(node)
  liteGraphCanvas.onNodeMoved = () => scheduleLiteGraphSync(true)
  canvas.onAfterChange = () => scheduleLiteGraphSync(true)

  graph.onAfterChange = () => scheduleLiteGraphSync(true)
  graph.onConnectionChange = () => scheduleLiteGraphSync(true)
  liteGraph.onNodeAdded = () => scheduleLiteGraphSync(true)
  graph.onNodeRemoved = () => scheduleLiteGraphSync(true)

  liteGraph.start()
  registerLiteGraphNodeSpecs()
  resizeLiteGraphCanvas()
  resizeObserver = new ResizeObserver(resizeLiteGraphCanvas)
  if (liteGraphShell.value) resizeObserver.observe(liteGraphShell.value)
  liteGraphReady.value = true
  syncDefinitionToLiteGraph()
}

function configureLiteGraphTheme() {
  const theme = LiteGraph as LooseLiteGraphTheme
  theme.NODE_TITLE_HEIGHT = 30
  theme.NODE_TITLE_TEXT_Y = 20
  theme.NODE_SLOT_HEIGHT = 22
  theme.DEFAULT_SHADOW_COLOR = 'rgba(0,0,0,0.04)'
  theme.NODE_COLLAPSED_RADIUS = 12
  // 端口命中半径 — 默认 6，调大让端口更容易点中和拖线
  theme.NODE_SLOT_RADIUS = 8
  theme.NODE_TEXT_SIZE = 12
  theme.NODE_SUBTEXT_SIZE = 11
  theme.NODE_TITLE_COLOR = '#1F2A37'
  theme.NODE_SELECTED_TITLE_COLOR = '#111827'
  theme.NODE_TEXT_COLOR = '#536273'
  theme.NODE_DEFAULT_COLOR = '#D4DDE8'
  theme.NODE_DEFAULT_BGCOLOR = '#FFFFFF'
  theme.NODE_DEFAULT_BOXCOLOR = '#2F5F8F'
  theme.NODE_BOX_OUTLINE_COLOR = '#2F5F8F'
  theme.LINK_COLOR = LINK_DEFAULT_COLOR
  theme.CONNECTING_LINK_COLOR = LINK_CONNECTING_COLOR
  theme.WIDGET_BGCOLOR = '#F8FAFC'
  theme.WIDGET_OUTLINE_COLOR = '#D7DEE8'
  theme.WIDGET_TEXT_COLOR = '#1F2A37'
  theme.WIDGET_SECONDARY_TEXT_COLOR = '#536273'
  theme.NODE_WIDGET_HEIGHT = 24 // 略高于默认 20，和 28px 端口行更协调
  Object.assign(LGraphCanvas.link_type_colors, pipelinePortColors(0.92))
  patchLiteGraphLinkHighlight()
}

// LiteGraph 内置在节点被选中 / 拖动时,会把相关连线 push 进 highlighted_links,
// renderLink 里 hardcode `color = "#FFF"` —— 在浅色画布上等于看不见。
// 这里 patch 一次 prototype,统一改为蓝色高亮 + 加粗,把所有走 highlighted_links 的场景都覆盖。
function patchLiteGraphLinkHighlight() {
  const proto = LGraphCanvas.prototype as Record<string, any>
  const origRenderLink = proto.renderLink
  if (typeof origRenderLink !== 'function') return
  // 防止 HMR 重载时把 patch 嵌套包装多层
  if ((origRenderLink as any)[LINK_HIGHLIGHT_PATCH_MARK]) return

  const patched = function patchedRenderLink(
    this: LooseLiteGraphCanvas,
    ctx: CanvasRenderingContext2D,
    a: number[],
    b: number[],
    link: { id?: string | number; type?: string | number } | null,
    skipBorder: boolean,
    flow: boolean,
    color: string | undefined,
    ...rest: unknown[]
  ) {
    const hl = (this as any).highlighted_links || {}
    let bypassedId: string | number | null = null
    if (link != null && link.id != null && hl[link.id]) {
      // 临时把这条 link 从 highlighted_links 移除,绕过 LiteGraph 里 hardcode 的 `color="#FFF"`
      bypassedId = link.id
      delete hl[link.id]
      if (!color) color = LINK_HIGHLIGHT_COLOR
    }

    const originalWidth = (this as any).connections_width
    if (bypassedId !== null) {
      ;(this as any).connections_width = originalWidth * LINK_HIGHLIGHT_WIDTH_MULT
    }
    try {
      return origRenderLink.call(this, ctx, a, b, link, skipBorder, flow, color, ...rest)
    } finally {
      if (bypassedId !== null) {
        hl[bypassedId] = true
        ;(this as any).connections_width = originalWidth
      }
    }
  }
  ;(patched as any)[LINK_HIGHLIGHT_PATCH_MARK] = true
  proto.renderLink = patched
}

function drawPipelineCanvasBackground(ctx: CanvasRenderingContext2D, visibleArea: Float32Array | number[]) {
  const area = visibleArea || [0, 0, 1600, 900]
  const left = Number(area[0] || 0)
  const top = Number(area[1] || 0)
  const width = Number(area[2] || 1600)
  const height = Number(area[3] || 900)
  const major = 160
  const minor = 32

  ctx.save()
  ctx.fillStyle = '#F8FAFC'
  ctx.fillRect(left, top, width, height)

  drawGrid(ctx, left, top, width, height, minor, 'rgba(83, 98, 115, 0.065)')
  drawGrid(ctx, left, top, width, height, major, 'rgba(47, 95, 143, 0.13)', 1.15)
  drawCanvasAxis(ctx, left, top, width, height)
  ctx.restore()
}

function drawGrid(
  ctx: CanvasRenderingContext2D,
  left: number,
  top: number,
  width: number,
  height: number,
  step: number,
  color: string,
  lineWidth = 1,
) {
  const scale = liteGraphCanvas?.ds?.scale || 1
  ctx.beginPath()
  ctx.strokeStyle = color
  ctx.lineWidth = lineWidth / Math.max(scale, 0.5)
  const startX = Math.floor(left / step) * step
  const endX = left + width
  const startY = Math.floor(top / step) * step
  const endY = top + height
  for (let x = startX; x <= endX; x += step) {
    ctx.moveTo(x, top)
    ctx.lineTo(x, endY)
  }
  for (let y = startY; y <= endY; y += step) {
    ctx.moveTo(left, y)
    ctx.lineTo(endX, y)
  }
  ctx.stroke()
}

function drawCanvasAxis(ctx: CanvasRenderingContext2D, left: number, top: number, width: number, height: number) {
  const scale = liteGraphCanvas?.ds?.scale || 1
  const right = left + width
  const bottom = top + height
  ctx.beginPath()
  ctx.strokeStyle = 'rgba(47, 95, 143, 0.18)'
  ctx.lineWidth = 1.2 / Math.max(scale, 0.5)
  if (left <= 0 && right >= 0) {
    ctx.moveTo(0, top)
    ctx.lineTo(0, bottom)
  }
  if (top <= 0 && bottom >= 0) {
    ctx.moveTo(left, 0)
    ctx.lineTo(right, 0)
  }
  ctx.stroke()
}

// litegraph 图遍历 liteGraphNodes / liteGraphReachableFromLoadData → composables/pipeline/litegraphUtils

function jobForNodeId(nodeId: string) {
  return executionJobByNodeId.value.get(nodeId) || null
}

function artifactCountForJob(jobId: string) {
  return runArtifactsByJobId.value.get(jobId)?.length || 0
}

// 产物预览函数（open / reset）见 composables/pipeline/useArtifactPreview

// 双击画布节点：若该节点本次运行产出了已保存的结果，则在弹出窗口查看其时域图
function openNodeWaveform(node: LiteGraphNode | LGraphNode | null) {
  const studyId = selectedStudyId.value
  if (!studyId) return
  const nodeId = getLiteGraphNodeId(node)
  if (!nodeId) return
  const job = executionJobByNodeId.value.get(nodeId)
  if (!job) {
    statusMessage.value = '该节点本次运行没有执行记录，先运行工作流再查看'
    return
  }
  // 手动去伪迹去坏段：交互节点在 waiting_user_input 时双击 → 打开波形审核台（标坏段/坏道 → 确认 → 续跑）
  if (job.node_type === 'eeg/preproc/artifact_mark' && job.status === 'waiting_user_input') {
    const params = new URLSearchParams({
      studyId,
      executionId: String(activeExecutionId.value || job.execution_id || ''),
      jobId: job.id,
    })
    const reviewLink = document.createElement('a')
    reviewLink.href = `/artifact?${params.toString()}`
    reviewLink.target = '_blank'
    reviewLink.rel = 'noopener'
    document.body.appendChild(reviewLink)
    reviewLink.click()
    reviewLink.remove()
    return
  }
  const artifacts = runArtifactsByJobId.value.get(job.id) || []
  const saved = artifacts.filter((item) => !item.deleted_at)
  if (!saved.length) {
    statusMessage.value = '该节点输出未保存（未保留的中间结果），无法查看时域图'
    return
  }
  // evoked（ERP）可能是同一节点的多个条件产物 → 一起送时域页按"数据集"对比；
  // 其余按 data_type 路由：TFR=/observe/tfr、PSD=/observe/psd、其余=/observe/waveform。
  const evokeds = saved.filter((item) => item.data_type === 'evoked')
  const psds = saved.filter((item) => (item.data_type || '').toLowerCase() === 'psd')
  const tfrs = saved.filter((item) => (item.data_type || '').toLowerCase() === 'tfr')
  const icas = saved.filter((item) => (item.data_type || '').toLowerCase() === 'ica')
  let href: string
  if (evokeds.length) {
    const ids = evokeds.map((e) => e.id).join(',')
    const params = new URLSearchParams({
      studyId,
      study_output_id: ids,
      name: evokeds.length > 1 ? 'ERP（多条件对比）' : evokeds[0].display_name || 'ERP',
      type: 'evoked',
    })
    href = `/observe/waveform?${params.toString()}`
  } else if (psds.length) {
    // PSD 多条件产物（同 evoked 口径）→ 一起送频域页按"数据集"对比
    const ids = psds.map((p) => p.id).join(',')
    const params = new URLSearchParams({
      studyId,
      study_output_id: ids,
      name: psds.length > 1 ? '功率谱（多条件对比）' : psds[0].display_name || '功率谱',
    })
    href = `/observe/psd?${params.toString()}`
  } else if (tfrs.length) {
    // TFR 多条件产物（同 evoked/psd 口径）→ 一起送时频页按"数据集"对比；
    // 只送本节点产物，观察页据此呈现，保证"双击哪个节点 = 看哪个节点产的"
    const ids = tfrs.map((t) => t.id).join(',')
    const params = new URLSearchParams({
      studyId,
      study_output_id: ids,
      name: tfrs.length > 1 ? '时频（多条件对比）' : tfrs[0].display_name || '时频',
    })
    href = `/observe/tfr?${params.toString()}`
  } else if (icas.length) {
    // ICA 矩阵产物 → 成分审阅页（只读查看；选成分的决策流走 Apply ICA 暂停）
    const params = new URLSearchParams({ studyId, study_output_id: icas[0].id, name: icas[0].display_name || 'ICA 成分' })
    href = `/ica?${params.toString()}`
  } else {
    const target = saved[0]
    const base = {
      studyId,
      study_output_id: target.id,
      name: target.display_name || target.data_type || '结果',
      type: target.data_type || '',
    }
    href = `/observe/waveform?${new URLSearchParams(base).toString()}`
  }
  // 用 <a target="_blank"> 模拟点链接 → 浏览器按"在新标签页打开"处理（可拖进标签栏并排），
  // 比 window.open(name) 更可靠：后者在部分浏览器里会被当成独立弹窗，无法并入标签栏
  const link = document.createElement('a')
  link.href = href
  link.target = '_blank'
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

// 产物预览构建函数（label / summary / metrics / events / curves）见 composables/pipeline/useArtifactPreview

function jobErrorMessage(job: PipelineJob) {
  const errors = job.error_json?.errors
  if (Array.isArray(errors)) {
    const first = errors.find(Boolean)
    if (isRecord(first)) return String(first.message || first.code || '')
    if (first) return String(first)
  }
  // log_tail 仅在任务真失败时作为错误兜底；成功/缓存命中 job 的 log_tail
  //（如 "Cache hit from job …"）是调试信息而非错误，不向用户暴露（缓存调试见 cacheHitDebug + ?debug）。
  const normalized = normalizedJobStatus(job.status)
  if (normalized === 'failed' || normalized === 'canceled') return job.log_tail || ''
  return ''
}

// 缓存命中的来源 job 等信息只对开发者可见：本地 DEV，或 URL 带 ?debug（云端生产构建排查用，
// DEV 在生产构建为 false 故必须保留 ?debug 入口）。普通用户无需知道缓存命中这件事。
const cacheDebugVisible = computed(
  () => Boolean((import.meta as { env?: { DEV?: boolean } }).env?.DEV) || route.query.debug != null,
)
const cacheHitDebug = computed(() => {
  if (!cacheDebugVisible.value) return ''
  const job = selectedJob.value
  if (!job || normalizedJobStatus(job.status) !== 'cached') return ''
  return job.log_tail || '缓存命中'
})

// 产物列表：多产物默认折叠成一行汇总，点开才看明细，避免对用户铺一长串技术文件名。
const artifactListExpanded = ref(false)
watch(selectedJob, () => {
  artifactListExpanded.value = false
})
const artifactSummaryText = computed(() => {
  const items = selectedNodeArtifacts.value
  if (!items.length) return ''
  const typeLabels = new Set(items.map((item) => formatDataType(item.data_type)))
  const typeText = typeLabels.size === 1 ? [...typeLabels][0] : '产物'
  const subjects = new Set(items.map((item) => item.bids_subject_id || item.subject_id).filter(Boolean))
  const conditions = new Set(items.map((item) => item.condition).filter(Boolean))
  const parts = [`${items.length} 个${typeText}`]
  if (subjects.size > 1) parts.push(`${subjects.size} 名被试`)
  if (conditions.size > 1) parts.push(`${conditions.size} 个条件`)
  return parts.join(' · ')
})
function artifactFriendlyLabel(artifact: StudyOutput) {
  const subject = artifact.bids_subject_id || artifact.subject_id || ''
  const condition = artifact.condition || ''
  const friendly = [subject, condition].filter(Boolean).join(' · ')
  if (friendly) return friendly
  // 退化：结构化字段缺失时取 display_name 末段（去 BIDS 路径前缀），仍比整条 glob 路径短。
  const name = artifact.display_name || ''
  if (name) return name.split('/').pop() || name
  return formatDataType(artifact.data_type)
}

function applyLiteGraphRunState() {
  if (!liteGraph || !liteGraphCanvas) return
  for (const graphNode of liteGraphNodes(liteGraph)) {
    const nodeId = getLiteGraphNodeId(graphNode)
    const definitionNode = definition.value.graph.nodes.find((node) => node.id === nodeId)
    applyLiteGraphNodeRunState(graphNode, nodeId, definitionNode ? specForNode(definitionNode) : null)
  }
  liteGraphCanvas.setDirty(true, true)
}

function applyLiteGraphNodeRunState(graphNode: LiteGraphNode, nodeId: string, spec?: NodeSpec | null) {
  const job = jobForNodeId(nodeId)
  if (!job) {
    graphNode.color = '#D4DDE8'
    graphNode.boxcolor = categoryColor(spec?.category)
    graphNode.bgcolor = '#FFFFFF'
    return
  }
  const color = nodeStatusColor(job.status)
  graphNode.color = withAlpha(color, 0.34)
  graphNode.boxcolor = color
  graphNode.bgcolor = nodeStatusSoftColor(job.status)
}

// 节点自绘原语 drawNodeAccentBar / drawNodeStatusBadge / drawNodeSaveIcon → composables/pipeline/litegraphUtils

function centerLiteGraphView() {
  if (!liteGraph || !liteGraphCanvas) return
  const targetNode = (selectedNodeId.value && findLiteGraphNode(selectedNodeId.value)) || liteGraphNodes(liteGraph)[0]
  if (targetNode) liteGraphCanvas.centerOnNode(targetNode)
  liteGraphCanvas.setDirty(true, true)
}

function resetLiteGraphZoom() {
  if (!liteGraphCanvas) return
  pendingFitOnLoad = false // 用户手动复位 → 退出加载适应窗口，别被随后的 resize 重新 fit 覆盖
  liteGraphCanvas.ds.scale = liteGraphPixelRatio
  liteGraphCanvas.ds.offset = [24, 64]
  liteGraphCanvas.setDirty(true, true)
}

/** 缩放 + 平移，让全部节点恰好落进可视区（解决「一屏装不下」）。
 *  镜像 LiteGraph centerOnNode 的坐标变换：画布像素 = (图坐标 + ds.offset) × ds.scale，
 *  这里改成把「所有节点包围盒的中心」对齐到画布中心，缩放取「宽、高两个方向都装得下」的较小值。
 *  W/H 用 canvas 位图像素（已含 devicePixelRatio），故 padding 也按 pixelRatio 放大；
 *  缩放夹在 ds.min_scale/max_scale 内（resizeLiteGraphCanvas 设的，已含 pixelRatio）。 */
function fitGraphToView(padding = 56) {
  if (!liteGraph || !liteGraphCanvas) return
  const nodes = liteGraphNodes(liteGraph)
  if (!nodes.length) return
  const W = liteGraphCanvasEl.value?.width || 0
  const H = liteGraphCanvasEl.value?.height || 0
  if (W < 2 || H < 2) return
  const titleH = LiteGraph.NODE_TITLE_HEIGHT || 30
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of nodes) {
    const x = Number(node.pos?.[0] ?? 0)
    const y = Number(node.pos?.[1] ?? 0)
    const w = Number(node.size?.[0] ?? NODE_CARD_WIDTH)
    const h = Number(node.size?.[1] ?? NODE_CARD_MIN_HEIGHT)
    if (x < minX) minX = x
    if (y - titleH < minY) minY = y - titleH // 标题画在 pos.y 之上 titleH 处
    if (x + w > maxX) maxX = x + w
    if (y + h > maxY) maxY = y + h
  }
  const contentW = Math.max(1, maxX - minX)
  const contentH = Math.max(1, maxY - minY)
  const pad = padding * (liteGraphPixelRatio || 1)
  const minScale = liteGraphCanvas.ds.min_scale || LITEGRAPH_MIN_ZOOM
  const maxScale = liteGraphCanvas.ds.max_scale || LITEGRAPH_MAX_ZOOM
  let scale = Math.min((W - 2 * pad) / contentW, (H - 2 * pad) / contentH)
  scale = Math.max(minScale, Math.min(maxScale, scale))
  const centerX = minX + contentW / 2
  const centerY = minY + contentH / 2
  liteGraphCanvas.ds.scale = scale
  liteGraphCanvas.ds.offset = [(W * 0.5) / scale - centerX, (H * 0.5) / scale - centerY]
  liteGraphCanvas.setDirty(true, true)
}

// ---------------------------------------------------------------------------
// Pipeline → 静态 HTML 导出
// ---------------------------------------------------------------------------

function escHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function formatParamForHtmlExport(prop: NodeSpec['properties'][number], value: unknown): string {
  if (value === undefined || value === null || value === '') return ''
  if (prop.type === 'boolean') return Boolean(value) ? '是' : '否'
  if (prop.type === 'select') {
    const opt = prop.options?.find((o) => String(o.value) === String(value))
    return opt?.label ?? String(value)
  }
  if (prop.type === 'channel_list' || prop.type === 'event_select') {
    const arr = Array.isArray(value) ? (value as unknown[]) : []
    if (!arr.length) return ''
    const names = arr.map((v) =>
      typeof v === 'object' && v !== null ? ((v as { name?: string }).name ?? JSON.stringify(v)) : String(v),
    )
    if (names.length <= 4) return names.join(' / ')
    return `${names.slice(0, 3).join(' / ')} 等 ${names.length} 项`
  }
  if (prop.type === 'tags_input') {
    const arr = Array.isArray(value) ? (value as unknown[]) : []
    return arr.length ? arr.map(String).join(', ') : ''
  }
  if (prop.type === 'dataset_filter' || prop.type === 'dataset_ids') {
    if (Array.isArray(value) && (value as unknown[]).length) return `${(value as unknown[]).length} 项`
    return '按筛选条件'
  }
  if (prop.type === 'montage_picker') return String(value)
  if (prop.type === 'number' || prop.type === 'integer') {
    const n = Number(value)
    if (!Number.isFinite(n)) return String(value)
    return prop.type === 'integer' ? String(n) : String(parseFloat(n.toFixed(3)))
  }
  const s = String(value)
  return s.length > 120 ? `${s.slice(0, 120)}…` : s
}

function buildPipelineExportHtml(canvasDataUrl: string): string {
  const pl = currentPipeline.value
  const nodes = definition.value.graph.nodes
  const linkCount = (definition.value.graph.links as unknown[]).length
  const exportTime = new Date().toLocaleString('zh-CN', { hour12: false })

  const nodeCardsHtml = nodes
    .map((node, idx) => {
      const spec = nodeSpecs.value.find((s) => s.type === node.type) ?? null
      const params = (node.params ?? {}) as Record<string, unknown>
      const title = node.title || spec?.title || node.type
      const desc = spec?.description ?? ''

      const visibleProps = (spec?.properties ?? []).filter((p) => {
        if (p.advanced) return false
        if (p.type === 'text' || p.type === 'string') return false
        if (!p.visible_when) return true
        return Object.entries(p.visible_when as Record<string, unknown[]>).every(([k, allowed]) => {
          const v = params[k] ?? spec!.properties.find((pp) => pp.name === k)?.default
          return (allowed as unknown[]).map(String).includes(String(v ?? ''))
        })
      })

      const paramRows = visibleProps
        .map((p) => {
          const raw = params[p.name]
          const val = raw !== undefined && raw !== null && raw !== '' ? raw : p.default
          const display = formatParamForHtmlExport(p, val)
          if (!display) return ''
          const unitHtml = p.unit ? ` <span class="unit">${escHtml(p.unit)}</span>` : ''
          return `<tr><td class="param-label">${escHtml(p.label ?? p.name)}</td><td class="param-value">${escHtml(display)}${unitHtml}</td></tr>`
        })
        .filter(Boolean)
        .join('\n')

      return `
    <div class="node-card">
      <div class="node-header">
        <span class="node-index">${idx + 1}</span>
        <div class="node-title-wrap">
          <div class="node-title">${escHtml(title)}</div>
          ${desc ? `<div class="node-desc">${escHtml(desc)}</div>` : ''}
        </div>
        <div class="node-type">${escHtml(node.type)}</div>
      </div>
      ${paramRows ? `<table class="params-table"><tbody>${paramRows}</tbody></table>` : '<p class="no-params">无参数</p>'}
    </div>`
    })
    .join('\n')

  const canvasSection = canvasDataUrl
    ? `
  <section class="canvas-section">
    <h2 class="section-title">工作流图</h2>
    <div class="canvas-wrap">
      <img src="${canvasDataUrl}" alt="工作流图" class="canvas-img" />
    </div>
  </section>`
    : ''

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escHtml(pl?.name ?? '未命名工作流')} · Pipeline</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;background:#F0F4FA;color:#1A2B3C;font-size:14px;line-height:1.5}
.page{max-width:1100px;margin:0 auto;padding:36px 24px}
.page-header{background:linear-gradient(135deg,#1D3E6B 0%,#2B5EA7 100%);color:#fff;padding:28px 36px;border-radius:12px;margin-bottom:28px;box-shadow:0 4px 20px rgba(29,62,107,.2)}
.pipeline-name{font-size:26px;font-weight:700;letter-spacing:-.5px;margin-bottom:10px}
.pipeline-meta{display:flex;flex-wrap:wrap;font-size:13px;opacity:.78}
.pipeline-meta span{padding:0 14px;border-left:1px solid rgba(255,255,255,.3)}
.pipeline-meta span:first-child{padding-left:0;border-left:none}
.section-title{font-size:11px;font-weight:700;color:#768AA0;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #D6E4F7}
.canvas-section{margin-bottom:32px}
.canvas-wrap{background:#20293A;border-radius:10px;overflow:hidden;padding:8px;box-shadow:0 2px 12px rgba(0,0,0,.15)}
.canvas-img{width:100%;height:auto;display:block;border-radius:6px}
.nodes-section{margin-bottom:32px}
.node-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.node-card{background:#fff;border:1px solid #D6E4F7;border-radius:10px;overflow:hidden;box-shadow:0 1px 5px rgba(30,60,100,.07)}
.node-header{display:flex;align-items:flex-start;gap:12px;padding:12px 16px;border-bottom:1px solid #EEF3FB;background:#F7FAFF}
.node-index{flex-shrink:0;width:22px;height:22px;background:#3B6FB0;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;margin-top:2px}
.node-title-wrap{flex:1;min-width:0}
.node-title{font-size:13px;font-weight:600;color:#1A2B3C}
.node-desc{font-size:11px;color:#768AA0;margin-top:2px;line-height:1.4}
.node-type{font-size:10px;color:#A0B4C8;font-family:monospace;background:#EEF3FB;padding:2px 6px;border-radius:4px;white-space:nowrap;margin-top:3px;flex-shrink:0}
.params-table{width:100%;border-collapse:collapse}
.params-table tr+tr td{border-top:1px solid #F0F5FC}
.param-label{padding:7px 8px 7px 16px;font-size:12px;color:#768AA0;width:38%;vertical-align:middle}
.param-value{padding:7px 16px 7px 8px;font-size:12px;color:#1D3E6B;font-weight:500;vertical-align:middle;word-break:break-word}
.unit{font-size:11px;color:#3B6FB0;font-weight:400}
.no-params{padding:10px 16px;font-size:12px;color:#A0B4C8;font-style:italic}
.page-footer{text-align:center;font-size:11px;color:#A8BACE;padding-top:20px;border-top:1px solid #D6E4F7;margin-top:8px}
@media print{body{background:#fff}.page-header{background:#1D3E6B!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}.canvas-wrap{background:#20293A!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style>
</head>
<body>
<div class="page">
  <header class="page-header">
    <div class="pipeline-name">${escHtml(pl?.name ?? '未命名工作流')}</div>
    <div class="pipeline-meta">
      <span>版本 ${pl?.version ?? 1}</span>
      <span>${nodes.length} 节点</span>
      <span>${linkCount} 连线</span>
      <span>导出 ${exportTime}</span>
    </div>
  </header>
  ${canvasSection}
  <section class="nodes-section">
    <h2 class="section-title">节点参数明细</h2>
    <div class="node-grid">
      ${nodeCardsHtml}
    </div>
  </section>
  <footer class="page-footer">ELYS · 念析脑电分析平台 · Pipeline Export</footer>
</div>
</body>
</html>`
}

function exportPipelineHtml() {
  if (!liteGraph || !liteGraphCanvas) return

  const ds = liteGraphCanvas.ds as { scale: number; offset: [number, number] }
  const prevScale = ds.scale
  const prevOffset: [number, number] = [ds.offset[0], ds.offset[1]]

  fitGraphToView(32)
  ;(liteGraphCanvas as { draw?: (a: boolean, b: boolean) => void }).draw?.(true, true)
  const dataUrl = liteGraphCanvasEl.value?.toDataURL('image/png', 1.0) ?? ''

  ds.scale = prevScale
  ds.offset = prevOffset
  liteGraphCanvas.setDirty(true, true)

  const html = buildPipelineExportHtml(dataUrl)
  const safeName = (currentPipeline.value?.name ?? 'pipeline').replace(/[^\w一-鿿\-]/g, '_')
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `pipeline_${safeName}.html`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/** 自动排列：把全部节点按蛇形网格重排（依拓扑层深，连线最短），再适应屏幕。
 *  画布宽高比传给布局算法，让排出来的网格接近画布形状。markAsDirty 时标脏（用户主动整理才落库）。 */
function autoArrangeGraph(options: { markAsDirty?: boolean } = {}) {
  if (!liteGraph) return
  const nodes = definition.value.graph.nodes
  if (nodes.length === 0) return
  const W = liteGraphCanvasEl.value?.width || 0
  const H = liteGraphCanvasEl.value?.height || 0
  const aspect = W > 0 && H > 0 ? W / H : 1.7
  // 行列间距按节点「实际」最大宽高算（加了 widget 后节点变高，固定间距会上下重叠）；
  // 节点越高 → gapY 越大 → cols 越多、行数越少、换行回扫线越少。
  const titleH = LiteGraph.NODE_TITLE_HEIGHT || 30
  let maxW = NODE_CARD_WIDTH
  let maxH = NODE_CARD_MIN_HEIGHT
  for (const lgNode of liteGraphNodes(liteGraph)) {
    const size = (lgNode.size || []) as number[]
    maxW = Math.max(maxW, Number(size[0]) || 0)
    maxH = Math.max(maxH, (Number(size[1]) || 0) + titleH)
  }
  const layout = computeFlowLayout(nodes, definition.value.graph.links || [], {
    gapX: Math.round(maxW + 64),
    gapY: Math.round(maxH + 60),
    aspect,
  })
  for (const node of nodes) {
    const pos = layout.get(node.id)
    if (pos) node.position = pos
  }
  syncDefinitionToLiteGraph()
  if (options.markAsDirty) markDirty()
  fitGraphToView()
}

/** 判断当前布局是否「退化」：单行（脚本生成的一字长蛇阵）或单列（叠罗汉）。
 *  节点 < 4 个不折腾。坐标按 ~48px 量化分桶，容忍轻微抖动。 */
function graphLayoutIsDegenerate(): boolean {
  const nodes = definition.value.graph.nodes
  if (nodes.length < 4) return false
  const rows = new Set<number>()
  const cols = new Set<number>()
  for (const node of nodes) {
    rows.add(Math.round(Number(node.position?.[1] ?? 0) / 48))
    cols.add(Math.round(Number(node.position?.[0] ?? 0) / 48))
  }
  return rows.size <= 1 || cols.size <= 1
}

/** 加载工作流后整理视图：退化布局（脚本一字排开）自动整理（不标脏，保存时才落库），否则只适应屏幕。
 *  轮询到「画布真有尺寸」再适应：加载可能早于画布初始化 / 布局结算（右侧检查器抽屉此刻才展开、
 *  ResizeObserver 未结算、节点未首绘），此时 fitGraphToView 因画布宽高未就绪而空跑返回、视图停在
 *  默认 100% 装不下（用户反馈「点开好丑」）。故每帧重试，画布一拿到真实尺寸立刻适应；至多 ~0.8s 放弃，
 *  始终未就绪（如标签页未激活）则不强行适应，免得按最小尺寸算出错误缩放。 */
function normalizeGraphViewOnLoad() {
  if (!liteGraph || !liteGraphCanvas) return
  if (definition.value.graph.nodes.length === 0) return
  // 开「加载适应窗口」：随后 ~360ms 内每次 resize（含检查器抽屉 0.22s 过渡逐帧挤窄画布）都重新 fit。
  // 抽屉已开（无过渡）时，下面这次 rAF fit 即按稳定宽度一次到位；有过渡则靠窗口内 resize 逐帧重 fit 收敛。
  pendingFitOnLoad = true
  if (pendingFitClearTimer) window.clearTimeout(pendingFitClearTimer)
  pendingFitClearTimer = window.setTimeout(() => { pendingFitOnLoad = false }, 360)
  let tries = 0
  const attempt = () => {
    if (!liteGraph || !liteGraphCanvas) return
    if (definition.value.graph.nodes.length === 0) return
    const ready =
      (liteGraphCanvasEl.value?.width || 0) > 2 &&
      (liteGraphCanvasEl.value?.height || 0) > 2 &&
      (liteGraphShell.value?.clientWidth || 0) > 2
    if (!ready) {
      if (tries < 48) {
        tries += 1
        requestAnimationFrame(attempt)
      }
      return
    }
    if (graphLayoutIsDegenerate()) autoArrangeGraph({ markAsDirty: false })
    else fitGraphToView()
  }
  requestAnimationFrame(attempt)
}

function nextNodePosition(index: number): [number, number] {
  if (liteGraphCanvas?.visible_area) {
    const area = liteGraphCanvas.visible_area
    return [
      Number(area[0] || 0) + 72 + (index % 3) * NODE_GAP_X,
      Number(area[1] || 0) + 92 + Math.floor(index / 3) * NODE_GAP_Y,
    ]
  }
  return [80 + (index % 4) * NODE_GAP_X, 80 + Math.floor(index / 4) * NODE_GAP_Y]
}

function resizeLiteGraphCanvas() {
  if (!liteGraphShell.value || !liteGraphCanvasEl.value || !liteGraphCanvas) return
  const rect = liteGraphShell.value.getBoundingClientRect()
  const width = Math.max(640, Math.round(rect.width))
  const height = Math.max(420, Math.round(rect.height))
  const previousUiScale = getLiteGraphUiScale()
  liteGraphPixelRatio = getLiteGraphPixelRatio()
  const bitmapWidth = Math.max(1, Math.round(width * liteGraphPixelRatio))
  const bitmapHeight = Math.max(1, Math.round(height * liteGraphPixelRatio))
  liteGraphCanvasEl.value.width = bitmapWidth
  liteGraphCanvasEl.value.height = bitmapHeight
  liteGraphCanvasEl.value.style.width = `${width}px`
  liteGraphCanvasEl.value.style.height = `${height}px`
  liteGraphCanvasEl.value.style.imageRendering = 'auto'
  liteGraphCanvas.resize(bitmapWidth, bitmapHeight)
  liteGraphCanvas.ds.min_scale = LITEGRAPH_MIN_ZOOM * liteGraphPixelRatio
  liteGraphCanvas.ds.max_scale = LITEGRAPH_MAX_ZOOM * liteGraphPixelRatio
  // 加载适应窗口内（检查器抽屉过渡逐帧挤窄画布期间）按最新窄宽重新 fit，而非保留过渡前算出的过大缩放；
  // 窗口外（用户交互态）维持原逻辑：保留用户当前缩放，不打断手动缩放/平移。
  if (pendingFitOnLoad) {
    fitGraphToView() // 内部已 setDirty
  } else {
    liteGraphCanvas.ds.scale = clampLiteGraphUiScale(previousUiScale) * liteGraphPixelRatio
    liteGraphCanvas.setDirty(true, true)
  }
}

function getLiteGraphPixelRatio() {
  return Math.max(1, Math.min(window.devicePixelRatio || 1, LITEGRAPH_MAX_PIXEL_RATIO))
}

function getLiteGraphUiScale() {
  if (!liteGraphCanvas) return 1
  return clampLiteGraphUiScale((liteGraphCanvas.ds.scale || liteGraphPixelRatio) / Math.max(liteGraphPixelRatio, 1))
}

function clampLiteGraphUiScale(scale: number) {
  return Math.max(LITEGRAPH_MIN_ZOOM, Math.min(LITEGRAPH_MAX_ZOOM, scale || 1))
}

function bindHiDpiLiteGraphEvents(canvas: LGraphCanvas, canvasEl: HTMLCanvasElement) {
  const canvasWithEvents = canvas as LGraphCanvas & {
    processMouseDown: (event: MouseEvent) => unknown
    processMouseMove: (event: MouseEvent) => unknown
    processMouseUp: (event: MouseEvent) => unknown
    processMouseWheel: (event: WheelEvent) => unknown
    processDrop: (event: DragEvent) => unknown
    bindEvents: () => void
  }
  const toHiDpiEvent = <T extends MouseEvent>(event: T): T => {
    const ratio = liteGraphPixelRatio || 1
    if (ratio <= 1) return event

    const rect = canvasEl.getBoundingClientRect()
    const overrides = new Map<PropertyKey, unknown>()
    return new Proxy(event, {
      get(target, prop, receiver) {
        if (overrides.has(prop)) return overrides.get(prop)
        if (prop === LITEGRAPH_HIDPI_EVENT_PROP) return true
        if (prop === LITEGRAPH_ORIGINAL_CLIENT_X_PROP) return target.clientX
        if (prop === LITEGRAPH_ORIGINAL_CLIENT_Y_PROP) return target.clientY
        if (prop === 'clientX') return rect.left + (target.clientX - rect.left) * ratio
        if (prop === 'clientY') return rect.top + (target.clientY - rect.top) * ratio
        if (prop === 'offsetX') return Number(target.offsetX || target.clientX - rect.left) * ratio
        if (prop === 'offsetY') return Number(target.offsetY || target.clientY - rect.top) * ratio
        const value = Reflect.get(target, prop, target)
        return typeof value === 'function' ? value.bind(target) : value
      },
      set(_target, prop, value) {
        overrides.set(prop, value)
        return true
      },
    }) as T
  }

  const processMouseDown = canvasWithEvents.processMouseDown.bind(canvasWithEvents)
  const processMouseMove = canvasWithEvents.processMouseMove.bind(canvasWithEvents)
  const processMouseUp = canvasWithEvents.processMouseUp.bind(canvasWithEvents)
  const processMouseWheel = canvasWithEvents.processMouseWheel.bind(canvasWithEvents)
  const processDrop = canvasWithEvents.processDrop.bind(canvasWithEvents)

  canvasWithEvents.processMouseDown = (event) => {
    if (event.which !== 3 && event.button !== 2) closePipelineContextMenu()
    // LiteGraph uses pointer_is_down to detect two-finger touch (right-click emulation).
    // When mouseup fires outside the canvas the flag gets stuck, so the next left-click
    // is mis-detected as pointer_is_double=true and triggers the context menu.
    // Force-reset before every left-click to prevent the false positive.
    if (event.button === 0) {
      ;(canvasWithEvents as unknown as Record<string, unknown>).pointer_is_down = false
    }
    return processMouseDown(toHiDpiEvent(event))
  }
  canvasWithEvents.processMouseMove = (event) => processMouseMove(toHiDpiEvent(event))
  canvasWithEvents.processMouseUp = (event) => processMouseUp(toHiDpiEvent(event))
  canvasWithEvents.processMouseWheel = (event) => {
    closePipelineContextMenu()
    return processMouseWheel(toHiDpiEvent(event))
  }
  canvasWithEvents.processDrop = (event) => processDrop(toHiDpiEvent(event))
}

function showPipelineContextMenu(node: LiteGraphNode | null, event: LiteGraphContextEvent) {
  event.preventDefault()
  event.stopPropagation()
  syncDefinitionFromLiteGraph(false)

  const nodeId = getLiteGraphNodeId(node)
  if (nodeId) {
    selectedNodeId.value = nodeId
    selectLiteGraphNode(nodeId, { center: false })
  }

  const items: PipelineContextMenuItem[] = nodeId
    ? [
        { key: 'center-node', label: '居中查看' },
        { key: 'duplicate-node', label: '复制节点' },
        { key: 'disconnect-node', label: '断开全部连线', disabled: !nodeHasLinks(nodeId) },
        { key: 'delete-node', label: '删除节点', danger: true },
      ]
    : [
        { key: 'auto-arrange', label: '整理布局', disabled: definition.value.graph.nodes.length === 0 },
        { key: 'fit-view', label: '适应屏幕', disabled: definition.value.graph.nodes.length === 0 },
        { key: 'center-view', label: '居中视图', disabled: definition.value.graph.nodes.length === 0 },
        { key: 'reset-zoom', label: '缩放到 100%' },
        { key: 'add-load-data', label: '添加 LoadData 节点', disabled: !nodeSpecs.value.some((spec) => spec.type === LOAD_DATA_NODE_TYPE) },
      ]

  const point = pipelineContextMenuPoint(event, items.length)
  pipelineContextMenu.open = true
  pipelineContextMenu.x = point.x
  pipelineContextMenu.y = point.y
  pipelineContextMenu.nodeId = nodeId
  pipelineContextMenu.graphX = Number(event.canvasX || 0)
  pipelineContextMenu.graphY = Number(event.canvasY || 0)
  pipelineContextMenu.items = items
}

function pipelineContextMenuPoint(event: LiteGraphContextEvent, itemCount: number) {
  const shellRect = liteGraphShell.value?.getBoundingClientRect()
  const canvasRect = liteGraphCanvasEl.value?.getBoundingClientRect()
  if (!shellRect || !canvasRect) return { x: 12, y: 12 }

  const eventMeta = event as LiteGraphContextEvent & Record<string, unknown>
  const clientX =
    eventMeta[LITEGRAPH_HIDPI_EVENT_PROP] === true
      ? Number(eventMeta[LITEGRAPH_ORIGINAL_CLIENT_X_PROP] || event.clientX)
      : event.clientX
  const clientY =
    eventMeta[LITEGRAPH_HIDPI_EVENT_PROP] === true
      ? Number(eventMeta[LITEGRAPH_ORIGINAL_CLIENT_Y_PROP] || event.clientY)
      : event.clientY
  const menuWidth = 184
  const menuHeight = 14 + itemCount * 34
  const x = Math.max(8, Math.min(clientX - shellRect.left, shellRect.width - menuWidth - 8))
  const y = Math.max(8, Math.min(clientY - shellRect.top, shellRect.height - menuHeight - 8))
  return { x, y }
}

function closePipelineContextMenu() {
  if (!pipelineContextMenu.open) return
  pipelineContextMenu.open = false
  pipelineContextMenu.nodeId = ''
  pipelineContextMenu.items = []
}

function runPipelineContextAction(item: PipelineContextMenuItem) {
  if (item.disabled) return
  const nodeId = pipelineContextMenu.nodeId
  const graphPosition: [number, number] = [pipelineContextMenu.graphX, pipelineContextMenu.graphY]
  closePipelineContextMenu()

  switch (item.key) {
    case 'center-node':
      if (nodeId) centerLiteGraphNode(nodeId)
      break
    case 'duplicate-node':
      if (nodeId) duplicatePipelineNode(nodeId)
      break
    case 'disconnect-node':
      if (nodeId) disconnectNodeLinks(nodeId)
      break
    case 'delete-node':
      if (nodeId) deleteNodeById(nodeId)
      break
    case 'auto-arrange':
      autoArrangeGraph({ markAsDirty: true })
      break
    case 'fit-view':
      fitGraphToView()
      break
    case 'center-view':
      centerLiteGraphView()
      break
    case 'reset-zoom':
      resetLiteGraphZoom()
      break
    case 'add-load-data': {
      const spec = nodeSpecs.value.find((item) => item.type === LOAD_DATA_NODE_TYPE)
      if (spec) addNodeAt(spec, graphPosition)
      break
    }
  }
}

function nodeHasLinks(nodeId: string) {
  return definition.value.graph.links.some((link) => link.from.node === nodeId || link.to.node === nodeId)
}

function centerLiteGraphNode(nodeId: string) {
  if (!liteGraphCanvas) return
  const node = findLiteGraphNode(nodeId)
  if (!node) return
  liteGraphCanvas.centerOnNode(node)
  liteGraphCanvas.setDirty(true, true)
}

function duplicatePipelineNode(nodeId: string) {
  syncDefinitionFromLiteGraph(false)
  const source = definition.value.graph.nodes.find((node) => node.id === nodeId)
  if (!source) return
  const node: PipelineGraphNode = normalizeNode({
    ...source,
    id: `n_${Date.now().toString(36)}_${++nodeCounter}`,
    title: source.title,
    position: [Number(source.position?.[0] || 80) + 32, Number(source.position?.[1] || 80) + 32],
    params: clonePlainObject(source.params || {}),
    ui: clonePlainObject(source.ui || {}),
  })
  const graphNode = createLiteGraphNode(node)
  if (graphNode && liteGraph) {
    liteGraph.add(graphNode)
    selectedNodeId.value = node.id
    selectLiteGraphNode(node.id, { center: false })
    syncDefinitionFromLiteGraph(true)
    return
  }
  definition.value.graph.nodes.push(node)
  selectedNodeId.value = node.id
  syncDefinitionToLiteGraph()
  markDirty()
}

function disconnectNodeLinks(nodeId: string) {
  const graphNode = findLiteGraphNode(nodeId)
  if (graphNode) {
    for (let i = (graphNode.inputs?.length || 0) - 1; i >= 0; i -= 1) graphNode.disconnectInput(i)
    for (let i = (graphNode.outputs?.length || 0) - 1; i >= 0; i -= 1) graphNode.disconnectOutput(i)
    syncDefinitionFromLiteGraph(true)
    return
  }
  definition.value.graph.links = definition.value.graph.links.filter((link) => link.from.node !== nodeId && link.to.node !== nodeId)
  syncDefinitionToLiteGraph()
  markDirty()
}

function deleteNodeById(nodeId: string) {
  delete loadDataExecutionOverrides[nodeId]
  const graphNode = findLiteGraphNode(nodeId)
  if (graphNode && liteGraph) {
    liteGraph.remove(graphNode)
    selectedNodeId.value = definition.value.graph.nodes.find((node) => node.id !== nodeId)?.id || ''
    syncDefinitionFromLiteGraph(true)
    return
  }
  definition.value.graph.nodes = definition.value.graph.nodes.filter((node) => node.id !== nodeId)
  definition.value.graph.links = definition.value.graph.links.filter((link) => link.from.node !== nodeId && link.to.node !== nodeId)
  selectedNodeId.value = definition.value.graph.nodes[0]?.id || ''
  syncDefinitionToLiteGraph()
  markDirty()
}

// litegraph 节点类型注册 + ElysPipelineNode 自绘类 + graphNodeSize → composables/pipeline/useLiteGraphNodeTypes

// 节点 id 读写 getLiteGraphNodeId / setLiteGraphNodeId → composables/pipeline/litegraphUtils

function createLiteGraphNode(node: PipelineGraphNode) {
  registerLiteGraphNodeSpecs()
  const graphNode = LiteGraph.createNode<LiteGraphNode>(node.type)
  if (!graphNode) {
    statusMessage.value = `未知节点类型，无法创建画布节点: ${node.type}`
    return null
  }

  const spec = specForNode(node)
  const params = {
    ...(spec ? defaultParams(spec) : {}),
    ...clonePlainObject(node.params || {}),
  }
  graphNode.title = node.title || spec?.title || node.type
  graphNode.pos = [...(node.position || [80, 80])]
  graphNode.properties = params
  graphNode.size = spec ? graphNodeSize(spec) : [NODE_CARD_WIDTH, NODE_CARD_MIN_HEIGHT]
  graphNode.color = '#D4DDE8'
  graphNode.boxcolor = categoryColor(spec?.category)
  graphNode.bgcolor = '#FFFFFF'
  setLiteGraphNodeId(graphNode, node.id)
  applyLiteGraphNodeRunState(graphNode, node.id, spec)
  applyNodeWidgets(graphNode)
  return graphNode
}

function syncDefinitionToLiteGraph() {
  if (!liteGraph || !liteGraphCanvas) return
  registerLiteGraphNodeSpecs()
  syncingGraph = true
  liteGraph.clear()

  const graphNodes = new Map<string, LiteGraphNode>()
  for (const node of definition.value.graph.nodes.map(normalizeNode)) {
    const graphNode = createLiteGraphNode(node)
    if (!graphNode) continue
    liteGraph.add(graphNode)
    graphNodes.set(node.id, graphNode)
  }

  for (const link of definition.value.graph.links || []) {
    const from = graphNodes.get(link.from.node)
    const to = graphNodes.get(link.to.node)
    if (!from || !to) continue
    // 端口名失配时 findXxxSlot 返回 -1：直接跳过这条悬空连线。
    // 不能再用 Math.max(0,-1)→0 强连到 0 号槽 —— 那会塞一条畸形连线进图，
    // LiteGraph 之后遍历它就抛 'value' in null，连带卡死整个画布初始化和右键菜单。
    const outputSlot = from.findOutputSlot(link.from.port)
    const inputSlot = to.findInputSlot(link.to.port)
    if (outputSlot < 0 || inputSlot < 0) {
      console.warn('[pipeline] 跳过端口失配的悬空连线', link)
      continue
    }
    try {
      from.connect(outputSlot, to, inputSlot)
    } catch (error) {
      console.error('[pipeline] 连线失败，已跳过', link, error)
    }
  }

  if (selectedNodeId.value) selectLiteGraphNode(selectedNodeId.value)
  liteGraphCanvas.setDirty(true, true)
  syncingGraph = false
}

function scheduleLiteGraphSync(markAsDirty: boolean) {
  if (syncingGraph || pendingGraphSync) return
  pendingGraphSync = window.requestAnimationFrame(() => {
    pendingGraphSync = 0
    syncDefinitionFromLiteGraph(markAsDirty)
  })
}

function syncDefinitionFromLiteGraph(markAsDirty = true) {
  if (!liteGraph || syncingGraph) return

  const nodes = liteGraphNodes(liteGraph).map((node) => liteGraphNodeToDefinition(node))
  const links = liteGraphLinksToDefinition()
  definition.value = {
    ...definition.value,
    graph: { nodes, links },
  }
  if (selectedNodeId.value && !nodes.some((node) => node.id === selectedNodeId.value)) {
    selectedNodeId.value = nodes[0]?.id || ''
  }
  if (markAsDirty) markDirty()
}

function liteGraphNodeToDefinition(node: LiteGraphNode): PipelineGraphNode {
  const params = clonePlainObject(node.properties || {})
  delete params[LITEGRAPH_NODE_ID_PROP]
  const id = getLiteGraphNodeId(node) || `n_${node.id}`
  return normalizeNode({
    id,
    type: String(node.type || ''),
    title: node.title,
    position: [Number(node.pos?.[0] || 0), Number(node.pos?.[1] || 0)],
    params,
    ui: {},
  })
}

function liteGraphLinksToDefinition(): PipelineGraphLink[] {
  if (!liteGraph) return []
  const nodeByInternalId = new Map<number, LiteGraphNode>()
  for (const node of liteGraphNodes(liteGraph)) {
    nodeByInternalId.set(node.id, node)
  }

  return Object.values((liteGraph as LGraph & { links?: Record<string, LiteGraphLink> }).links || {})
    .map((link) => {
      const from = nodeByInternalId.get(link.origin_id)
      const to = nodeByInternalId.get(link.target_id)
      if (!from || !to) return null
      const fromPort = from.outputs?.[link.origin_slot]?.name || 'output'
      const toPort = to.inputs?.[link.target_slot]?.name || 'input'
      return {
        id: `l_${link.id ?? `${getLiteGraphNodeId(from)}_${link.origin_slot}_${getLiteGraphNodeId(to)}_${link.target_slot}`}`,
        from: { node: getLiteGraphNodeId(from), port: fromPort },
        to: { node: getLiteGraphNodeId(to), port: toPort },
      }
    })
    .filter((link): link is PipelineGraphLink => Boolean(link))
}

function selectLiteGraphNode(nodeId: string, options: { center?: boolean } = {}) {
  if (!liteGraph || !liteGraphCanvas) return
  const node = findLiteGraphNode(nodeId)
  if (!node) return
  liteGraphCanvas.deselectAllNodes()
  liteGraphCanvas.selectNode(node)
  if (options.center) liteGraphCanvas.centerOnNode(node)
  liteGraphCanvas.setDirty(true, true)
}

function findLiteGraphNode(nodeId: string) {
  if (!liteGraph) return null
  return liteGraphNodes(liteGraph).find((node) => getLiteGraphNodeId(node) === nodeId) || null
}

function updateLiteGraphNode(node: PipelineGraphNode) {
  const graphNode = findLiteGraphNode(node.id)
  if (!graphNode || !liteGraphCanvas) return
  graphNode.title = node.title || specForNode(node)?.title || node.type
  graphNode.properties = {
    ...clonePlainObject(node.params || {}),
    [LITEGRAPH_NODE_ID_PROP]: node.id,
  }
  graphNode.pos = [...(node.position || graphNode.pos || [80, 80])]
  applyLiteGraphNodeRunState(graphNode, node.id, specForNode(node))
  applyNodeWidgets(graphNode)
  liteGraphCanvas.setDirty(true, true)
}

// ===== 节点就地控件（widgets）：规划见 composables/pipeline/nodeWidgetPlan =====

/** 节点事实缓冲：push*Summary 把 1~N 条事实/行累积到节点上，finalizeNodeWidgets 再统一画成「参数面板」。 */
function nodeFactBuffer(graphNode: LiteGraphNode): ElysFact[] {
  const g = graphNode as { __elysFacts?: ElysFact[] }
  return g.__elysFacts || (g.__elysFacts = [])
}

/** 画面板内一行：事实=「标签(左灰) …… 值(右；数字醒目/单位弱化)」；行=左对齐单行(文件名/提示)。 */
function drawFactRow(
  ctx: CanvasRenderingContext2D,
  row: ElysFact,
  cy: number,
  leftX: number,
  rightX: number,
  valNum: string,
  valUnit: string,
) {
  ctx.textBaseline = 'middle'
  if (row.kind === 'line') {
    ctx.textAlign = 'left'
    if (row.tone === 'muted') {
      ctx.font = 'italic 11px "Segoe UI", Arial, sans-serif'
      ctx.fillStyle = '#9AAABB'
    } else if (row.tone === 'accent') {
      ctx.font = '11px "Segoe UI", Arial, sans-serif'
      ctx.fillStyle = NODE_WIDGET_SLIDER_COLOR
    } else {
      ctx.font = '500 12px "Segoe UI", Arial, sans-serif'
      ctx.fillStyle = '#2D3E52'
    }
    ctx.fillText(truncByWidth(ctx, row.text, rightX - leftX), leftX, cy)
    return
  }
  // 标签（左，浅灰 10px）
  ctx.font = '10px "Segoe UI", Arial, sans-serif'
  ctx.fillStyle = '#9AAABB'
  ctx.textAlign = 'left'
  const labelTxt = truncWidgetText(row.label, 10)
  ctx.fillText(labelTxt, leftX, cy)
  const labelEnd = leftX + ctx.measureText(labelTxt).width
  // 值（先按数字字重测宽截断 → 多段上色 → 整体右对齐）
  ctx.font = FACT_NUM_FONT
  const maxValW = Math.max(24, rightX - labelEnd - 10)
  const valTxt = truncByWidth(ctx, row.value, maxValW)
  const runs = factValueRuns(valTxt, valNum, valUnit)
  let cw = 0
  for (const r of runs) {
    ctx.font = r.font
    r.w = ctx.measureText(r.text).width
    cw += r.w
  }
  ctx.textAlign = 'left'
  let tx = Math.round(rightX - cw)
  for (const r of runs) {
    ctx.font = r.font
    ctx.fillStyle = r.fill
    ctx.fillText(r.text, tx, cy)
    tx += r.w
  }
}

/** 统一节点尺寸 + 画「参数面板」(D 方案)：标题 → 端口区 → 一块淡类别色面板(框住全部事实行) → 底部保存条留白。
 *  卡片高度取「固定统一高度 NODE_CARD_MIN_HEIGHT」与内容真实高度的较大者——短卡面板内补留白、一排齐平。
 *  面板 + 各行都在「单个自绘 widget」里画(不再逐行 widget)，高度按 litegraph「起点 +2、widget 后 +4」精确预留、不溢出。 */
function finalizeNodeWidgets(graphNode: LiteGraphNode, spec: NodeSpec | null) {
  const facts = nodeFactBuffer(graphNode)
  const portRows = Math.max(spec?.inputs?.length || 0, spec?.outputs?.length || 0, 1)
  const slotH = LiteGraph.NODE_SLOT_HEIGHT || 22
  const portsHeight = portRows * slotH
  const widgetsStartY = portsHeight + PANEL_GAP_TOP
  ;(graphNode as { widgets_start_y?: number }).widgets_start_y = widgetsStartY
  ;(graphNode as { widgets?: unknown[] }).widgets = []

  if (facts.length === 0) {
    graphNode.size = [NODE_CARD_WIDTH, Math.max(NODE_CARD_MIN_HEIGHT, widgetsStartY + 8)]
    return
  }

  const rowsContentH = facts.length * PANEL_ROW_H + PANEL_PAD_V * 2
  const naturalCardH = widgetsStartY + 2 + rowsContentH + PANEL_SAVE_RESERVE
  const cardH = Math.max(NODE_CARD_MIN_HEIGHT, naturalCardH)
  // 面板填到「卡底 − 保存条留白」，行多则卡变高、行少则面板内补留白（短卡仍达固定高、一排齐平）。
  const panelH = cardH - PANEL_SAVE_RESERVE - widgetsStartY - 2

  const accent = categoryColor(spec?.category)
  const panelTint = mixHex(accent, '#FFFFFF', 0.92) // 一缕类别淡底
  const panelStroke = mixHex(accent, '#FFFFFF', 0.74) // 极细类别边（无左竖线，克制）
  const valNum = mixHex(accent, '#000000', 0.2)
  const valUnit = mixHex(valNum, panelTint, 0.42)
  const rows = facts.slice()

  ;(graphNode as { widgets?: unknown[] }).widgets!.push({
    type: 'elys_fact_panel',
    name: '',
    value: null,
    computeSize: (w: number) => [w, panelH],
    draw: (ctx: CanvasRenderingContext2D, _node: unknown, w: number, y: number, _h: number) => {
      ctx.save()
      const px = PANEL_INSET_X
      const pw = w - PANEL_INSET_X * 2
      ctx.fillStyle = panelTint
      ctx.beginPath()
      ctx.roundRect(px, y, pw, panelH, PANEL_R)
      ctx.fill()
      ctx.strokeStyle = panelStroke
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.roundRect(px + 0.5, y + 0.5, pw - 1, panelH - 1, PANEL_R)
      ctx.stroke()
      const leftX = px + PANEL_PAD_L
      const rightX = px + pw - PANEL_PAD_R
      for (let i = 0; i < rows.length; i += 1) {
        drawFactRow(ctx, rows[i], y + PANEL_PAD_V + i * PANEL_ROW_H + PANEL_ROW_H / 2, leftX, rightX, valNum, valUnit)
      }
      ctx.restore()
    },
  } as unknown)

  graphNode.size = [NODE_CARD_WIDTH, cardH]
}

/** 文字截断（超长加省略号）—— 节点卡片窄，长中文 label / 值要截。 */
function truncWidgetText(text: string, max: number): string {
  const s = String(text ?? '')
  return s.length > max ? `${s.slice(0, max - 1)}…` : s
}

/** 数字去尾零（30.0→「30」、0.50→「0.5」）—— 只读事实自绘，能甩掉 litegraph 原生 toFixed 的尾零。 */
function trimNumberText(v: number): string {
  if (!Number.isFinite(v)) return String(v ?? '')
  return Number.isInteger(v) ? String(v) : String(parseFloat(v.toFixed(3)))
}

/** 一条 recording 的卡上文件名：优先 fif/source 路径 basename，否则退回 BIDS 式 sub-xxx_task。 */
function recordingDisplayName(rec: { fif_path?: string | null; source_path?: string | null; bids_subject_id?: string | null; subject_id?: string | null; task?: string | null } | undefined): string {
  if (!rec) return '(数据缺失)'
  const path = String(rec.fif_path || rec.source_path || '')
  const base = path ? path.split(/[\\/]/).pop() || '' : ''
  if (base) return base
  const subj = rec.bids_subject_id || rec.subject_id || '?'
  return `sub-${subj}${rec.task ? `_${rec.task}` : ''}`
}

/** 不透明 hex 线性插值（a→b 取 t∈[0,1]）。从类别强调色派生胶囊的描边/文字/单位色，
 *  比 withAlpha 的 rgba 更稳：与背景无关、HiDPI 下边缘干净（避免半透明叠色发糊）。 */
function mixHex(a: string, b: string, t: number): string {
  const parse = (hex: string) => {
    const s = hex.replace('#', '')
    return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)]
  }
  const [ca, cb] = [parse(a), parse(b)]
  const to2 = (x: number) => Math.round(Math.max(0, Math.min(255, x))).toString(16).padStart(2, '0')
  return '#' + [0, 1, 2].map((i) => to2(ca[i] * (1 - t) + cb[i] * t)).join('')
}

/** 把胶囊值切成「数字 / 运算符 / 单位」多段做双层排版——仅当 value 是「纯数值事实」
 *  （只由数字、运算符 →~±<>、空白、已知单位组成）时才拆；含字母 / 中文 / '/'（通道名 TP9、
 *  事件名 Stimulus/S 9、中文档位 带通）整体一段、不弱化。数字醒目、单位/运算符弱化且同色系。 */
function factValueRuns(value: string, textColor: string, mutedColor: string): FactRun[] {
  // 先剥掉已知单位再判字母：'dB'/'30 Hz' 的单位不算字母，但 'LOF'/'带通' 的字母/中文要拦住。
  const unitStripped = value.replace(/Hz|kHz|ms|µV|uV|dB|%|项|个|通道|s/g, '')
  const isNumericFact = /\d/.test(value) && !/[/A-Za-z一-鿿]/.test(unitStripped)
  if (!isNumericFact) return [{ text: value, font: FACT_CAT_FONT, fill: textColor, w: 0 }]

  const runs: FactRun[] = []
  const push = (text: string, font: string, fill: string) => {
    if (text) runs.push({ text, font, fill, w: 0 })
  }
  // 匹配 数字 / 运算符 / 空白；未匹配的间隙（Hz、s、项 等单位）归入弱化单位段。
  const re = /([+\-]?\d[\d.]*)|([→~±<>])|(\s+)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(value))) {
    if (m.index > last) push(value.slice(last, m.index), FACT_UNIT_FONT, mutedColor)
    if (m[1] !== undefined) push(m[1], FACT_NUM_FONT, textColor)
    else if (m[2] !== undefined) push(m[2], FACT_UNIT_FONT, mutedColor)
    else push(m[0], FACT_UNIT_FONT, mutedColor) // 空白：用单位字体测宽留白
    last = re.lastIndex
  }
  if (last < value.length) push(value.slice(last), FACT_UNIT_FONT, mutedColor)
  return runs
}

/** 按像素宽度截断文字（ctx 须已设好字体）—— 比字符数截断更准确，中文/数字/ASCII 混合时不溢出。 */
function truncByWidth(ctx: CanvasRenderingContext2D, text: string, maxPx: number): string {
  if (ctx.measureText(text).width <= maxPx) return text
  let s = text
  while (s.length > 1 && ctx.measureText(s + '…').width > maxPx) s = s.slice(0, -1)
  return s + '…'
}

/** 只读「标签 …… 值」事实：累积到节点事实缓冲，由 finalizeNodeWidgets 统一画进参数面板
 *  （面板内右对齐、数字醒目单位弱化，配色随节点类别在面板渲染时统一派生）。 */
function pushReadonlyFact(graphNode: LiteGraphNode, label: string, value: string) {
  nodeFactBuffer(graphNode).push({ kind: 'fact', label, value })
}

/** 只读单行（文件名 / 提示）：累积到事实缓冲，面板内左对齐绘制；muted=细灰斜体，accent=蓝提示，默认=深色文本。 */
function pushReadonlyLine(graphNode: LiteGraphNode, text: string, opts: { muted?: boolean; accent?: boolean }) {
  nodeFactBuffer(graphNode).push({ kind: 'line', text, tone: opts.muted ? 'muted' : opts.accent ? 'accent' : 'default' })
}

/** LoadData 专属只读摘要：选 1~2 个显文件名、更多显「N 个文件」、没选显「未选择数据」提示。 */
function pushLoadDataSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const rawIds = Array.isArray(params.dataset_ids) ? (params.dataset_ids as unknown[]).filter(Boolean) : []
  if (rawIds.length === 0) {
    pushReadonlyLine(graphNode, '未选择数据', { muted: true })
    pushReadonlyLine(graphNode, '点击设置 →', { accent: true })
    return
  }
  if (studyDatasets.value.length === 0) {
    // 数据集列表还没加载完 → 先显数量（watch 在列表到位后会重画显文件名），别误报「数据缺失」
    pushReadonlyLine(graphNode, `${rawIds.length} 个文件`, {})
    return
  }
  const byId = new Map(studyDatasets.value.map((r) => [String(r.id), r]))
  if (rawIds.length <= 3) {
    for (const id of rawIds) pushReadonlyLine(graphNode, recordingDisplayName(byId.get(String(id))), {})
  } else {
    for (const id of rawIds.slice(0, 2)) pushReadonlyLine(graphNode, recordingDisplayName(byId.get(String(id))), {})
    pushReadonlyLine(graphNode, `…还有 ${rawIds.length - 2} 个`, { muted: true })
  }
}

// ===== 节点专属摘要函数 =====

/** Filter：带通/高通/低通显范围，陷波显工频+谐波数。 */
function pushFilterSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const filterType = String(params.filter_type ?? 'bandpass')
  const TYPE_LABEL: Record<string, string> = { bandpass: '带通', highpass: '高通', lowpass: '低通', notch: '工频陷波' }
  const typeLabel = TYPE_LABEL[filterType] ?? filterType

  // 精简成一行：标签 = 滤波类型，值 = 频率范围 / 工频（谐波数等细节留检查器）。
  if (filterType === 'notch') {
    const freq = Number(params.notch_freq ?? 50)
    pushReadonlyFact(graphNode, typeLabel, `${trimNumberText(freq)} Hz`)
    return
  }
  const lf = params.l_freq != null ? Number(params.l_freq) : null
  const hf = params.h_freq != null ? Number(params.h_freq) : null
  let rangeText = ''
  if (filterType === 'bandpass' && lf != null && hf != null) rangeText = `${trimNumberText(lf)} → ${trimNumberText(hf)} Hz`
  else if (filterType === 'highpass' && lf != null) rangeText = `> ${trimNumberText(lf)} Hz`
  else if (filterType === 'lowpass' && hf != null) rangeText = `< ${trimNumberText(hf)} Hz`
  pushReadonlyFact(graphNode, typeLabel, rangeText || '—')
}

/** Bad Channels：处理 + 算法精简成一行「修复 · LOF」。 */
function pushBadChannelsSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const action = String(params.action ?? 'interpolate')
  const method = String(params.method ?? 'lof')
  pushReadonlyFact(graphNode, '坏道', `${action === 'interpolate' ? '修复' : '仅标记'} · ${method === 'lof' ? 'LOF' : 'RANSAC'}`)
}

/** 把 event_select / channel_list 值解析成名称字符串列表：对象取 .name，字符串直接用。 */
function resolveNameList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => {
      if (typeof item === 'string') return item
      if (item && typeof item === 'object' && 'name' in item) return String((item as { name: unknown }).name)
      return String(item)
    })
    .filter(Boolean)
}

/** Re-reference：显实际通道名，≤3 个全显，>3 前 2 + "+N"；空则提示未设置。 */
function pushRereferenceSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const channels = Array.isArray(params.ref_channels) ? (params.ref_channels as unknown[]).map(String).filter(Boolean) : []
  if (channels.length === 0) {
    pushReadonlyLine(graphNode, '未设置参考', { muted: true })
    return
  }
  if (channels.length === 1 && channels[0] === 'average') {
    pushReadonlyFact(graphNode, '参考', '共同平均')
    return
  }
  const MAX_SHOW = 3
  const display =
    channels.length <= MAX_SHOW
      ? channels.join(' / ')
      : `${channels.slice(0, 2).join(' / ')} +${channels.length - 2}`
  pushReadonlyFact(graphNode, '参考', display)
}

/** Epoch：显条件名（≤2 个全显，>2 折叠）+ 时窗范围。 */
function pushEpochSummary(graphNode: LiteGraphNode, params: Record<string, unknown>, spec: NodeSpec | null) {
  const condNames = resolveNameList(params.conditions)
  const tmin = params.tmin ?? spec?.properties.find((p) => p.name === 'tmin')?.default ?? -0.2
  const tmax = params.tmax ?? spec?.properties.find((p) => p.name === 'tmax')?.default ?? 1.0

  if (condNames.length > 0) {
    const condText =
      condNames.length <= 2 ? condNames.join(' · ') : `${condNames.slice(0, 2).join(' · ')} +${condNames.length - 2}`
    pushReadonlyFact(graphNode, '条件', condText)
  } else {
    pushReadonlyLine(graphNode, '未选条件', { muted: true })
  }
  pushReadonlyFact(graphNode, '时窗', `${trimNumberText(Number(tmin))} → ${trimNumberText(Number(tmax))} s`)
}

/** ERP Average：显条件名（同 Epoch，不显"2 项"）。 */
function pushErpSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const raw = params.condition
  const condNames = resolveNameList(Array.isArray(raw) ? raw : raw ? [raw] : [])
  if (condNames.length > 0) {
    const condText =
      condNames.length <= 2 ? condNames.join(' · ') : `${condNames.slice(0, 2).join(' · ')} +${condNames.length - 2}`
    pushReadonlyFact(graphNode, '条件', condText)
  } else {
    pushReadonlyLine(graphNode, '未选条件', { muted: true })
  }
}

/** ICA Compute：方法 + 成分数精简成一行「FastICA · 20」。 */
function pushIcaComputeSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const method = String(params.method ?? 'fastica')
  const METHOD_LABELS: Record<string, string> = { fastica: 'FastICA', infomax: 'Infomax', picard: 'Picard' }
  const n = params.n_components
  const nText = n != null && n !== '' ? String(n) : '自动'
  pushReadonlyFact(graphNode, 'ICA', `${METHOD_LABELS[method] ?? method} · ${nText}`)
}

/** ICA Apply：解析 excluded_components 文本→成分索引列表，空则提示待审阅。 */
function pushIcaApplySummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const raw = String(params.excluded_components ?? '').trim()
  if (!raw) {
    pushReadonlyLine(graphNode, '待审阅', { muted: true })
    return
  }
  const parts = raw.split(/[,\s]+/).filter(Boolean)
  const display =
    parts.length <= 5 ? parts.join(', ') : `${parts.slice(0, 4).join(', ')} +${parts.length - 4}`
  pushReadonlyFact(graphNode, '排除', display)
}

/** TFR：条件名 + 频率范围 + 基线模式。 */
function pushTfrSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const raw = params.condition
  const conds = resolveNameList(Array.isArray(raw) ? raw : raw ? [raw] : [])
  if (conds.length > 0) {
    const condText = conds.length <= 2 ? conds.join(' · ') : `${conds.slice(0, 2).join(' · ')} +${conds.length - 2}`
    pushReadonlyFact(graphNode, '条件', condText)
  }
  const fmin = params.fmin ?? 4
  const fmax = params.fmax ?? 40
  pushReadonlyFact(graphNode, '频率', `${trimNumberText(Number(fmin))} → ${trimNumberText(Number(fmax))} Hz`)
  // 基线模式（dB / % 变化 …）留检查器、不上卡（精简）。
}

/** PSD：条件名（可选）+ 频率范围 + 估计方法。 */
function pushPsdSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const raw = params.condition
  const conds = resolveNameList(Array.isArray(raw) ? raw : raw ? [raw] : [])
  if (conds.length > 0) {
    const condText = conds.length <= 2 ? conds.join(' · ') : `${conds.slice(0, 2).join(' · ')} +${conds.length - 2}`
    pushReadonlyFact(graphNode, '条件', condText)
  }
  const fmin = params.fmin ?? 1
  const fmax = params.fmax ?? 40
  pushReadonlyFact(graphNode, '频率', `${trimNumberText(Number(fmin))} → ${trimNumberText(Number(fmax))} Hz`)
  // 估计方法（Welch / Multitaper）留检查器、不上卡（精简）。
}

/** Channel Location：只显电极帽模板名，去掉 rename / on_missing 细节。 */
function pushChannelLocationSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const montage = String(params.montage ?? 'auto')
  const display = montage === 'auto' ? '自动' : montage === 'custom' ? '自定义' : montage
  pushReadonlyFact(graphNode, '电极帽', display)
}

/** ICLabel：处理方式(自动剔除/仅标注) + 置信度阈值 + 去除成分(5 个剔除开关折成一行的启用类别)。
 *  通用 planNodeWidgets 会把 5 个开关各占一行、还撞封顶 4 行漏掉「心电」并把 advanced 工频/坏道全藏掉——
 *  这里专属收成 3 行：医生一眼看清「删不删、删多确定、删哪几类」。 */
function pushIclabelSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const action = String(params.action ?? 'apply')
  pushReadonlyFact(graphNode, '处理方式', action === 'mark' ? '仅标注' : '自动剔除')

  const rawThr = params.prob_threshold
  const thr = rawThr != null && rawThr !== '' ? Number(rawThr) : 0.8
  pushReadonlyFact(graphNode, '置信度阈值', trimNumberText(thr))

  // 5 个剔除开关折成一行：列出启用的伪迹类别(默认全开 → 眼电/肌电/心电/工频/坏道)。
  const CATEGORIES: Array<[string, string]> = [
    ['remove_eye', '眼电'],
    ['remove_muscle', '肌电'],
    ['remove_heart', '心电'],
    ['remove_line_noise', '工频'],
    ['remove_channel_noise', '坏道'],
  ]
  const on = CATEGORIES.filter(([key]) => params[key] !== false).map(([, name]) => name)
  pushReadonlyFact(graphNode, '去除成分', on.length ? on.join('/') : '无')
}

/** Reject Trials：方法 + 阈值收成一行，仿 ICA Compute 的「方法 · 数」风格，避免整句选项标签搬上卡被截。 */
function pushRejectSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const method = String(params.method ?? 'threshold')
  if (method === 'autoreject') {
    pushReadonlyFact(graphNode, '剔除', 'AutoReject')
    return
  }
  const ptp = params.reject_peak_to_peak
  const ptpNum = ptp != null && ptp !== '' ? Number(ptp) : 150
  pushReadonlyFact(graphNode, '剔除', `阈值法 · ${trimNumberText(ptpNum)} µV`)
}

/** Baseline：把孤零零的「基线窗结束」点明成「起点 → X s」的窗范围（窗 = [epoch 起点, 此值]）。 */
function pushBaselineSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const raw = params.baseline_tmax
  const tmax = raw != null && raw !== '' ? Number(raw) : 0
  pushReadonlyFact(graphNode, '基线窗', `起点 → ${trimNumberText(tmax)} s`)
}

/** Grand Average PSD：无参数，补一行方法学说明避免空卡。 */
function pushGroupAverageSummary(graphNode: LiteGraphNode) {
  pushReadonlyFact(graphNode, '运算', '被试平均 ±SEM')
}

/** Group Merge：有组标签显标签，否则补一行说明（唯一参数是 string、通用渲染会跳过 → 否则空卡）。 */
function pushGroupMergeSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const label = String(params.label ?? '').trim()
  if (label) pushReadonlyFact(graphNode, '组标签', label)
  else pushReadonlyFact(graphNode, '合并', '多被试 PSD')
}

/** 数一个「标记字段」里有几项：优先按 JSON 数组(坏段 [{onset,…}])，否则按逗号/空白分隔(坏道名列表)。 */
function countMarkEntries(raw: unknown): number {
  if (typeof raw !== 'string') return Array.isArray(raw) ? raw.length : 0
  const s = raw.trim()
  if (!s) return 0
  try {
    const parsed = JSON.parse(s)
    if (Array.isArray(parsed)) return parsed.length
  } catch {
    /* 非 JSON，按分隔符数 */
  }
  return s.split(/[,\s]+/).filter(Boolean).length
}

/** Artifact Mark：显已标记的坏段 / 坏道计数（text 字段通用渲染会跳过 → 否则只剩啰嗦的处理方式一行）+ 坏道处理方式。 */
function pushArtifactMarkSummary(graphNode: LiteGraphNode, params: Record<string, unknown>) {
  const segCount = countMarkEntries(params.bad_segments)
  const chanCount = countMarkEntries(params.bad_channels)
  if (segCount === 0 && chanCount === 0) {
    pushReadonlyLine(graphNode, '待审核（双击打开）', { muted: true })
  } else {
    pushReadonlyFact(graphNode, '标记', `坏段 ${segCount} · 坏道 ${chanCount}`)
  }
  const action = String(params.channel_action ?? 'mark')
  pushReadonlyFact(graphNode, '坏道', action === 'interpolate' ? '插值修复' : '仅标记')
}

/** 只读事实的显示值：combo→中文档位、数字→去尾零+单位、开关→开/关。 */
function readonlyPlanValue(plan: NodeWidgetPlan, spec: NodeSpec): string {
  if (plan.kind === 'combo') return plan.value
  if (plan.kind === 'toggle') return plan.value ? '开' : '关'
  if (plan.kind === 'number' || plan.kind === 'slider') {
    const unit = spec.properties.find((p) => p.name === plan.name)?.unit
    return trimNumberText(plan.value) + (unit ? ` ${unit}` : '')
  }
  return ''
}

/** 重建节点就地内容：**纯只读展示，零交互**。点节点本身会选中 → 自动打开右侧检查器编辑。
 *  专属节点走各自的 push*Summary；其余走通用 planNodeWidgets → pushReadonlyFact。 */
function applyNodeWidgets(graphNode: LiteGraphNode) {
  if (!graphNode) return
  const nodeType = String((graphNode as { type?: unknown }).type || '')
  const spec = nodeSpecs.value.find((item) => item.type === nodeType) || null
  const params = (graphNode.properties || {}) as Record<string, unknown>
  ;(graphNode as { widgets?: unknown[] }).widgets = []
  ;(graphNode as { __elysFacts?: ElysFact[] }).__elysFacts = [] // 每次重建清空事实缓冲（push*Summary 重新累积）

  switch (nodeType) {
    case LOAD_DATA_NODE_TYPE:
      pushLoadDataSummary(graphNode, params)
      break
    case 'eeg/filter/apply':
      pushFilterSummary(graphNode, params)
      break
    case 'eeg/preproc/bad_channels':
      pushBadChannelsSummary(graphNode, params)
      break
    case 'eeg/preproc/rereference':
      pushRereferenceSummary(graphNode, params)
      break
    case EPOCH_NODE_TYPE:
      pushEpochSummary(graphNode, params, spec)
      break
    case ERP_NODE_TYPE:
      pushErpSummary(graphNode, params)
      break
    case 'eeg/ica/compute':
      pushIcaComputeSummary(graphNode, params)
      break
    case ICA_APPLY_NODE_TYPE:
      pushIcaApplySummary(graphNode, params)
      break
    case 'eeg/analysis/tfr':
      pushTfrSummary(graphNode, params)
      break
    case 'eeg/analysis/psd':
      pushPsdSummary(graphNode, params)
      break
    case 'eeg/preproc/channel_location':
      pushChannelLocationSummary(graphNode, params)
      break
    case 'eeg/ica/iclabel':
      pushIclabelSummary(graphNode, params)
      break
    case 'eeg/epoch/reject':
      pushRejectSummary(graphNode, params)
      break
    case 'eeg/epoch/baseline':
      pushBaselineSummary(graphNode, params)
      break
    case 'eeg/group/average':
      pushGroupAverageSummary(graphNode)
      break
    case 'eeg/group/merge':
      pushGroupMergeSummary(graphNode, params)
      break
    case 'eeg/preproc/artifact_mark':
      pushArtifactMarkSummary(graphNode, params)
      break
    default:
      if (spec) {
        for (const plan of planNodeWidgets(spec, params)) {
          const value = plan.kind === 'button' ? plan.summary : readonlyPlanValue(plan, spec)
          pushReadonlyFact(graphNode, plan.label, value)
        }
      }
  }

  finalizeNodeWidgets(graphNode, spec)
  liteGraphCanvas?.setDirty(true, true)
}

function clonePlainObject(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) return {}
  return JSON.parse(JSON.stringify(value)) as Record<string, unknown>
}

// LoadData 数据集加载 / 解析预览 / 事件标签拉取 → composables/pipeline/useLoadData

// ICA 成分人工剔除函数（load / toggle / submit / resume + 成分展示）见 composables/pipeline/useIcaInteraction

async function loadNodeSpecs() {
  loadingNodes.value = true
  nodeLoadError.value = ''
  try {
    const res = await pipelineApi.listNodeSpecs()
    nodeSpecs.value = res.data.nodes
    registerLiteGraphNodeSpecs()
    for (const spec of nodeSpecs.value) {
      if (!(spec.category in groupOpen)) groupOpen[spec.category] = true
    }
    syncDefinitionToLiteGraph()
  } catch (error) {
    nodeLoadError.value = describeError(error, '节点定义加载失败')
  } finally {
    loadingNodes.value = false
  }
}

async function loadPipelines(target: PipelineRouteTarget = {}) {
  resetRunTracking()
  selectedPipelineId.value = ''
  currentPipeline.value = null
  validation.value = null
  if (!selectedStudyId.value) {
    pipelines.value = []
    startNewPipeline(false)
    return
  }

  loadingPipelines.value = true
  try {
    const res = await pipelineApi.list(selectedStudyId.value)
    pipelines.value = res.data.pipelines
    const targetPipeline = target.pipelineId
      ? pipelines.value.find((item) => String(item.id) === target.pipelineId)
      : null
    const targetPipelineMissing = Boolean(target.pipelineId && !targetPipeline)
    if (targetPipeline) {
      loadPipelineIntoEditor(targetPipeline, target.executionId)
    } else if (pipelines.value[0]) {
      loadPipelineIntoEditor(pipelines.value[0])
      if (targetPipelineMissing) statusMessage.value = '未找到指定工作流，已显示最近工作流'
    } else {
      startNewPipeline(false)
      if (targetPipelineMissing) statusMessage.value = '未找到指定工作流，可先创建工作流'
    }
  } catch (error) {
    statusMessage.value = describeError(error, '工作流列表加载失败')
    startNewPipeline(false)
  } finally {
    loadingPipelines.value = false
  }
}

// 运行态核心函数（加载 / 轮询 / 刷新 / 重置）见 composables/pipeline/useRunExecution

function loadPipelineIntoEditor(pipeline: Pipeline, targetExecutionId = '') {
  currentPipeline.value = pipeline
  selectedPipelineId.value = String(pipeline.id)
  pipelineName.value = pipeline.name
  pipelineDescription.value = pipeline.description || ''
  definition.value = normalizeDefinition(pipeline.definition_json)
  clearAllLoadDataExecutionOverrides()
  pipelineEditLock.value = null
  pipelineEditLockError.value = ''
  selectedNodeId.value = definition.value.graph.nodes[0]?.id || ''
  validation.value = null
  dirty.value = false
  statusMessage.value = `已加载 ${pipeline.name}`
  syncDefinitionToLiteGraph()
  void loadPipelineExecutions(pipeline, targetExecutionId)
  // 最后尝试恢复未保存草稿（远程版本一致才恢复，否则跳过）
  tryRestoreDraft()
  // 整理视图：脚本生成的「一字长蛇阵」自动折成蛇形网格，其余只缩放到全部可见
  normalizeGraphViewOnLoad()
}

function startNewPipeline(markAsDirty = true) {
  resetRunTracking()
  currentPipeline.value = null
  selectedPipelineId.value = ''
  pipelineEditLock.value = null
  pipelineEditLockError.value = ''
  pipelineName.value = '未命名工作流'
  pipelineDescription.value = ''
  definition.value = createEmptyDefinition()
  clearAllLoadDataExecutionOverrides()
  selectedNodeId.value = ''
  validation.value = null
  statusMessage.value = '正在编辑新的工作流'
  dirty.value = markAsDirty
  syncDefinitionToLiteGraph()
  // 新建后尝试恢复"new"草稿（用户上次新建未保存就走了 → 切回页面恢复）
  tryRestoreDraft()
}

function normalizeDefinition(value: PipelineDefinitionPayload | null | undefined): PipelineDefinitionPayload {
  const base = createEmptyDefinition()
  if (!value) return base
  return {
    ...base,
    ...value,
    graph: {
      nodes: Array.isArray(value.graph?.nodes) ? value.graph.nodes.map(normalizeNode) : [],
      links: Array.isArray(value.graph?.links) ? value.graph.links : [],
    },
    settings: value.settings || base.settings,
  }
}

function normalizeNode(node: PipelineGraphNode): PipelineGraphNode {
  const normalized = {
    ...node,
    params: node.params || {},
    position: node.position || [80, 80],
  }
  if (normalized.type === LOAD_DATA_NODE_TYPE) ensureLoadDataParams(normalized)
  return normalized
}

function handlePipelineChange(event: Event) {
  const pipelineId = (event.target as HTMLSelectElement).value
  const pipeline = pipelines.value.find((item) => String(item.id) === pipelineId)
  if (pipeline) loadPipelineIntoEditor(pipeline)
  else startNewPipeline()
}

function addNode(spec: NodeSpec) {
  const index = definition.value.graph.nodes.length
  const node: PipelineGraphNode = {
    id: `n_${Date.now().toString(36)}_${++nodeCounter}`,
    type: spec.type,
    title: spec.title,
    position: nextNodePosition(index),
    params: defaultParams(spec),
    ui: {},
  }
  if (node.type === LOAD_DATA_NODE_TYPE) ensureLoadDataParams(node)
  if (liteGraph) {
    const graphNode = createLiteGraphNode(node)
    if (graphNode) {
      liteGraph.add(graphNode)
      selectedNodeId.value = node.id
      selectLiteGraphNode(node.id, { center: false })
      syncDefinitionFromLiteGraph(true)
      return
    }
  }
  definition.value.graph.nodes.push(node)
  selectedNodeId.value = node.id
  syncDefinitionToLiteGraph()
  markDirty()
}

function handleNodeDragStart(spec: NodeSpec, event: DragEvent) {
  draggedNodeType = spec.type
  event.dataTransfer?.setData('application/x-elys-node-type', spec.type)
  event.dataTransfer?.setData('text/plain', spec.type)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy'
}

function handleCanvasDrop(event: DragEvent) {
  const nodeType = event.dataTransfer?.getData('application/x-elys-node-type') || draggedNodeType
  const spec = nodeSpecs.value.find((item) => item.type === nodeType)
  draggedNodeType = ''
  if (!spec) return
  const rect = liteGraphCanvasEl.value?.getBoundingClientRect()
  const pos =
    liteGraphCanvas && rect
      ? liteGraphCanvas.convertCanvasToOffset([
          (event.clientX - rect.left) * liteGraphPixelRatio,
          (event.clientY - rect.top) * liteGraphPixelRatio,
        ])
      : [120, 120]
  addNodeAt(spec, [pos[0], pos[1]])
}

function addNodeAt(spec: NodeSpec, position: [number, number]) {
  const node: PipelineGraphNode = {
    id: `n_${Date.now().toString(36)}_${++nodeCounter}`,
    type: spec.type,
    title: spec.title,
    position,
    params: defaultParams(spec),
    ui: {},
  }
  if (node.type === LOAD_DATA_NODE_TYPE) ensureLoadDataParams(node)
  const graphNode = createLiteGraphNode(node)
  if (graphNode && liteGraph) {
    liteGraph.add(graphNode)
    selectedNodeId.value = node.id
    selectLiteGraphNode(node.id, { center: false })
    syncDefinitionFromLiteGraph(true)
  }
}

function defaultParams(spec: NodeSpec) {
  const params: Record<string, unknown> = {}
  for (const prop of spec.properties || []) {
    if (prop.default !== undefined) {
      params[prop.name] = cloneDefaultValue(prop.default)
    }
  }
  return params
}

function cloneDefaultValue(value: unknown) {
  if (value && typeof value === 'object') return JSON.parse(JSON.stringify(value))
  return value
}

// LoadData 参数规范化（ensureLoadDataParams / normalize* / same*）→ composables/pipeline/useLoadData

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

// LoadData 运行覆盖（buildRunSelectionOverridePayload 等）与 onLoadDataParamsUpdate → composables/pipeline/useLoadData

function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId
  selectLiteGraphNode(nodeId)
}

// 节点参数通用读写 formatParamValue/updateSelectedParam/coerceParamValue + 标题 handleNodeTitleInput → composables/pipeline/useNodeParamEditor

// 连接管理 selectedNodeInputLinks/connectableUpstreamCandidates/quickConnectUpstream/connectUpstreamToSelected/removeLink → composables/pipeline/useGraphConnections

function deleteSelectedNode() {
  if (!selectedNode.value) return
  deleteNodeById(selectedNode.value.id)
}

async function savePipeline() {
  if (!selectedStudyId.value || !pipelineName.value.trim()) return
  saving.value = true
  statusMessage.value = ''
  // 记录保存前的 draft key（可能是 'new' 或旧 pipeline_id），保存成功后清掉
  const previousStudyId = selectedStudyId.value
  const previousPipelineId = selectedPipelineId.value || 'new'
  try {
    const payload = {
      name: pipelineName.value.trim(),
      description: pipelineDescription.value.trim() || null,
      definition_json: buildDefinitionPayload(),
    }
    const res = currentPipeline.value
      ? await pipelineApi.update(selectedStudyId.value, currentPipeline.value.id, {
          ...payload,
          expected_version: currentPipeline.value.version,
        })
      : await pipelineApi.create(selectedStudyId.value, payload)
    upsertPipeline(res.data)
    // 清理保存前的 draft（避免旧 'new' draft 或同 id 旧 draft 残留）
    clearDraft(previousStudyId, previousPipelineId)
    // loadPipelineIntoEditor 会按新 id 再 tryRestoreDraft，但新 id 没 draft → 干净状态
    loadPipelineIntoEditor(res.data)
    statusMessage.value = '工作流已保存'
  } catch (error) {
    const httpStatus = (error as { response?: { status?: number } })?.response?.status
    if (httpStatus === 409 && currentPipeline.value) {
      // 乐观锁版本冲突：拉最新版本号刷新本地 expected_version，否则再点保存会一直发旧
      // 版本号、永远 409 死循环。只更新 version、不动画布（保留用户未保存的编辑），让用户
      // 确认后可重新保存（将覆盖远端最新版本）。
      try {
        const latest = await pipelineApi.get(selectedStudyId.value, currentPipeline.value.id)
        currentPipeline.value = { ...currentPipeline.value, version: latest.data.version }
        statusMessage.value = '此工作流已被其他人更新，已载入最新版本号；你的画布改动仍在，确认后可重新保存（将覆盖远端最新版本）。'
      } catch (refetchError) {
        statusMessage.value = describeError(error, '保存失败（版本冲突，刷新最新版本号也失败）')
      }
    } else {
      statusMessage.value = describeError(error, '保存失败')
    }
  } finally {
    saving.value = false
  }
}

async function validatePipeline() {
  if (!selectedStudyId.value) return
  if (dirty.value || !currentPipeline.value) {
    await savePipeline()
  }
  if (!currentPipeline.value) return
  try {
    const res = await pipelineApi.validate(selectedStudyId.value, currentPipeline.value.id)
    validation.value = res.data
    statusMessage.value = res.data.valid ? '校验通过，可以进入后续执行准备' : '校验发现问题'
  } catch (error) {
    statusMessage.value = describeError(error, '校验失败')
  }
}

// 运行控制函数（run / cancel / retry / dialog）见 composables/pipeline/useRunControl


// 产物管理函数（改名 / 标签 / 保留 / 下载 / 清理）见 composables/pipeline/useArtifactActions

function buildDefinitionPayload(): PipelineDefinitionPayload {
  syncDefinitionFromLiteGraph(false)
  return {
    ...definition.value,
    engine_version: LITEGRAPH_ENGINE_INFO.version,
    name: pipelineName.value.trim(),
    description: pipelineDescription.value.trim() || null,
    graph: {
      nodes: definition.value.graph.nodes.map(normalizeNode),
      links: definition.value.graph.links,
    },
    settings: {
      ...(definition.value.settings || {}),
      visual_editor: LITEGRAPH_ENGINE_INFO,
      litegraph: liteGraph?.serialize() || null,
    },
  }
}

// 产物状态文案 / 下载文件名（artifactActionStatusText / artifactDownloadName）见 composables/pipeline/useArtifactActions

function manifestArrayCount(key: string) {
  const value = activeExecutionManifest.value?.[key]
  if (Array.isArray(value)) return value.length
  if (isRecord(value)) return Object.keys(value).length
  return 0
}

function upsertPipeline(pipeline: Pipeline) {
  const index = pipelines.value.findIndex((item) => item.id === pipeline.id)
  if (index >= 0) pipelines.value[index] = pipeline
  else pipelines.value.unshift(pipeline)
}

function markDirty() {
  if (!hydrating.value) {
    dirty.value = true
    scheduleDraftSave()
  }
  validation.value = null
}

function describeError(error: unknown, fallback: string) {
  const maybeAxios = error as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = maybeAxios.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (isRecord(detail)) {
    const base = String(detail.message || detail.code || fallback)

    // 422 校验错误:展开 errors 数组,让用户看到具体哪个节点哪一项不通过
    const issues = Array.isArray(detail.errors)
      ? detail.errors
      : Array.isArray(detail.issues)
        ? detail.issues
        : []
    if (issues.length) {
      const summary = issues
        .slice(0, 5)
        .map((item) => {
          if (!isRecord(item)) return String(item)
          const node = item.node_id || item.node || item.target || ''
          const msg = item.message || item.detail || item.code || '校验失败'
          return node ? `「${node}」${msg}` : String(msg)
        })
        .join('；')
      const suffix = issues.length > 5 ? ` 等 ${issues.length} 项` : ''
      return `${base} → ${summary}${suffix}`
    }

    // 依赖阻塞类错误(原来的逻辑保留)
    const blockers = Array.isArray(detail.dependencies)
      ? detail.dependencies
      : Array.isArray(detail.blockers)
        ? detail.blockers
        : Array.isArray(detail.dependency_blockers)
          ? detail.dependency_blockers
          : []
    if (!blockers.length) return base
    const summary = blockers
      .slice(0, 3)
      .map((item) => {
        if (!isRecord(item)) return String(item)
        return String(item.execution_id || item.pipeline_execution_id || item.study_output_id || item.upstream_dataset_id || item.artifact_id || item.resource_id || item.id || item.kind || 'dependency')
      })
      .join('、')
    return `${base}；存在下游依赖阻塞：${summary}${blockers.length > 3 ? ` 等 ${blockers.length} 项` : ''}`
  }
  return maybeAxios.message || fallback
}
</script>

<style scoped>
:deep(.page) {
  padding: 0;
  overflow: hidden;
}

.pipeline-page {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
  background: var(--c-bg-soft);
  color: var(--c-text);
  overflow: hidden;
}

.library,
.inspector {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--c-surface);
  border-color: var(--c-border);
  overflow: auto;
  transform: translateX(0);
  transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

.library {
  left: 0;
  z-index: 20;
  padding: 12px;
  border-right: 1px solid var(--c-border);
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.04);
  min-width: 180px;
  max-width: 400px;
}

.library.is-hidden {
  transform: translateX(-100%);
  box-shadow: none;
  pointer-events: none;
}

.inspector {
  right: 0;
  z-index: 30;
  padding: 0;
  border-left: 1px solid var(--c-border);
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.04);
  min-width: 320px;
  max-width: 800px;
  overflow: visible; /* 允许内部手柄向左溢出至画布缝处 */
}

.inspector-inner {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  min-height: 0;
}

.inspector.is-hidden {
  transform: translateX(100%);
  box-shadow: none;
  pointer-events: none;
}

/* 抽屉拖拽手柄:抽屉外、跨在缝上的兄弟元素,left/right 由模板按抽屉宽度内联绑定。
   不再是抽屉子元素,故不被抽屉 overflow:auto 裁剪、也不和抽屉滚动条争点击;
   手柄一半盖在画布上(那侧永远没滚动条),命中区稳定、且加宽到 14px 更好抓。 */
.drawer-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 14px;
  cursor: ew-resize;
  background: transparent;
  z-index: 45;
  transition: background 0.15s;
}

.drawer-handle--seam-left {
  /* 配合 :style="{ left: libraryWidth }" —— 横跨左侧节点库的右缝 */
  transform: translateX(-50%);
}

.drawer-handle--seam-right {
  /* 手柄在 inspector 内部，left: -7px 使中心骑在 inspector 左缝；不依赖外部 right 绑定 */
  left: -7px;
}

.drawer-handle::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 2px;
  height: 28px;
  background: var(--c-text-3);
  border-radius: 1px;
  opacity: 0.45;
  transition: all 0.15s;
}

.drawer-handle:hover {
  background: rgba(47, 95, 143, 0.08);
}

.drawer-handle:hover::after,
.drawer-handle.is-dragging::after {
  opacity: 1;
  background: var(--c-primary);
  height: 56px;
  width: 3px;
}

.drawer-handle.is-dragging {
  background: rgba(47, 95, 143, 0.15);
}

/* 工具栏切换按钮 */
.toolbar-toggle {
  width: 32px;
  height: 32px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.18s cubic-bezier(0.4, 0, 0.2, 1),
              color 0.18s cubic-bezier(0.4, 0, 0.2, 1),
              border-color 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}

.toolbar-toggle.is-active {
  background: var(--c-primary-soft, rgba(47, 95, 143, 0.12));
  color: var(--c-primary);
  border-color: var(--c-primary);
}

.toolbar-toggle svg {
  display: block;
  transition: opacity 0.18s;
}

.toolbar-toggle:hover svg {
  opacity: 0.85;
}

/* Inspector 头部按钮 */
.inspector-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.inspector-header-btn {
  width: 22px;
  height: 22px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--c-text-2);
  padding: 0;
  transition: all 0.15s ease;
  font-size: 12px;
  color: var(--c-text-3);
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}

.inspector-header-btn:hover {
  background: var(--c-bg-tint);
  color: var(--c-text);
  border-color: var(--c-border);
}

.inspector-header-btn.is-active {
  background: var(--c-primary-soft, rgba(47, 95, 143, 0.12));
  color: var(--c-primary);
  border-color: var(--c-primary);
  transform: rotate(-12deg);
}

.inspector-header-btn.is-active:hover {
  transform: rotate(-15deg) scale(1.05);
}

.inspector-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--c-text-3);
  padding: 40px 20px;
  text-align: center;
  gap: 6px;
}
.inspector-empty-icon {
  margin-bottom: 8px;
  color: var(--c-text-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.inspector-empty-title {
  font-size: 13px;
  color: var(--c-text-2);
  font-weight: 500;
}
.inspector-empty-hint {
  font-size: 12px;
  color: var(--c-text-3);
  line-height: 1.5;
}
.inspector-empty-kbd {
  margin-top: 12px;
  font-size: 11px;
  color: var(--c-text-3);
  opacity: 0.7;
}
.inspector-empty-kbd .kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 1px 6px;
  border: 1px solid var(--c-border);
  border-radius: 3px;
  background: var(--c-bg-tint);
  font-family: var(--ff-mono, "Consolas", monospace);
  vertical-align: middle;
  min-height: 16px;
  font-size: 10px;
  margin: 0 2px;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel--fill {
  min-height: 0;
  flex: 1;
}

.panel__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--c-text-2);
}

.panel__title--tight {
  margin-top: 4px;
}

/* 节点名称作为面板主标题：透明背景输入框，hover/focus 时显示边框 */
.panel__title--node {
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--c-border);
}

.panel__title-input {
  flex: 1;
  min-width: 0;
  border: 1px solid transparent;
  background: transparent;
  color: var(--c-text);
  font-size: 13px;
  font-weight: 700;
  padding: 4px 6px;
  border-radius: 4px;
  outline: none;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.panel__title-input:hover {
  background: var(--c-bg-tint);
}

.panel__title-input:focus {
  background: var(--c-bg-tint);
  border-color: var(--c-border);
}

.panel__title-input::placeholder {
  color: var(--c-text-3);
  font-weight: 500;
}

.node-detail--subtitle {
  margin-top: -4px;
  margin-bottom: 6px;
}

.node-detail--subtitle small {
  color: var(--c-text-3);
  font-size: 11px;
  line-height: 1.4;
}

.node-detail--subtitle small strong {
  color: var(--c-text-2);
  font-weight: 600;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
  color: var(--c-text-2);
}

.field small,
.help-text {
  color: var(--c-text-3);
  line-height: 1.45;
}

.control,
.name-input,
.search input {
  width: 100%;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-tint);
  color: var(--c-text);
  font: inherit;
  outline: none;
}

.control {
  min-height: 32px;
  padding: 6px 8px;
}

.textarea {
  resize: vertical;
  min-height: 72px;
}

.checkbox {
  width: 16px;
  height: 16px;
}

.search {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-tint);
  padding: 0 8px;
}

.search input {
  min-height: 32px;
  padding: 0;
  border: 0;
  background: transparent;
}

.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-surface);
  color: var(--c-text);
  font-size: 12px;
  cursor: pointer;
}

.button:hover:not(:disabled) {
  border-color: var(--c-primary);
  color: var(--c-primary);
}

.button--primary {
  border-color: var(--c-primary);
  background: var(--c-primary);
  color: white;
}

.button--primary:hover:not(:disabled) {
  border-color: var(--c-primary-hover);
  background: var(--c-primary-hover);
  color: white;
}

.button--subtle {
  background: var(--c-surface);
  color: var(--c-text-2);
}

.button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.button--full {
  width: 100%;
}

.button--danger:hover:not(:disabled) {
  border-color: var(--c-danger);
  color: var(--c-danger);
}

.node-groups {
  overflow: auto;
  min-height: 0;
}

.node-group {
  border-top: 1px solid var(--c-border);
}

.group-head {
  width: 100%;
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  padding: 9px 0;
  color: var(--c-text);
  text-align: left;
  cursor: pointer;
}

.group-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.group-head small {
  color: var(--c-text-3);
  font-family: var(--ff-mono);
}

.group-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-bottom: 10px;
}

.node-template {
  display: flex;
  flex-direction: column;
  gap: 3px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-tint);
  padding: 8px;
  text-align: left;
  cursor: grab;
}

.node-template:active {
  cursor: grabbing;
}

.node-template:hover {
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}

.node-template__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-text);
}

.node-template__desc {
  font-size: 11px;
  line-height: 1.4;
  color: var(--c-text-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.editor {
  flex: 1;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
  padding-left: 240px;
  padding-right: 0;
  transition: padding-left 0.22s cubic-bezier(0.4, 0, 0.2, 1),
              padding-right 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

.toolbar {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 14px 10px;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-surface);
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-row--context {
  flex-wrap: nowrap;
}

.toolbar-row--actions {
  justify-content: space-between;
}

.toolbar-select {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--c-text-2);
}

.toolbar-select span {
  color: var(--c-text-3);
}

.toolbar-select select {
  height: 28px;
  min-width: 140px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  padding: 0 8px;
  font-size: 12px;
  background: var(--c-surface);
  color: var(--c-text);
}

.toolbar-select select:disabled {
  background: var(--c-bg-tint);
  color: var(--c-text-3);
}

.workflow-name,
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.workflow-name {
  min-width: 0;
  flex: 1;
}

.caret {
  margin-left: 4px;
  font-size: 10px;
  opacity: 0.7;
}

/* Run 抽屉 — 覆盖在 inspector 之上 */
.run-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  border-left: 1px solid var(--c-border);
  background: var(--c-surface);
  padding: 0 14px 14px;
  width: 420px;
  max-width: 90vw;
  overflow-y: auto;
  box-shadow: -8px 0 16px rgba(15, 23, 42, 0.08);
  z-index: 20;
  animation: run-drawer-slide 0.18s ease-out;
}

@keyframes run-drawer-slide {
  from {
    transform: translateX(20px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.run-drawer__head {
  position: sticky;
  top: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0 8px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  margin-bottom: 8px;
  z-index: 1;
}

.run-drawer__head strong {
  flex: 1;
  font-size: 14px;
}

.run-drawer .run-detail-panel {
  border: 0;
  padding: 0;
}

/* Chip 多选 (Epoch event_select 等节点参数还在用) */
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.chip-row--selected {
  padding: 4px;
  border-radius: 6px;
  background: rgba(47, 95, 143, 0.06);
}

.chip-row--pool {
  margin-top: 2px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.chip-row--pool .chip {
  width: 100%;
  justify-content: space-between;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--c-border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  line-height: 1.3;
  background: var(--c-surface);
  color: var(--c-text-2);
  cursor: pointer;
  transition: all 0.08s ease;
  user-select: none;
}

.chip:hover {
  border-color: var(--c-primary);
  color: var(--c-primary);
}

.chip.chip--active {
  background: var(--c-primary);
  border-color: var(--c-primary);
  color: #fff;
}

.chip.chip--active:hover {
  background: #244a72;
  border-color: #244a72;
  color: #fff;
}

.chip__remove {
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  opacity: 0.75;
}

.chip--more {
  font-weight: 700;
  color: var(--c-primary);
  border-style: dashed;
}

/* 只读自动标签（spec 提供的 auto_tags / dynamic_tags） */
.chip-row--readonly {
  background: transparent;
  padding: 2px 0;
}

.chip.chip--readonly {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.25);
  color: var(--c-text-2);
  cursor: default;
  font-family: var(--mono-font, ui-monospace, SFMono-Regular, Menlo, monospace);
}

.chip.chip--readonly:hover {
  border-color: rgba(99, 102, 241, 0.4);
  color: var(--c-text-2);
}

/* === 保存设置折叠区（P4）=== */
.save-settings {
  margin-top: 8px;
  padding: 6px 8px 8px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-surface);
}

.save-settings__head {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  font-weight: 700;
  color: var(--c-text-2);
  padding: 2px 0;
  list-style: none;
}

.save-settings__head::-webkit-details-marker {
  display: none;
}

.save-settings__head::before {
  content: '▶';
  font-size: 9px;
  color: var(--c-text-3);
  transition: transform 0.15s ease;
}

.save-settings[open] > .save-settings__head::before {
  transform: rotate(90deg);
}

.save-settings__icon {
  color: var(--c-text-2);
  flex-shrink: 0;
}

.save-settings__title {
  flex: 1;
}

.save-settings__keep {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text);
  white-space: nowrap;
  cursor: pointer;
}
.save-settings__keep input {
  cursor: pointer;
}
.save-settings__keep input:disabled {
  cursor: not-allowed;
}

.save-settings__hint {
  font-size: 10px;
  color: var(--c-text-3);
  white-space: nowrap;
}

.save-settings__meta-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-3);
  margin-top: 2px;
}

.save-settings__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--c-border);
}

.save-settings__preview {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(47, 95, 143, 0.08);
  color: var(--c-text);
  font-family: var(--mono-font, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 11px;
  word-break: break-all;
}

.save-settings__tags {
  gap: 6px;
}

.save-settings__meta {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 12px;
  margin-top: 4px;
  padding: 6px 8px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.02);
  font-size: 11px;
  color: var(--c-text-3);
}

.save-settings__meta > div {
  display: contents;
}

.save-settings__meta span {
  color: var(--c-text-3);
}

.save-settings__meta code {
  color: var(--c-text-2);
  font-family: var(--mono-font, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 11px;
}

.help-text--inline {
  display: inline;
  margin-left: 4px;
  font-weight: 400;
  color: var(--c-text-3);
}

.chip-search {
  margin: 2px 0;
}

.chip-search input {
  width: 100%;
  height: 26px;
  border: 1px solid var(--c-border);
  border-radius: 4px;
  padding: 0 8px;
  font-size: 12px;
  background: var(--c-surface);
}

/* Event select 节点参数 */
.event-select {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-surface);
}

.event-select__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.event-select__head > span:first-child {
  font-weight: 700;
  font-size: 12px;
  color: var(--c-text);
}

.event-select__head small {
  color: var(--c-text-3);
  font-size: 11px;
  margin-right: 6px;
}

.event-select__meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chip__count {
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
  color: inherit;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.4;
}

.chip--active .chip__count {
  background: rgba(255, 255, 255, 0.22);
}

.name-input {
  max-width: 360px;
  min-height: 32px;
  padding: 0 8px;
  font-weight: 700;
}

.badge {
  border-radius: 999px;
  border: 1px solid var(--c-border);
  padding: 2px 8px;
  font-size: 11px;
  color: var(--c-text-2);
}

.badge--warn {
  border-color: var(--c-warning);
  color: var(--c-warning);
  background: var(--c-warning-soft);
}

.canvas {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background-color: var(--c-bg-soft);
}

.litegraph-shell {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--c-bg-soft);
  box-shadow: inset 0 0 0 1px var(--c-border);
}

.litegraph-canvas {
  display: block;
  width: 100%;
  height: 100%;
  outline: none;
  image-rendering: auto;
  touch-action: none;
}

.pipeline-context-menu {
  position: absolute;
  z-index: 5;
  display: flex;
  flex-direction: column;
  width: 184px;
  padding: 6px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(14px);
}

.pipeline-context-menu__item {
  min-height: 32px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--c-text);
  font: 600 12px var(--ff-sans);
  text-align: left;
  cursor: pointer;
}

.pipeline-context-menu__item:hover:not(:disabled) {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.pipeline-context-menu__item.is-danger {
  color: var(--c-danger);
}

.pipeline-context-menu__item.is-danger:hover:not(:disabled) {
  background: rgba(255, 77, 79, 0.1);
}

.pipeline-context-menu__item:disabled {
  color: var(--c-text-3);
  cursor: not-allowed;
}

.canvas-overlay {
  position: absolute;
  top: 12px;
  right: 12px;
  left: 12px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  pointer-events: none;
}

.canvas-overlay__meta,
.canvas-overlay__actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(10px);
}

.canvas-overlay__meta {
  padding: 0 10px;
  color: var(--c-text-2);
  font-size: 12px;
}

.canvas-overlay__meta strong {
  color: var(--c-text);
}

.canvas-overlay__actions {
  padding: 3px;
  pointer-events: auto;
}

.canvas-tool {
  min-height: 24px;
  padding: 0 9px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--c-text-2);
  font-size: 12px;
  cursor: pointer;
}

.canvas-tool:hover {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.empty-canvas {
  position: absolute;
  left: 50%;
  top: 42%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: center;
  color: var(--c-text-2);
  pointer-events: none;
}

.empty-canvas strong {
  color: var(--c-text);
}

.status-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 74px;
  padding: 8px 14px;
  border-top: 1px solid var(--c-border);
  background: var(--c-surface);
  font-size: 12px;
}

.status-panel__summary,
.validation {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.validation .ok {
  color: var(--c-success);
  font-weight: 700;
}

.validation .warn {
  color: #9a6a28;
  font-weight: 700;
}

.validation .error,
.state-text--error {
  color: var(--c-danger);
}

.run-panel {
  display: grid;
  gap: 4px;
  max-height: 150px;
  overflow: auto;
  padding-top: 2px;
}

/* UI Phase (docs_v2/6-05) P1-2: 步骤进度条 */
.run-stepbar {
  margin-top: 6px;
  padding: 8px 4px;
  overflow-x: auto;
}
.run-stepbar__list {
  display: flex;
  align-items: center;
  list-style: none;
  margin: 0;
  padding: 0;
  gap: 0;
  min-width: max-content;
}
.run-stepbar__step {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0;
  flex-shrink: 0;
}
.run-stepbar__dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  border: 2px solid var(--c-border-2);
  background: var(--c-bg);
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 700;
  z-index: 1;
}
.run-stepbar__label {
  margin: 0 12px 0 6px;
  font-size: 12px;
  color: var(--c-text-2);
  white-space: nowrap;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.run-stepbar__connector {
  width: 22px;
  height: 2px;
  background: var(--c-border);
  margin-right: 6px;
}
.run-stepbar__connector.is-done {
  background: var(--c-success);
}
.run-stepbar__step.is-done .run-stepbar__dot {
  border-color: var(--c-success);
  background: var(--c-success);
  color: #fff;
}
.run-stepbar__step.is-doing .run-stepbar__dot {
  border-color: var(--c-info);
  background: var(--c-info-soft);
  color: var(--c-info);
  animation: stepbar-pulse 1.5s ease-in-out infinite;
}
.run-stepbar__step.is-failed .run-stepbar__dot {
  border-color: var(--c-danger);
  background: var(--c-danger);
  color: #fff;
}
.run-stepbar__step.is-waiting .run-stepbar__dot {
  border-color: var(--c-warning);
  background: var(--c-warning-soft);
  color: var(--c-warning);
}
.run-stepbar__step.is-skipped .run-stepbar__dot {
  border-color: var(--c-border-2);
  background: var(--c-bg-tint);
  color: var(--c-text-3);
}
@keyframes stepbar-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.run-panel-details {
  margin-top: 8px;
}
.run-panel-details summary {
  cursor: pointer;
  color: var(--c-text-3);
  font-size: 12px;
  padding: 4px 0;
  list-style: none;
}
.run-panel-details summary::-webkit-details-marker {
  display: none;
}

.run-node-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) auto auto auto minmax(0, 1.4fr);
  align-items: center;
  gap: 8px;
  min-height: 28px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-tint);
  padding: 4px 8px;
}

.run-node-row__title,
.run-node-row__error {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-node-row__title {
  font-weight: 700;
  color: var(--c-text);
}

.run-node-row__error {
  color: var(--c-danger);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 20px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.status-pill--success {
  border-color: rgba(47, 118, 111, 0.35);
  background: #f0f8f4;
  color: #2f766f;
}

.status-pill--failed {
  border-color: rgba(180, 35, 24, 0.32);
  background: #fff4f2;
  color: #b42318;
}

.status-pill--running {
  border-color: rgba(199, 131, 29, 0.35);
  background: #fff8e8;
  color: #9a6a28;
}

.status-pill--queued,
.status-pill--pending,
.status-pill--skipped,
.status-pill--canceled {
  background: #f8fafc;
  color: #687386;
}

.status-pill--cached {
  border-color: rgba(107, 95, 149, 0.35);
  background: #f5f1fa;
  color: #6b5f95;
}

.status-pill--pinned {
  border-color: rgba(180, 35, 24, 0.32);
  background: #fef0ea;
  color: #b42318;
}

.status-pill--current {
  border-color: rgba(47, 118, 111, 0.34);
  background: #e7f7ef;
  color: #1f6f63;
}

.status-pill--temporary {
  border-color: rgba(199, 131, 29, 0.35);
  background: #fff8e8;
  color: #9a6a28;
}

.status-pill--deleted {
  border-color: rgba(104, 115, 134, 0.36);
  background: #f3f4f7;
  color: #687386;
  text-decoration: line-through;
}

.status-pill--unknown {
  background: #f8fafc;
  color: #687386;
}

.status-pill--waiting_user_input {
  border-color: rgba(139, 92, 246, 0.35);
  background: #f5f1fa;
  color: #6b5f95;
}

/* 结果行（Run 抽屉 结果 tab） */
.derived-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-surface);
  padding: 8px 10px;
  margin-bottom: 8px;
}

.derived-row__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.derived-row__title {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
  background: transparent;
  border: 0;
  padding: 0;
  text-align: left;
  font: inherit;
  color: inherit;
  cursor: pointer;
}

.derived-row__title strong {
  color: var(--c-text);
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.derived-row__title strong:hover {
  text-decoration: underline;
}

.derived-row__rename {
  flex: 1;
  min-width: 120px;
  border: 1px solid var(--c-primary);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 13px;
  background: #fff;
}

.derived-row__type {
  font-size: 11px;
  color: var(--c-text-3);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.derived-row__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.derived-row__tag-input {
  border: 1px dashed var(--c-border);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  background: transparent;
  outline: none;
  min-width: 80px;
}

.derived-row__tag-input:focus {
  border-color: var(--c-primary);
  border-style: solid;
}

.derived-row__meta {
  color: var(--c-text-3);
  font-size: 11px;
}

.tags-input-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tags-input-field > span {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-2);
}

/* channel_list 多选 listbox（Re-reference 等节点用） */
.channel-list-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.channel-list__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.channel-list__head > span {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-2);
}

.channel-list__count {
  font-size: 11px;
  color: var(--c-text-3);
}

.channel-list__toolbar {
  display: flex;
  gap: 6px;
  align-items: center;
}

.channel-list__search {
  flex: 1;
  min-width: 0;
}

.channel-list__box {
  /* 不用 flex column —— max-height + overflow-y:auto 配合 flex 时会强制 shrink 子项，
     64 个 item 会被压扁到 4-8px 高度，文字看不见。用 block 流让 item 保持自然高度，
     超出容器再 scroll。 */
  display: block;
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid var(--c-border, #d4dde8);
  border-radius: 6px;
  background: #fff;
  outline: none;
  transition: box-shadow 0.18s, background 0.18s;
}

.channel-list__box:focus {
  box-shadow: inset 3px 0 0 #2f5f8f, 0 0 0 2px rgba(47, 95, 143, 0.12);
  background: linear-gradient(to right, rgba(47, 95, 143, 0.04), transparent 60%);
}

/* listbox 行：参考 LoadDataPanel .ldp-list-item 的风格 */
.channel-list__item {
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
  border-left: 3px solid transparent;
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--c-text-2);
  transition: background 0.12s;
}

.channel-list__item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.channel-list__item.is-selected {
  background: rgba(47, 95, 143, 0.16);
  color: #1f4e7a;
  border-left-color: #2f5f8f;
  font-weight: 500;
}

.channel-list__item.is-selected:hover {
  background: rgba(47, 95, 143, 0.22);
}

.channel-list__empty {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--c-text-3);
  font-style: italic;
}

.channel-list__hint {
  padding: 6px 10px;
  font-size: 11px;
  color: #2f5f8f;
  background: #eef4fa;
  border-radius: 4px;
  text-align: center;
}

.channel-list__shortcut-hint {
  font-size: 10.5px;
  color: var(--c-text-3);
  text-align: center;
  margin-top: -2px;
}

.state-text--warn {
  color: #9a6a28;
}

.state-text {
  font-size: 12px;
  color: var(--c-text-3);
  line-height: 1.5;
}

.state-text.state-text--error {
  color: var(--c-danger);
}

.state-text.state-text--warn {
  color: #9a6a28;
}

.node-detail {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-tint);
  padding: 8px;
}

.node-detail strong {
  font-size: 13px;
}

.node-detail small {
  color: var(--c-text-2);
  line-height: 1.45;
}

.node-run-summary {
  display: grid;
  gap: 8px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: #fff;
  padding: 8px;
}

.node-run-summary__head,
.node-run-summary__grid {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.node-run-summary__head strong {
  font-size: 13px;
}

.node-run-summary__grid {
  color: var(--c-text-3);
}

.node-run-summary__grid strong {
  color: var(--c-text);
}

/* 缓存命中调试信息（仅 DEV / ?debug 可见）：中性灰、等宽，刻意不用红色 error 样式 */
.node-run-summary__debug {
  font-family: var(--ff-mono, monospace);
  font-size: 11px;
  color: var(--c-text-3);
  word-break: break-all;
}

.artifact-list {
  display: grid;
  gap: 6px;
}

/* 多产物折叠汇总条：默认收起，点开看明细，避免对用户铺一长串技术文件名 */
.artifact-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 7px 9px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: #fff;
  color: var(--c-text);
  text-align: left;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.artifact-summary:hover {
  border-color: rgba(47, 95, 143, 0.38);
  background: #eef4fa;
}

.artifact-summary small {
  color: var(--c-text-3);
  font-weight: 400;
  white-space: nowrap;
}

.artifact-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  min-height: 46px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: #fff;
  padding: 7px 9px;
  color: var(--c-text);
  text-align: left;
  cursor: pointer;
}

.artifact-row:hover,
.artifact-row.is-active {
  border-color: rgba(47, 95, 143, 0.38);
  background: #eef4fa;
}

.artifact-row span,
.artifact-row small {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-row span {
  font-weight: 700;
}

.artifact-row small {
  color: var(--c-text-3);
}

.artifact-preview-panel {
  display: grid;
  gap: 8px;
  border: 1px solid rgba(47, 95, 143, 0.24);
  border-radius: 6px;
  background: #f8fbff;
  padding: 10px;
}

.artifact-preview-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.artifact-preview-panel__head strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: #fff;
  color: var(--c-text-2);
  cursor: pointer;
}

.icon-button:hover {
  border-color: rgba(47, 95, 143, 0.38);
  color: var(--c-primary);
}

.artifact-preview-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.artifact-preview-metrics div {
  min-width: 0;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 6px;
  background: #fff;
  padding: 6px;
}

.artifact-preview-metrics span,
.artifact-preview-metrics strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-preview-metrics span {
  color: var(--c-text-3);
}

.artifact-preview-events,
.artifact-preview-curves {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.artifact-preview-events span,
.artifact-preview-curves span {
  max-width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 999px;
  background: #fff;
  padding: 3px 7px;
  color: var(--c-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-preview-panel__link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  border: 1px solid rgba(47, 95, 143, 0.3);
  border-radius: 6px;
  background: #fff;
  color: var(--c-primary);
  font-weight: 700;
  text-decoration: none;
}

.artifact-preview-panel__link:hover {
  background: #eef4fa;
}

.ica-interaction-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid rgba(107, 95, 149, 0.28);
  border-radius: 6px;
  background: #fbfaff;
  padding: 10px;
}

.ica-interaction-panel__head,
.ica-interaction-panel__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ica-component-row {
  display: grid;
  grid-template-columns: 18px minmax(48px, 0.5fr) minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: #ffffff;
  padding: 6px 8px;
  font-size: 12px;
}

.ica-component-row small {
  min-width: 0;
  overflow: hidden;
  color: var(--c-text-3);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.connections {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
/* 参数面板:两列网格;普通字段整行,数字参数(field--half)半宽 → 两两并排一行 */
.property-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 8px;
  row-gap: 10px;
  align-items: start;
}
.property-list > * {
  grid-column: 1 / -1;
}
.property-list > .field--half {
  grid-column: auto;
}
/* 节点上复杂参数按钮点击 → 滚到对应字段并短暂高亮，引导视线 */
.param-flash {
  animation: param-flash 1.2s ease-out;
  border-radius: 8px;
}
@keyframes param-flash {
  0%, 30% { box-shadow: 0 0 0 2px rgba(59, 111, 176, 0.55); background: rgba(59, 111, 176, 0.08); }
  100% { box-shadow: 0 0 0 2px rgba(59, 111, 176, 0); background: transparent; }
}

/* litegraph 数字控件「点击输入数值」弹的原生 prompt 默认黑皮(#333/black)——覆盖成扁平浅色小框。
   它被 append 到画布容器内，故 :deep 能命中；litegraph.css 的 box-shadow 带 !important，这里也要 !important。 */
:deep(.graphdialog) {
  display: flex !important;
  align-items: center !important;
  gap: 6px !important;
  min-height: 0 !important;
  padding: 7px 9px !important;
  background-color: #fff !important;
  border: 1px solid #d4dde8 !important;
  border-radius: 10px !important;
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.16) !important;
  font-size: 13px !important;
  font-family: 'Segoe UI', system-ui, sans-serif !important;
  color: #1f2a37 !important;
}
:deep(.graphdialog .name) { display: none !important; } /* 隐藏冗余的 "Value" 英文标签 */
:deep(.graphdialog input.value),
:deep(.graphdialog textarea.value) {
  margin: 0 !important;
  min-height: 0 !important;
  background-color: #f1f5f9 !important;
  color: #1f2a37 !important;
  border: 1px solid #cbd5e1 !important;
  border-radius: 6px !important;
  padding: 4px 8px !important;
  font-size: 13px !important;
}
:deep(.graphdialog button.rounded) {
  margin: 0 !important;
  background-color: #3b6fb0 !important;
  color: #fff !important;
  border: 0 !important;
  border-radius: 6px !important;
  padding: 5px 12px !important;
  font-size: 12px !important;
  cursor: pointer !important;
}

.dataset-qa-cell {
  display: grid;
  gap: 4px;
  min-width: 150px;
}

.dataset-qa-cell__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.dataset-qa-cell small {
  max-width: 160px;
  color: var(--c-text-3);
}

.dataset-qa-cell small.is-danger {
  color: var(--c-danger);
  font-weight: 700;
}

.dataset-qa-status,
.dataset-qa-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 20px;
  border-radius: 999px;
  padding: 0 7px;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.dataset-qa-status {
  min-width: 66px;
  border: 1px solid var(--c-border);
  background: var(--c-bg-tint);
  color: var(--c-text-2);
}

.dataset-qa-status--converted {
  border-color: rgba(47, 95, 143, 0.24);
  background: #eef6ff;
  color: #2f5f8f;
}

.dataset-qa-status--checked {
  border-color: rgba(47, 118, 111, 0.44);
  background: #e7f7ef;
  color: #1f6f63;
  box-shadow: inset 0 0 0 1px rgba(47, 118, 111, 0.16);
}

.dataset-qa-status--failed,
.dataset-qa-status--rejected,
.dataset-qa-status--deleted {
  border-color: rgba(180, 35, 24, 0.32);
  background: #fff4f2;
  color: #b42318;
}

.dataset-qa-status--pending {
  border-color: rgba(199, 131, 29, 0.34);
  background: #fff8e8;
  color: #9a6a28;
}

.dataset-qa-status--unknown {
  background: #f8fafc;
  color: #687386;
}

.dataset-qa-tag {
  border: 1px solid rgba(199, 131, 29, 0.28);
  background: #fff8e8;
  color: #9a6a28;
}

.link-button {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--c-primary);
  font-size: 12px;
  cursor: pointer;
}

.link-button:disabled {
  color: var(--c-text-3);
  cursor: not-allowed;
}

.link-button:hover:not(:disabled) {
  text-decoration: underline;
}

/* [Dead code 已清理] 旧 LoadData chip UI 的 CSS (.load-filters / .load-result / .status-badge / .load-excluded / .load-row-detail 等) 已删除，新版样式见 LoadDataPanel.vue (scoped) */

.link-list button {
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-tint);
  color: var(--c-text-2);
  padding: 6px 8px;
  text-align: left;
  font-family: var(--ff-mono);
  font-size: 10px;
  cursor: pointer;
}

.link-list button:hover {
  border-color: var(--c-danger);
  color: var(--c-danger);
}

/* === 节点连接区（新版） === */
.connection-list,
.connection-pool {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.connection-list__head {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-text-2);
}

.connection-list__head small {
  margin-left: 4px;
  color: var(--c-text-3);
  font-weight: 400;
}

.connection-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(47, 95, 143, 0.06);
  border-radius: 6px;
  font-size: 12px;
}

.connection-row__from {
  flex: 1;
  font-weight: 600;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.connection-row__arrow {
  color: var(--c-text-3);
}

.connection-row__port {
  color: var(--c-text-3);
  font-size: 11px;
}

.connection-row .icon-button {
  margin-left: auto;
  width: 22px;
  height: 22px;
  line-height: 1;
  border-radius: 4px;
}

.connection-row .icon-button:hover {
  background: rgba(180, 35, 24, 0.1);
  color: var(--c-danger);
}

.chip--upstream {
  font-weight: 600;
}

.chip--upstream small {
  margin-left: 4px;
  font-weight: 400;
  color: var(--c-text-3);
}

.chip--upstream:hover small {
  color: inherit;
  opacity: 0.85;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.32);
  padding: 20px;
}

.run-dialog {
  display: grid;
  gap: 14px;
  width: min(520px, 100%);
  border: 1px solid rgba(148, 163, 184, 0.36);
  border-radius: 8px;
  background: var(--c-surface);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.22);
  padding: 16px;
}

.run-dialog__head,
.run-dialog__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.run-dialog__head h3 {
  margin: 0;
  font-size: 18px;
}

.run-dialog__head p {
  margin: 4px 0 0;
  color: var(--c-text-3);
  font-size: 12px;
}

.run-dialog__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.run-dialog__notice {
  display: grid;
  gap: 3px;
  border: 1px solid rgba(47, 118, 111, 0.24);
  border-radius: 6px;
  background: #f0f8f4;
  padding: 9px 10px;
  font-size: 12px;
  color: #2f766f;
}

.run-dialog__notice.is-error {
  border-color: rgba(180, 35, 24, 0.28);
  background: #fff4f2;
  color: #b42318;
}

.run-dialog__override {
  display: grid;
  gap: 6px;
  border: 1px solid rgba(150, 91, 32, 0.22);
  border-radius: 6px;
  background: #fff8ee;
  padding: 9px 10px;
  font-size: 12px;
  color: #7a4a1a;
}

.run-dialog__override > strong {
  color: var(--c-text);
}

.run-dialog__override-list {
  display: grid;
  gap: 6px;
}

.run-dialog__override-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  border-top: 1px solid rgba(150, 91, 32, 0.16);
  padding-top: 6px;
}

.run-dialog__override-list div {
  display: grid;
  min-width: 0;
}

.run-dialog__override-list strong,
.run-dialog__override-list small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-dialog__override-list small {
  color: #8a5d2d;
}

.run-detail-panel {
  flex: 0 0 auto;
}

.run-detail-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.run-detail-summary small {
  min-width: 0;
  overflow: hidden;
  color: var(--c-text-3);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-action-strip,
.lock-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.lock-panel small {
  color: var(--c-text-3);
  font-size: 11px;
  line-height: 1.45;
}

.run-detail-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 4px;
}

.run-detail-tabs button {
  min-height: 28px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-tint);
  color: var(--c-text-2);
  font-size: 11px;
  cursor: pointer;
}

.run-detail-tabs button.is-active {
  border-color: rgba(47, 95, 143, 0.4);
  background: #eef4fa;
  color: var(--c-primary);
  font-weight: 800;
}

.run-detail-body {
  display: grid;
  gap: 7px;
  max-height: 260px;
  overflow: auto;
}

.run-kv {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 6px 10px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-tint);
  padding: 8px;
  font-size: 12px;
}

.run-kv span {
  color: var(--c-text-3);
}

.run-kv strong {
  min-width: 0;
  overflow: hidden;
  color: var(--c-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-row,
.artifact-manage-row {
  display: grid;
  gap: 3px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: #fff;
  padding: 7px 8px;
  font-size: 12px;
}

.compact-row strong,
.compact-row span,
.compact-row small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-row span,
.compact-row small {
  color: var(--c-text-3);
}

.compact-row--task {
  gap: 7px;
}

.compact-row__main {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.task-actions button {
  min-height: 24px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: var(--c-bg-tint);
  color: var(--c-text-2);
  padding: 0 8px;
  font-size: 11px;
  cursor: pointer;
}

.task-actions button:hover:not(:disabled) {
  border-color: rgba(47, 95, 143, 0.38);
  color: var(--c-primary);
}

.task-actions button:disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

.task-event-list {
  display: grid;
  gap: 3px;
  border-top: 1px solid var(--c-border);
  padding-top: 6px;
}

.task-event-list span {
  color: var(--c-text-3);
  font-size: 11px;
  white-space: normal;
}

.artifact-toolbar {
  display: flex;
  justify-content: flex-end;
}

.artifact-manage-row__main {
  display: grid;
  gap: 2px;
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--c-text);
  padding: 0;
  text-align: left;
  cursor: pointer;
}

.artifact-manage-row__main strong,
.artifact-manage-row__main span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-manage-row__main span {
  color: var(--c-text-3);
  font-size: 11px;
}

.artifact-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.artifact-actions button {
  min-height: 24px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: var(--c-bg-tint);
  color: var(--c-text-2);
  padding: 0 8px;
  font-size: 11px;
  cursor: pointer;
}

.artifact-actions button:hover:not(:disabled) {
  border-color: rgba(47, 95, 143, 0.38);
  color: var(--c-primary);
}

.artifact-actions button:disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

@media (max-width: 900px) {
  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-actions {
    flex-wrap: wrap;
  }
}
</style>
