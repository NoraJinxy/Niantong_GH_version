<template>
  <div class="pipeline-page" @pointerdown="closePipelineContextMenu">
      <aside
        class="library"
        :class="{ 'is-hidden': !libraryVisible }"
        :style="{ width: libraryWidth + 'px' }"
      >
        <div
          class="drawer-handle drawer-handle--right"
          :class="{ 'is-dragging': drawerDragging === 'library' }"
          title="拖动调整宽度"
          @mousedown="startDrawerDrag('library', $event)"
        ></div>
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
                  <span class="node-template__type">{{ spec.type }}</span>
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
              <span v-else-if="currentPipeline" class="badge">v{{ currentPipeline.version }}</span>
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
                <span class="caret">▾</span>
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
                <strong>LiteGraph</strong>
                <span>{{ definition.graph.nodes.length }} 节点</span>
                <span>{{ definition.graph.links.length }} 连线</span>
              </div>
              <div class="canvas-overlay__actions">
                <button class="canvas-tool" type="button" @click="centerLiteGraphView">居中</button>
                <button class="canvas-tool" type="button" @click="resetLiteGraphZoom">100%</button>
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
            <span v-if="runArtifacts.length">{{ runArtifacts.length }} artifact</span>
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
        <div
          class="drawer-handle drawer-handle--left"
          :class="{ 'is-dragging': drawerDragging === 'inspector' }"
          title="拖动调整宽度"
          @mousedown="startDrawerDrag('inspector', $event)"
        ></div>
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
          </div>

          <div v-if="selectedNodeArtifacts.length" class="artifact-list">
            <button
              v-for="artifact in selectedNodeArtifacts"
              :key="artifact.id"
              class="artifact-row"
              :class="{ 'is-active': selectedArtifactPreview?.study_output_id === artifact.id }"
              type="button"
              @click="openArtifactPreview(artifact)"
            >
              <span>{{ artifactLabel(artifact) }}</span>
              <small>{{ artifact.data_type }} · {{ formatFileSize(artifact.file_size) }}</small>
            </button>
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
              <div v-if="prop.type === 'event_select'" class="field event-select">
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
              <div v-else-if="prop.type === 'channel_list'" class="field channel-list-field">
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
              <div v-else-if="prop.type === 'tags_input'" class="field tags-input-field">
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

              <label v-else class="field">
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

              <!-- 调试信息（只读元信息） -->
              <div class="save-settings__meta-title">调试信息</div>
              <div class="save-settings__meta">
                <div><span>step_label</span><code>{{ saveSpec.step_label || '—' }}</code></div>
                <div><span>data_type</span><code>{{ saveSpec.data_type || '—' }}</code></div>
                <div v-if="saveSpec.split_supported"><span>支持拆分</span><code>condition</code></div>
                <div v-if="saveSpec.always_per_condition"><span>逐 condition</span><code>是</code></div>
              </div>
            </div>
          </details>

          <div class="connections">
            <div class="panel__title panel__title--tight">连接</div>

            <div v-if="selectedNodeInputLinks.length" class="connection-list">
              <div class="connection-list__head">已连接的上游</div>
              <div
                v-for="link in selectedNodeInputLinks"
                :key="link.id"
                class="connection-row"
              >
                <span class="connection-row__from">{{ upstreamNodeLabel(link.from.node) }}</span>
                <span class="connection-row__arrow">→</span>
                <span class="connection-row__port">{{ link.to.port }}</span>
                <button
                  type="button"
                  class="icon-button"
                  title="移除该连线"
                  @click="removeLink(link.id)"
                >
                  ×
                </button>
              </div>
            </div>

            <div v-if="connectableUpstreamCandidates.length" class="connection-pool">
              <div class="connection-list__head">
                可作为上游
                <small>· 点击即可连接（也可在画布上从端口拖线）</small>
              </div>
              <div class="chip-row">
                <button
                  v-for="candidate in connectableUpstreamCandidates"
                  :key="candidate.node.id"
                  type="button"
                  class="chip chip--upstream"
                  :title="candidate.tooltip"
                  @click="quickConnectUpstream(candidate.node.id)"
                >
                  {{ candidate.label }}
                  <small v-if="candidate.outputType">· {{ candidate.outputType }}</small>
                </button>
              </div>
            </div>
            <div v-else-if="!selectedNodeInputLinks.length" class="state-text">
              当前画布里没有可作为上游的节点。先添加一个有输出端口的节点。
            </div>
          </div>
        </section>
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
import { datasetApi } from '@/api/datasets'
import { pipelineApi } from '@/api/pipelines'
import type {
  Recording,
  AsyncTask,
  LoadDataDataInfo,
  LoadDataResolveRequest,
  NodeProperty,
  NodeSpec,
  Pipeline,
  StudyOutput,
  StudyOutputPreview,
  PipelineDefinitionPayload,
  PipelineEditLock,
  PipelineGraphLink,
  PipelineGraphNode,
  PipelineIcaComponentPreview,
  PipelineInteraction,
  PipelineJob,
  PipelineExecution,
  PipelineExecutionDetail,
  PipelineExecutionLineage,
  PipelineExecutionMode,
  PipelineExecutionSelectionOverride,
  PipelineValidationResponse,
  TaskEvent,
} from '@/types'
import {
  LOAD_DATA_NODE_TYPE,
  EPOCH_NODE_TYPE,
  ERP_NODE_TYPE,
  ICA_APPLY_NODE_TYPE,
  NULL_FILTER_VALUE,
  DEFAULT_LOAD_DATA_QA_STATUS,
  LITEGRAPH_NODE_ID_PROP,
  LITEGRAPH_HIDPI_EVENT_PROP,
  LITEGRAPH_ORIGINAL_CLIENT_X_PROP,
  LITEGRAPH_ORIGINAL_CLIENT_Y_PROP,
  LITEGRAPH_ENGINE_INFO,
  LINK_DEFAULT_COLOR,
  LINK_HIGHLIGHT_COLOR,
  LINK_CONNECTING_COLOR,
  LINK_HIGHLIGHT_WIDTH_MULT,
  EXECUTION_POLL_INTERVAL_MS,
  EXECUTION_CANCELABLE_STATUSES,
  EXECUTION_RETRYABLE_STATUSES,
  TASK_CANCELABLE_STATUSES,
  TASK_RETRYABLE_STATUSES,
  EXECUTION_MODE_OPTIONS,
  NODE_CARD_WIDTH,
  NODE_CARD_MIN_HEIGHT,
  NODE_GAP_X,
  NODE_GAP_Y,
  LITEGRAPH_MIN_ZOOM,
  LITEGRAPH_MAX_ZOOM,
  LITEGRAPH_MAX_PIXEL_RATIO,
  DRAFT_LS_PREFIX,
  DRAFT_STORAGE_VERSION,
  LAYOUT_LS_PREFIX,
  LINK_HIGHLIGHT_PATCH_MARK,
  NO_SAVE_ICON_NODE_TYPES,
} from '@/composables/pipeline/pipelineConstants'
import {
  pipelinePortColors,
  portTypeColor,
  withAlpha,
  nodeStatusColor,
  nodeStatusSoftColor,
  formatJobStatus,
  jobStatusClass,
  stepVisualState,
  stepIcon,
  isStepDone,
  formatFileSize,
  shortId,
  numericMetric,
  formatMetricNumber,
  formatSecondsMetric,
  formatDurationMs,
  formatPipelineExecutionStatus,
  formatTaskStatus,
  formatDateTime,
  formatPipelineStatus,
  allowedExecutionModeText,
  formatExecutionMode,
  formatArtifactRetention,
  categoryColor,
  categorySoftColor,
  compactNodeTitle,
  portTypesCompatible,
  liteGraphPortType,
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

type LiteGraphNode = LGraphNode & {
  elysNodeId?: string
  constructor?: typeof LGraphNode & { title?: string; desc?: string }
}

type LooseLiteGraphCanvas = LGraphCanvas & Record<string, any>
type LooseLiteGraph = Record<string, any> & {
  _nodes?: LiteGraphNode[]
  _version?: number
  onAfterChange?: () => void
  onConnectionChange?: () => void
  onNodeRemoved?: () => void
}
type LooseLiteGraphTheme = typeof LiteGraph & Record<string, any>
type ElysPipelineNodeConstructor = typeof LGraphNode & { desc?: string }

type LiteGraphLink = {
  id?: number | string
  origin_id: number
  origin_slot: number
  target_id: number
  target_slot: number
}

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
const selectedPipelineId = ref('')
const currentPipeline = ref<Pipeline | null>(null)
const pipelineName = ref('未命名工作流')
const pipelineDescription = ref('')
const upstreamNodeId = ref('')
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
const registeredLiteGraphTypes = new Set<string>()
let draggedNodeType = ''
let liteGraphPixelRatio = 1
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
// —— 节点参数的条件显示 (visible_when) 与高级折叠 (advanced) ——
// effectiveNodeParams：属性默认值 + 用户实参合并，给 visible_when 判定用（控制字段未显式给时回退默认）
const effectiveNodeParams = computed<Record<string, unknown>>(() => {
  const eff: Record<string, unknown> = {}
  const spec = selectedNodeSpec.value
  if (spec) {
    for (const prop of spec.properties) {
      if (prop.default !== undefined) eff[prop.name] = prop.default
    }
  }
  const params = (selectedNode.value?.params ?? {}) as Record<string, unknown>
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') eff[key] = value
  }
  return eff
})
const isPropVisible = (prop: { visible_when?: Record<string, Array<string | number | boolean>> }): boolean => {
  const rules = prop.visible_when
  if (!rules) return true
  const eff = effectiveNodeParams.value
  return Object.entries(rules).every(([key, allowed]) =>
    allowed.map((value) => String(value)).includes(String(eff[key])),
  )
}
const visibleBasicProperties = computed(() =>
  (selectedNodeSpec.value?.properties ?? []).filter((prop) => !prop.advanced && isPropVisible(prop)),
)
const visibleAdvancedProperties = computed(() =>
  (selectedNodeSpec.value?.properties ?? []).filter((prop) => prop.advanced && isPropVisible(prop)),
)
/**
 * 从所有 LoadData 节点出发 BFS，标记所有"上游可达 LoadData"的节点 id。
 * 用于画布保留指示：只有可达节点才谈得上"保留产物"，孤立节点（拖出但没连数据源）不画。
 */
const reachableNodeIds = computed<Set<string>>(() => {
  const reachable = new Set<string>()
  const nodes = definition.value.graph.nodes
  const links = definition.value.graph.links || []
  const queue: string[] = []
  for (const n of nodes) {
    if (n.type === LOAD_DATA_NODE_TYPE) {
      reachable.add(n.id)
      queue.push(n.id)
    }
  }
  if (queue.length === 0) return reachable
  const downstreamByFrom: Record<string, string[]> = {}
  for (const link of links) {
    const from = link.from?.node
    const to = link.to?.node
    if (typeof from === 'string' && typeof to === 'string') {
      if (!downstreamByFrom[from]) downstreamByFrom[from] = []
      downstreamByFrom[from].push(to)
    }
  }
  while (queue.length) {
    const cur = queue.shift() as string
    const next = downstreamByFrom[cur] || []
    for (const id of next) {
      if (!reachable.has(id)) {
        reachable.add(id)
        queue.push(id)
      }
    }
  }
  return reachable
})

/** 叶子节点（最终输出）强制保留的提示文案。 */
const keepLeafHint = '最终结果默认保存；不需要请直接删除该节点'

/** 当前选中节点是否保留输出。
 *  叶子节点（最终产出）强制保留；中间节点取 params.keep override，默认不保留。 */
const selectedNodeKeep = computed<boolean>(() => {
  if (isLeafNode.value) return true
  const override = selectedNode.value?.params?.keep
  if (typeof override === 'boolean') return override
  if (override === 'true') return true
  if (override === 'false') return false
  return false
})

/** 节点拓扑前缀（leaf / intermediate / detached）。 */
const topologyLabel = computed<string>(() => {
  const node = selectedNode.value
  if (!node) return ''
  if (!reachableNodeIds.value.has(node.id)) return 'detached'
  return isLeafNode.value ? 'leaf' : 'intermediate'
})

/** keep checkbox 是否禁用：叶子节点强制保留、或未连数据源不产出。 */
const keepCheckboxDisabled = computed<boolean>(() => isLeafNode.value || topologyLabel.value === 'detached')

function onToggleKeep(event: Event) {
  const node = selectedNode.value
  if (!node || keepCheckboxDisabled.value) return
  const checked = (event.target as HTMLInputElement).checked
  node.params = { ...node.params, keep: checked }
  updateLiteGraphNode(node)
  markDirty()
}
// [Dead code 已清理] 旧 LoadData chip UI 相关 computed (loadDataSelectionMode/eligibleLoadDataDatasets/matchedLoadDataDatasets/loadData*Options 等) 已全部删除，
// 筛选逻辑迁移到 LoadDataPanel.vue 组件内部。

// === Epoch / ERP 节点：事件标签下拉 ===
const isEpochNode = computed(() => selectedNode.value?.type === EPOCH_NODE_TYPE)
const isErpNode = computed(() => selectedNode.value?.type === ERP_NODE_TYPE)

/** 沿 graph.links 倒推：从某节点开始向上找指定 type 的最近祖先节点（BFS）。 */
function findUpstreamNodeByType(startNodeId: string, targetType: string): typeof definition.value.graph.nodes[number] | null {
  const links = definition.value.graph.links || []
  const incoming: Record<string, string[]> = {}
  for (const link of links) {
    const from = link.from?.node
    const to = link.to?.node
    if (typeof from === 'string' && typeof to === 'string') {
      if (!incoming[to]) incoming[to] = []
      incoming[to].push(from)
    }
  }
  const visited = new Set<string>([startNodeId])
  const queue: string[] = [...(incoming[startNodeId] || [])]
  while (queue.length) {
    const cur = queue.shift() as string
    if (visited.has(cur)) continue
    visited.add(cur)
    const node = definition.value.graph.nodes.find((n) => n.id === cur)
    if (node?.type === targetType) return node
    const parents = incoming[cur] || []
    for (const p of parents) if (!visited.has(p)) queue.push(p)
  }
  return null
}

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

const availableEventLabels = computed<Array<{ label: string; count: number; datasets: number }>>(() => {
  // Epoch 节点：从 graph 中所有 LoadData 节点的"已选中" data_infos 聚合事件。
  // 关键：用 loadDataSelectedInfos —— LoadData 没勾文件 → 无事件，不会泄漏数据库全集。
  if (isEpochNode.value) {
    const aggregate = new Map<string, { count: number; datasets: number }>()
    for (const node of definition.value.graph.nodes) {
      if (node.type !== LOAD_DATA_NODE_TYPE) continue
      for (const info of loadDataSelectedInfos(node)) {
        const labels = info.event_labels || []
        const counts = info.event_counts || {}
        for (const label of labels) {
          const existing = aggregate.get(label) || { count: 0, datasets: 0 }
          existing.count += counts[label] || 0
          existing.datasets += 1
          aggregate.set(label, existing)
        }
      }
    }
    return Array.from(aggregate.entries())
      .map(([label, info]) => ({ label, count: info.count, datasets: info.datasets }))
      .sort((a, b) => {
        const an = Number(a.label)
        const bn = Number(b.label)
        if (!Number.isNaN(an) && !Number.isNaN(bn)) return an - bn
        return a.label.localeCompare(b.label)
      })
  }

  // ERP 节点：候选 condition 只能是上游 Epoch 节点 event_id 里选过的
  // count / datasets 同样按 LoadData dataset_ids 过滤。
  if (isErpNode.value && selectedNode.value) {
    const upstreamEpoch = findUpstreamNodeByType(selectedNode.value.id, EPOCH_NODE_TYPE)
    const raw = upstreamEpoch?.params?.event_id
    let labels: string[] = []
    if (Array.isArray(raw)) labels = raw.map((s) => String(s).trim()).filter(Boolean)
    else if (typeof raw === 'string' && raw.trim()) {
      labels = raw.split(',').map((s) => s.trim()).filter(Boolean)
    }

    const allowed = new Set(labels)
    const aggregate = new Map<string, { count: number; datasets: number }>()
    for (const n of definition.value.graph.nodes) {
      if (n.type !== LOAD_DATA_NODE_TYPE) continue
      for (const info of loadDataSelectedInfos(n)) {
        const ls = info.event_labels || []
        const counts = info.event_counts || {}
        for (const lab of ls) {
          if (!allowed.has(lab)) continue
          const existing = aggregate.get(lab) || { count: 0, datasets: 0 }
          existing.count += counts[lab] || 0
          existing.datasets += 1
          aggregate.set(lab, existing)
        }
      }
    }

    // 保持上游 Epoch event_id 中的标签顺序；没真实 count 的填 0
    return labels.map((label) => {
      const info = aggregate.get(label)
      return { label, count: info?.count ?? 0, datasets: info?.datasets ?? 0 }
    })
  }

  return []
})

function getEventIdArray(prop: NodeProperty): string[] {
  const raw = selectedNode.value?.params?.[prop.name]
  if (Array.isArray(raw)) return raw.map((item) => String(item)).filter(Boolean)
  if (typeof raw === 'string' && raw.trim()) {
    return raw
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

function isEventIdSelected(prop: NodeProperty, label: string) {
  return getEventIdArray(prop).includes(label)
}

function toggleEventId(prop: NodeProperty, label: string) {
  const node = selectedNode.value
  if (!node) return
  const current = new Set(getEventIdArray(prop))
  if (current.has(label)) current.delete(label)
  else current.add(label)
  node.params = { ...node.params, [prop.name]: Array.from(current) }
  updateLiteGraphNode(node)
  markDirty()
}

function clearEventIds(prop: NodeProperty) {
  const node = selectedNode.value
  if (!node) return
  node.params = { ...node.params, [prop.name]: [] }
  updateLiteGraphNode(node)
  markDirty()
}

// === 保存设置（P4）===
// 折叠区展开状态 + 自定义标签草稿（独立于其他 tag drafts）
const saveSettingsOpen = ref(false)
const userTagDraft = ref('')

/** 节点 spec 中 save 子对象（P0 起所有处理节点都填）。无则隐藏整个折叠区。 */
const saveSpec = computed<Record<string, unknown> | null>(() => {
  const raw = (selectedNodeSpec.value as Record<string, unknown> | null)?.save
  if (!raw || typeof raw !== 'object') return null
  // LoadData 等 source 节点不声明 save 字段，但后端 Pydantic schema
  // 用 default_factory=dict 默认填空 {} → 前端要把空 dict 视为"无保存配置"。
  if (Object.keys(raw as Record<string, unknown>).length === 0) return null
  return raw as Record<string, unknown>
})

/** 拓扑角色：节点的输出端口在 graph.links 中出现 → intermediate，否则 leaf。
 *  source 节点（LoadData）在这套 UI 中无 save 子对象不会渲染折叠区，不需要单独处理。
 */
const isLeafNode = computed<boolean>(() => {
  const node = selectedNode.value
  if (!node) return true
  const links = definition.value.graph.links || []
  return !links.some((link) => link.from?.node === node.id)
})

/** Epoch 节点 split_by=condition 时，模板使用 _split 变体；否则用 default 模板。 */
const splitMode = computed<string>(() => {
  const node = selectedNode.value
  if (!node) return 'none'
  const raw = node.params?.split_by
  return typeof raw === 'string' ? raw.trim().toLowerCase() : 'none'
})

/** 选择当前生效的 spec 模板（split 影响模板选择）。 */
const effectiveNameTemplate = computed<string>(() => {
  const spec = saveSpec.value
  if (!spec) return '{subject}_{task}_{node_title}'
  if (splitMode.value === 'condition') {
    return String(spec.name_template_default_split || spec.name_template_default || '{subject}_{task}_{node_title}')
  }
  return String(spec.name_template_default || '{subject}_{task}_{node_title}')
})

/** display_name 预览（前端复刻后端 render_template，缺失值回落 {name?}）。 */
function renderTemplatePreview(tpl: string, ctx: Record<string, unknown>): string {
  if (!tpl) return ''
  return tpl.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, (_match, name: string) => {
    if (name === 'subject') {
      const v = ctx.subject || ctx.bids_subject_id || ctx.subject_id
      return v ? String(v) : '{subject?}'
    }
    if (name === 'index') {
      return ctx.index != null ? String(ctx.index) : '{index?}'
    }
    const v = ctx[name]
    if (v === undefined || v === null || v === '') return `{${name}?}`
    return String(v)
  })
}

const previewDisplayName = computed<string>(() => {
  const node = selectedNode.value
  const spec = saveSpec.value
  if (!node || !spec) return ''
  const userTemplate = String(node.params?.display_name_template || '').trim()
  const template = userTemplate || effectiveNameTemplate.value
  // 用 study_datasets 第一项的 subject/task 作为预览示例
  const exampleRaw = ((studyDatasets.value || [])[0] || {}) as Record<string, unknown>
  const exampleSubject =
    (exampleRaw.bids_subject_id as string | undefined) ||
    (exampleRaw.subject_id as string | undefined) ||
    'sub-XX'
  const exampleTask = (exampleRaw.task as string | undefined) || 'task'
  // condition 预览：split=condition 时用 'go'；ERP 节点用 params.condition 第一个
  let exampleCondition: string | undefined
  if (splitMode.value === 'condition') {
    exampleCondition = 'go'
  } else {
    const condRaw = node.params?.condition
    if (typeof condRaw === 'string' && condRaw.trim()) exampleCondition = condRaw.trim()
    else if (Array.isArray(condRaw) && condRaw.length) exampleCondition = String(condRaw[0])
    else if (spec.always_per_condition) exampleCondition = 'go'
  }
  return renderTemplatePreview(template, {
    subject: exampleSubject,
    bids_subject_id: exampleSubject,
    task: exampleTask,
    node_title: node.title || selectedNodeSpec.value?.title || node.type,
    step_label: spec.step_label,
    data_type: spec.data_type,
    condition: exampleCondition,
    index: 1,
  })
})

/** 自动 tag 预览（spec 的 auto_tags + dynamic_tags，模板渲染后展示给用户）。 */
const autoTagsPreview = computed<string[]>(() => {
  const spec = saveSpec.value
  if (!spec) return []
  const result: string[] = []
  const seen = new Set<string>()
  const node = selectedNode.value
  const ctx: Record<string, unknown> = {
    condition: splitMode.value === 'condition' ? '{condition}' : (node?.params?.condition || (spec.always_per_condition ? '{condition}' : '')),
  }
  const sources: unknown[] = [spec.auto_tags]
  if (spec.always_per_condition) sources.push(spec.dynamic_tags_always)
  else if (splitMode.value === 'condition') sources.push(spec.dynamic_tags_when_split)
  for (const source of sources) {
    if (!Array.isArray(source)) continue
    for (const raw of source) {
      const tag = renderTemplatePreview(String(raw), ctx).trim()
      if (!tag || seen.has(tag)) continue
      seen.add(tag)
      result.push(tag)
    }
  }
  return result
})

/** 用户自定义标签（存于 selectedNode.params.tags）。 */
const userTagsArray = computed<string[]>(() => {
  const raw = selectedNode.value?.params?.tags
  if (Array.isArray(raw)) return raw.map((item) => String(item).trim()).filter(Boolean)
  if (typeof raw === 'string' && raw.trim()) {
    return raw.split(',').map((item) => item.trim()).filter(Boolean)
  }
  return []
})

function getSaveSetting(field: string): string {
  const raw = selectedNode.value?.params?.[field]
  if (raw == null) return ''
  return String(raw)
}

function onSaveSettingInput(field: string, event: Event) {
  const node = selectedNode.value
  if (!node) return
  const target = event.target as HTMLInputElement | HTMLSelectElement
  const value = target.value
  node.params = { ...node.params, [field]: value }
  updateLiteGraphNode(node)
  markDirty()
}

function onSaveSettingsToggle(event: Event) {
  saveSettingsOpen.value = (event.target as HTMLDetailsElement).open
}

function removeUserTag(tag: string) {
  const node = selectedNode.value
  if (!node) return
  const next = userTagsArray.value.filter((t) => t !== tag)
  node.params = { ...node.params, tags: next }
  updateLiteGraphNode(node)
  markDirty()
}

function commitUserTagDraft() {
  const node = selectedNode.value
  if (!node) return
  const draft = userTagDraft.value
  if (!draft.trim()) return
  const pieces = draft.split(',').map((s) => s.trim()).filter(Boolean)
  const merged = [...userTagsArray.value]
  for (const piece of pieces) {
    if (!merged.includes(piece)) merged.push(piece)
  }
  node.params = { ...node.params, tags: merged }
  userTagDraft.value = ''
  updateLiteGraphNode(node)
  markDirty()
}

// === tags_input 通用属性渲染（Save 节点等使用）===
const paramTagDrafts = reactive<Record<string, string>>({})

function paramTagKey(prop: NodeProperty): string {
  const node = selectedNode.value
  return `${node?.id || ''}::${prop.name}`
}

function getTagsArray(prop: NodeProperty): string[] {
  const node = selectedNode.value
  if (!node) return []
  const raw = node.params[prop.name]
  if (Array.isArray(raw)) return raw.map((item) => String(item)).filter(Boolean)
  if (typeof raw === 'string' && raw.trim()) {
    return raw.split(',').map((item) => item.trim()).filter(Boolean)
  }
  return []
}

function paramTagDraftFor(prop: NodeProperty): string {
  return paramTagDrafts[paramTagKey(prop)] || ''
}

function setParamTagDraft(prop: NodeProperty, value: string) {
  paramTagDrafts[paramTagKey(prop)] = value
}

function commitParamTagDraft(prop: NodeProperty) {
  const node = selectedNode.value
  if (!node) return
  const draft = (paramTagDrafts[paramTagKey(prop)] || '').trim()
  if (!draft) return
  const existing = getTagsArray(prop)
  const next: string[] = [...existing]
  const seen = new Set(existing)
  for (const piece of draft.split(',')) {
    const text = piece.trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    next.push(text)
  }
  node.params = { ...node.params, [prop.name]: next }
  paramTagDrafts[paramTagKey(prop)] = ''
  updateLiteGraphNode(node)
  markDirty()
}

function toggleParamTag(prop: NodeProperty, tag: string) {
  const node = selectedNode.value
  if (!node) return
  const tags = getTagsArray(prop).filter((item) => item !== tag)
  node.params = { ...node.params, [prop.name]: tags }
  updateLiteGraphNode(node)
  markDirty()
}

// === channel_list 类型：从上游 LoadData 通道做 listbox 多选 ===
// 设计语义（与节点 spec.help 一致）：
//   单选 = 单通道做参考；多选 = 这些通道的平均做参考；全选 = 共同平均参考
// 通道列表来源：当前节点所有上游 LoadData 节点 selectedInfos 的 ch_names 交集。
// 交集而非并集 —— 用户如果选了多个 ch_names 不一致的文件，只显示"都有"的通道，避免运行时报错。

const channelFilterDrafts = reactive<Record<string, string>>({})

function channelFilterKey(prop: NodeProperty): string {
  return `${selectedNode.value?.id || ''}::${prop.name}`
}

function channelFilterFor(prop: NodeProperty): string {
  return channelFilterDrafts[channelFilterKey(prop)] || ''
}

function setChannelFilter(prop: NodeProperty, value: string) {
  channelFilterDrafts[channelFilterKey(prop)] = value
}

/** 沿 graph.links 倒推所有上游节点中类型为 targetType 的全部节点（BFS，不止找第一个）。 */
function findAllUpstreamNodesByType(startNodeId: string, targetType: string): typeof definition.value.graph.nodes {
  const links = definition.value.graph.links || []
  const incoming: Record<string, string[]> = {}
  for (const link of links) {
    const from = link.from?.node
    const to = link.to?.node
    if (typeof from === 'string' && typeof to === 'string') {
      if (!incoming[to]) incoming[to] = []
      incoming[to].push(from)
    }
  }
  const visited = new Set<string>([startNodeId])
  const queue: string[] = [...(incoming[startNodeId] || [])]
  const result: typeof definition.value.graph.nodes = []
  while (queue.length) {
    const cur = queue.shift() as string
    if (visited.has(cur)) continue
    visited.add(cur)
    const node = definition.value.graph.nodes.find((n) => n.id === cur)
    if (node) {
      if (node.type === targetType) result.push(node)
      for (const p of incoming[cur] || []) if (!visited.has(p)) queue.push(p)
    }
  }
  return result
}

/** 当前选中节点的上游通道选项（交集 + 保持出现顺序）。
 *  过滤空字符串/None 名字，避免 backend 旧 cache 数据 / 异常 mne info 导致 listbox 出现空行。
 */
const upstreamChannels = computed<string[]>(() => {
  const node = selectedNode.value
  if (!node) return []
  const loadDataNodes = findAllUpstreamNodesByType(node.id, LOAD_DATA_NODE_TYPE)
  let common: string[] | null = null
  for (const ld of loadDataNodes) {
    for (const info of loadDataSelectedInfos(ld)) {
      const names = (info.ch_names || [])
        .map((n) => (n == null ? '' : String(n).trim()))
        .filter(Boolean)
      if (!names.length) continue
      if (common === null) {
        common = [...names]
      } else {
        const s = new Set(names)
        common = common.filter((c) => s.has(c))
      }
    }
  }
  return common || []
})

function getChannelListArray(prop: NodeProperty): string[] {
  const node = selectedNode.value
  if (!node) return []
  const raw = node.params[prop.name]
  if (Array.isArray(raw)) return raw.map((item) => String(item)).filter(Boolean)
  if (typeof raw === 'string' && raw.trim()) {
    return raw.split(',').map((item) => item.trim()).filter(Boolean)
  }
  return []
}

function isChannelSelected(prop: NodeProperty, ch: string): boolean {
  return getChannelListArray(prop).includes(ch)
}

function setChannelListArray(prop: NodeProperty, channels: string[]) {
  const node = selectedNode.value
  if (!node) return
  // 保持 upstreamChannels 的顺序，避免乱序导致 hash 抖动
  const order = new Map(upstreamChannels.value.map((c, i) => [c, i]))
  const sorted = [...new Set(channels)].sort((a, b) => {
    const ai = order.has(a) ? (order.get(a) as number) : Number.MAX_SAFE_INTEGER
    const bi = order.has(b) ? (order.get(b) as number) : Number.MAX_SAFE_INTEGER
    return ai - bi
  })
  node.params = { ...node.params, [prop.name]: sorted }
  updateLiteGraphNode(node)
  markDirty()
}

function toggleChannel(prop: NodeProperty, ch: string) {
  const current = new Set(getChannelListArray(prop))
  if (current.has(ch)) current.delete(ch)
  else current.add(ch)
  setChannelListArray(prop, Array.from(current))
}

function selectAllChannels(prop: NodeProperty) {
  setChannelListArray(prop, [...upstreamChannels.value])
}

function clearChannels(prop: NodeProperty) {
  setChannelListArray(prop, [])
}

function invertChannels(prop: NodeProperty) {
  const cur = new Set(getChannelListArray(prop))
  const inverted = upstreamChannels.value.filter((c) => !cur.has(c))
  setChannelListArray(prop, inverted)
}

function filteredChannelOptions(prop: NodeProperty): string[] {
  const q = channelFilterFor(prop).trim().toLowerCase()
  if (!q) return upstreamChannels.value
  return upstreamChannels.value.filter((c) => c.toLowerCase().includes(q))
}

// === channel_list listbox 多选交互（与 LoadDataPanel Include 一致） ===
// 单击 = toggle，Shift+点击 = 从上次锚点到当前位置范围加入，Ctrl+A = 全选可见，Delete = 移除已选
//
// 注：不用 :ref="callback" 拿 DOM，因为 v-if/v-show 切换时 callback 会反复 mount/unmount，
// 配合 reactive 数据闪烁可能产生异常。focus 改成 click 时从 event.currentTarget.closest 找。

/** prop key → 上次点击的可见索引（Shift 范围锚点） */
const channelLastAnchor = reactive<Record<string, number>>({})

function handleChannelListClick(e: MouseEvent, prop: NodeProperty, idx: number, ch: string) {
  // focus 父 listbox（按 keydown 监听就在它上面）—— 用 currentTarget 找最近 .channel-list__box
  ;(e.currentTarget as HTMLElement | null)
    ?.closest<HTMLElement>('.channel-list__box')
    ?.focus()
  const key = channelFilterKey(prop)
  const visible = filteredChannelOptions(prop)
  const lastIdx = channelLastAnchor[key]

  if (e.shiftKey && typeof lastIdx === 'number' && lastIdx >= 0) {
    const current = new Set(getChannelListArray(prop))
    const [start, end] = [Math.min(lastIdx, idx), Math.max(lastIdx, idx)]
    for (let i = start; i <= end; i++) {
      const item = visible[i]
      if (item) current.add(item)
    }
    setChannelListArray(prop, Array.from(current))
  } else {
    toggleChannel(prop, ch)
  }
  channelLastAnchor[key] = idx
}

function handleChannelListKeydown(e: KeyboardEvent, prop: NodeProperty) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
    e.preventDefault()
    // 只全选当前过滤后可见的（与文件列表 Ctrl+A 一致）
    const visible = filteredChannelOptions(prop)
    const current = new Set(getChannelListArray(prop))
    for (const ch of visible) current.add(ch)
    setChannelListArray(prop, Array.from(current))
    return
  }
  if (e.key === 'Delete' || e.key === 'Backspace') {
    // 移除当前已选的所有通道（focused listbox 内）
    if (getChannelListArray(prop).length > 0) {
      e.preventDefault()
      clearChannels(prop)
    }
  }
}

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

const upstreamCandidates = computed(() => {
  if (!selectedNode.value) return []
  return definition.value.graph.nodes.filter((node) => node.id !== selectedNode.value?.id)
})

const selectedNodeLinks = computed(() => {
  if (!selectedNode.value) return []
  return definition.value.graph.links.filter(
    (link) => link.from.node === selectedNode.value?.id || link.to.node === selectedNode.value?.id,
  )
})

const selectedNodeInputLinks = computed(() => {
  if (!selectedNode.value) return []
  return definition.value.graph.links.filter((link) => link.to.node === selectedNode.value?.id)
})

const connectableUpstreamCandidates = computed(() => {
  if (!selectedNode.value || !selectedNodeSpec.value) return []
  const targetInput = selectedNodeSpec.value.inputs?.[0]
  if (!targetInput) return []
  const alreadyConnected = new Set(
    selectedNodeInputLinks.value.map((link) => link.from.node),
  )
  const candidates: Array<{
    node: PipelineGraphNode
    label: string
    outputType: string
    tooltip: string
  }> = []
  for (const node of definition.value.graph.nodes) {
    if (node.id === selectedNode.value.id) continue
    if (alreadyConnected.has(node.id)) continue
    const spec = specForNode(node)
    if (!spec || !spec.outputs?.length) continue
    const output = spec.outputs.find((port) => portTypesCompatible(port.type, targetInput.type))
    if (!output) continue
    const label = node.title || spec.title || node.id
    candidates.push({
      node,
      label,
      outputType: output.label || output.type || output.name,
      tooltip: `${spec.title || node.id} 的 ${output.label || output.type} → 当前节点的 ${targetInput.label || targetInput.type}`,
    })
  }
  return candidates
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

onMounted(async () => {
  restoreLayoutState()
  await nextTick()
  initLiteGraphCanvas()
  hydrating.value = true
  await loadNodeSpecs()
  hydrating.value = false
  if (selectedStudyId.value) {
    await Promise.all([loadPipelines(routeTarget()), loadDatasets(selectedStudyId.value)])
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
  liteGraphCanvas.show_info = true
  canvas.renderInfo = renderPipelineCanvasInfo
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
  theme.NODE_SLOT_HEIGHT = 28
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

function renderPipelineCanvasInfo(ctx: CanvasRenderingContext2D) {
  const canvas = liteGraphCanvas
  const graph = canvas?.graph
  if (!canvas || !graph) return
  const nodes = liteGraphNodes(graph)
  const version = (graph as unknown as LooseLiteGraph)._version ?? 0

  const ratio = Math.max(1, liteGraphPixelRatio || 1)
  const fontSize = 12.5 * ratio
  const lineHeight = 17 * ratio
  const paddingX = 8 * ratio
  const paddingY = 7 * ratio
  const left = 12 * ratio
  const bottom = 12 * ratio
  const lines = [
    `T: ${graph.globaltime.toFixed(2)}s · I: ${graph.iteration} · N: ${nodes.length}[${canvas.visible_nodes.length}]`,
    `V: ${version} · FPS: ${canvas.fps.toFixed(1)}`,
  ]

  ctx.save()
  ctx.font = `500 ${fontSize}px "Segoe UI", Arial, sans-serif`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'alphabetic'

  const boxWidth = Math.ceil(Math.max(...lines.map((line) => ctx.measureText(line).width)) + paddingX * 2)
  const boxHeight = Math.ceil(lineHeight * lines.length + paddingY * 2)
  const top = Math.max(10 * ratio, (ctx.canvas.height || canvas.canvas.height) - bottom - boxHeight)

  ctx.fillStyle = 'rgba(255, 255, 255, 0.82)'
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.28)'
  ctx.lineWidth = 1 * ratio
  ctx.beginPath()
  ctx.roundRect(left, top, boxWidth, boxHeight, [7 * ratio])
  ctx.fill()
  ctx.stroke()

  ctx.fillStyle = '#536273'
  lines.forEach((line, index) => {
    ctx.fillText(line, left + paddingX, top + paddingY + (index + 0.78) * lineHeight)
  })
  ctx.restore()
}

function liteGraphNodes(graph: LGraph | null | undefined): LiteGraphNode[] {
  return ((graph as unknown as LooseLiteGraph | null | undefined)?._nodes || []) as LiteGraphNode[]
}

/** 从 LiteGraph 自身 link 结构出发，BFS 找出"从某个 LoadData 节点可顺流到达"的所有节点 elysNodeId 集合。
 *  用于画布"保存指示胶囊"判定：节点必须通过 input 链路一路追溯到 LoadData，才认为可达。
 *
 *  关键：直接读 LiteGraph 的 outputs[].links + liteGraph.links（不依赖 Vue 响应式 definition.value.graph，
 *  避免新节点拖入后 graph 还没 sync 的时序问题——task #65 的修复留下的盲区是只看了"自己有 input link"）。
 */
function liteGraphReachableFromLoadData(graph: LGraph | null | undefined): Set<string> {
  const reachable = new Set<string>()
  if (!graph) return reachable
  const allNodes = liteGraphNodes(graph)
  const links = ((graph as unknown as { links?: Record<string, LiteGraphLink> })?.links) || {}

  // 用 LiteGraph 内部 numeric id 走 BFS（link.target_id 是 numeric）
  const visitedInternal = new Set<number>()
  const queue: number[] = []
  for (const n of allNodes) {
    const type = String((n as { type?: unknown }).type || '')
    if (type !== LOAD_DATA_NODE_TYPE) continue
    const internalId = (n as unknown as { id?: number }).id
    const elysId = getLiteGraphNodeId(n)
    if (typeof internalId !== 'number' || !elysId) continue
    if (visitedInternal.has(internalId)) continue
    visitedInternal.add(internalId)
    reachable.add(elysId)
    queue.push(internalId)
  }

  const getNodeById = (graph as unknown as { getNodeById?: (id: number) => LiteGraphNode | null }).getNodeById?.bind(graph)
  if (!getNodeById) return reachable

  while (queue.length) {
    const curId = queue.shift() as number
    const cur = getNodeById(curId)
    if (!cur) continue
    const outputs = (cur as unknown as { outputs?: Array<{ links?: unknown } | null> }).outputs || []
    for (const out of outputs) {
      const outLinks = out?.links
      if (!Array.isArray(outLinks)) continue
      for (const linkId of outLinks as unknown[]) {
        if (typeof linkId !== 'number') continue
        const link = links[String(linkId) as keyof typeof links] || (links as unknown as Record<number, LiteGraphLink>)[linkId]
        if (!link || typeof link.target_id !== 'number') continue
        if (visitedInternal.has(link.target_id)) continue
        visitedInternal.add(link.target_id)
        const targetNode = getNodeById(link.target_id)
        if (targetNode) {
          const targetElysId = getLiteGraphNodeId(targetNode)
          if (targetElysId) reachable.add(targetElysId)
        }
        queue.push(link.target_id)
      }
    }
  }
  return reachable
}

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
  const artifacts = runArtifactsByJobId.value.get(job.id) || []
  const saved = artifacts.filter((item) => !item.deleted_at)
  if (!saved.length) {
    statusMessage.value = '该节点输出未保存（未保留的中间结果），无法查看时域图'
    return
  }
  // 优先 evoked（带时域采样曲线），否则取第一个已保存产物
  const target = saved.find((item) => item.data_type === 'evoked') || saved[0]
  const params = new URLSearchParams({
    study: studyId,
    dd: target.id,
    name: target.display_name || target.data_type || '结果',
    type: target.data_type || '',
  })
  // 用 <a target="_blank"> 模拟点链接 → 浏览器按"在新标签页打开"处理（可拖进标签栏并排），
  // 比 window.open(name) 更可靠：后者在部分浏览器里会被当成独立弹窗，无法并入标签栏
  const link = document.createElement('a')
  link.href = `/observe/waveform?${params.toString()}`
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
  return job.log_tail || ''
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

/**
 * 画节点左侧那根 category 主色竖条（accent bar）。
 *
 * 关键：用节点圆角矩形边框「同一条路径」做 clip，再填一个直角矩形，
 * 让竖条上/下两个圆角精确贴合边框圆角（半径 6）。
 *
 * 不能直接用 roundRect 画这根 4px 宽的窄条：canvas roundRect 规范在
 * 「同一条边上两圆角半径之和 > 边长」时会按比例收缩半径——4px 宽配半径 6
 * 会被压成约 4，竖条圆弧就和半径 6 的边框圆弧对不上（圆心、弧度都偏）。
 */
function drawNodeAccentBar(
  ctx: CanvasRenderingContext2D,
  color: string,
  width: number,
  bodyHeight: number,
  titleHeight: number,
) {
  const fullHeight = bodyHeight + titleHeight
  ctx.save()
  ctx.beginPath()
  // 与 onDrawForeground 里节点边框完全一致的圆角路径（原点 0.5、半径 6）
  ctx.roundRect(0.5, -titleHeight + 0.5, width, fullHeight, [6])
  ctx.clip()
  ctx.fillStyle = color
  ctx.fillRect(0, -titleHeight, 4, fullHeight)
  ctx.restore()
}

function drawNodeStatusBadge(ctx: CanvasRenderingContext2D, width: number, status: string) {
  const label = formatJobStatus(status)
  const titleHeight = LiteGraph.NODE_TITLE_HEIGHT
  const badgeHeight = 18
  ctx.save()
  ctx.font = '600 10px "Segoe UI", Arial, sans-serif'
  const textWidth = ctx.measureText(label).width
  const badgeWidth = Math.max(40, textWidth + 14)
  const x = Math.max(10, width - badgeWidth - 8)
  // 标题栏内（y < 0），上下居中：badge 高 18，标题栏高 titleHeight，居中 -titleHeight + (titleHeight - 18)/2
  const y = -titleHeight + (titleHeight - badgeHeight) / 2
  ctx.fillStyle = nodeStatusSoftColor(status)
  ctx.strokeStyle = withAlpha(nodeStatusColor(status), 0.42)
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.roundRect(x, y, badgeWidth, badgeHeight, [badgeHeight / 2])
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = nodeStatusColor(status)
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, x + badgeWidth / 2, y + badgeHeight / 2)
  ctx.restore()
}

/**
 * 在节点底部画一个"保留"指示胶囊 —— 颜色取节点自己的 spec.ui.color。
 *
 * 设计参考: mockup_save_indicator.html 变体 6（圆角胶囊色块）。
 * 形状: 距左右各 14px、距底 3px、高 4px 的圆角矩形（圆角半径 = 高度的一半 → 完全胶囊形）。
 *
 * 概念：节点产物只有"保留"一种状态。color 传 null 表示不画
 * （不可达节点 / 用户选择 retention=cached/none / intermediate 默认）。
 */
function drawNodeSaveIcon(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  color: string | null,
) {
  if (!color) return

  const padX = 14
  const barH = 4
  const marginBottom = 3
  const x = padX
  const y = height - barH - marginBottom
  const w = Math.max(0, width - padX * 2)
  if (w <= 0) return

  ctx.save()
  ctx.fillStyle = color
  ctx.beginPath()
  if (typeof (ctx as unknown as { roundRect?: unknown }).roundRect === 'function') {
    ctx.roundRect(x, y, w, barH, [barH / 2])
  } else {
    ctx.rect(x, y, w, barH)
  }
  ctx.fill()
  ctx.restore()
}

function centerLiteGraphView() {
  if (!liteGraph || !liteGraphCanvas) return
  const targetNode = (selectedNodeId.value && findLiteGraphNode(selectedNodeId.value)) || liteGraphNodes(liteGraph)[0]
  if (targetNode) liteGraphCanvas.centerOnNode(targetNode)
  liteGraphCanvas.setDirty(true, true)
}

function resetLiteGraphZoom() {
  if (!liteGraphCanvas) return
  liteGraphCanvas.ds.scale = liteGraphPixelRatio
  liteGraphCanvas.ds.offset = [24, 64]
  liteGraphCanvas.setDirty(true, true)
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
  liteGraphCanvas.ds.scale = clampLiteGraphUiScale(previousUiScale) * liteGraphPixelRatio
  liteGraphCanvas.setDirty(true, true)
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

function registerLiteGraphNodeSpecs() {
  for (const spec of nodeSpecs.value) {
    if (registeredLiteGraphTypes.has(spec.type)) continue
    if ((LiteGraph as unknown as { registered_node_types?: Record<string, unknown> }).registered_node_types?.[spec.type]) {
      registeredLiteGraphTypes.add(spec.type)
      continue
    }

    const accent = categoryColor(spec.category)
    const softAccent = categorySoftColor(spec.category)
    class ElysPipelineNode extends LGraphNode {
      constructor() {
        super(spec.title)
        this.title = spec.title
        this.properties = defaultParams(spec)
        this.size = graphNodeSize(spec)
        this.color = '#D4DDE8'
        this.boxcolor = accent
        this.bgcolor = '#FFFFFF'
        this.shape = LiteGraph.ROUND_SHAPE
        this.resizable = true
        for (const input of spec.inputs || []) {
          const color = portTypeColor(input.type)
          this.addInput(input.name, liteGraphPortType(input.type), {
            label: input.label || input.name,
            color_on: color,
            color_off: withAlpha(color, 0.36),
            shape: LiteGraph.CIRCLE_SHAPE,
          })
        }
        for (const output of spec.outputs || []) {
          const color = portTypeColor(output.type)
          this.addOutput(output.name, liteGraphPortType(output.type), {
            label: output.label || output.name,
            color_on: color,
            color_off: withAlpha(color, 0.36),
            shape: LiteGraph.CIRCLE_SHAPE,
          })
        }
      }

      getTitle() {
        return compactNodeTitle(String(this.title || spec.title || spec.type || 'Node'))
      }

      onDrawTitleBar(ctx: CanvasRenderingContext2D, titleHeight: number, size: [number, number]) {
        const gradient = ctx.createLinearGradient(0, -titleHeight, size[0], 0)
        gradient.addColorStop(0, softAccent)
        gradient.addColorStop(0.64, '#FFFFFF')
        gradient.addColorStop(1, '#F8FAFC')
        ctx.fillStyle = gradient
        ctx.beginPath()
        ctx.roundRect(0, -titleHeight, size[0] + 1, titleHeight, [6, 6, 0, 0])
        ctx.fill()

        drawNodeAccentBar(ctx, accent, size[0], size[1], titleHeight)

        ctx.strokeStyle = '#D9E0EA'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(0, -0.5)
        ctx.lineTo(size[0], -0.5)
        ctx.stroke()
      }

      onDrawTitleBox(ctx: CanvasRenderingContext2D, titleHeight: number) {
        const x = titleHeight * 0.5 - 1
        const y = -titleHeight * 0.5
        ctx.fillStyle = '#FFFFFF'
        ctx.strokeStyle = withAlpha(accent, 0.42)
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(x, y, 6, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
        ctx.fillStyle = accent
        ctx.beginPath()
        ctx.arc(x, y, 3, 0, Math.PI * 2)
        ctx.fill()
      }

      onDrawBackground(ctx: CanvasRenderingContext2D) {
        const node = this as unknown as LiteGraphNode
        const [width, height] = node.size as [number, number]
        ctx.fillStyle = '#FFFFFF'
        ctx.fillRect(4, 0, width - 4, height)

        ctx.fillStyle = 'rgba(248, 250, 252, 0.92)'
        ctx.fillRect(4, 0, width - 4, 1)
      }

      onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this as unknown as LiteGraphNode
        const [width, height] = node.size as [number, number]
        const titleHeight = LiteGraph.NODE_TITLE_HEIGHT
        const selected = Boolean(node.is_selected)
        const hovered = Boolean(node.mouseOver)

        ctx.save()
        if (selected) {
          ctx.strokeStyle = withAlpha(accent, 0.22)
          ctx.lineWidth = 3
          ctx.beginPath()
          ctx.roundRect(-2, -titleHeight - 2, width + 5, height + titleHeight + 5, [8])
          ctx.stroke()
        }

        ctx.strokeStyle = selected ? accent : hovered ? withAlpha(accent, 0.72) : '#D4DDE8'
        ctx.lineWidth = selected ? 1.6 : hovered ? 1.25 : 1
        ctx.beginPath()
        ctx.roundRect(0.5, -titleHeight + 0.5, width, height + titleHeight, [6])
        ctx.stroke()

        if (selected || hovered) {
          drawNodeAccentBar(ctx, selected ? accent : withAlpha(accent, 0.72), width, height, titleHeight)
        }

        const nodeId = getLiteGraphNodeId(node)
        const job = jobForNodeId(nodeId)
        if (job) drawNodeStatusBadge(ctx, width, job.status)

        // 保存状态指示胶囊：直接看 LiteGraph 实际链接，不依赖 definition.value.graph（避开 sync 时序问题）。
        //
        // 规则：
        // - LoadData 等 source 节点 → 不画（在 NO_SAVE_ICON_NODE_TYPES 里）
        // - 必须能从某个 LoadData 节点顺流走到本节点（BFS 可达） —— 即使本节点有 input link，
        //   但若其上游链路没接 LoadData，也不画。这是 task #71 的核心修复（task #65 漏判）。
        // - 节点 outputs 全部未连接 → leaf → 画（默认 retention='current'）
        // - 节点有 output 连接 → intermediate → 不画（默认 cached）
        // - 用户在 params 里显式设了 retention：
        //     'current' / 'pinned' → 强制画（仅当可达）
        //     'cached' / 'none'    → 强制不画
        //     其它/留空            → 走拓扑默认
        // - 颜色用 closure 里的 accent（= categoryColor(spec.category)）
        const nodeType = String((node as { type?: unknown }).type || '')
        if (nodeType && !NO_SAVE_ICON_NODE_TYPES.has(nodeType)) {
          // 先用 BFS 判 LoadData 可达性 —— 不可达就一定不画（用户 override 也无效）
          const reachableSet = liteGraphReachableFromLoadData(liteGraph)
          if (reachableSet.has(nodeId)) {
            const params = (node.properties || {}) as Record<string, unknown>
            const override = String((params.retention as string | undefined) || '').trim().toLowerCase()

            let shouldDraw = false
            if (override === 'current' || override === 'pinned') {
              shouldDraw = true
            } else if (override === 'cached' || override === 'none') {
              shouldDraw = false
            } else {
              // 拓扑默认：可达 + 是 leaf（无 output 连接）
              const outputs = (node as unknown as { outputs?: Array<{ links?: unknown } | null> }).outputs || []
              const isLeaf = !outputs.some((o) => Array.isArray(o?.links) && (o.links as unknown[]).length > 0)
              shouldDraw = isLeaf
            }

            if (shouldDraw) {
              drawNodeSaveIcon(ctx, width, height, accent)
            }
          }
        }
        ctx.restore()
      }
    }

    const nodeConstructor = ElysPipelineNode as ElysPipelineNodeConstructor
    nodeConstructor.title = spec.title
    nodeConstructor.desc = spec.description || spec.title
    ;(ElysPipelineNode as unknown as Record<string, unknown>).title_color = softAccent
    ;(ElysPipelineNode as unknown as Record<string, unknown>).title_text_color = '#1F2A37'
    ;(ElysPipelineNode as unknown as Record<string, unknown>).bgcolor = '#FFFFFF'
    ;(ElysPipelineNode as unknown as Record<string, unknown>).color = '#D4DDE8'
    LiteGraph.registerNodeType(spec.type, ElysPipelineNode)
    registeredLiteGraphTypes.add(spec.type)
  }
}

function graphNodeSize(spec: NodeSpec): [number, number] {
  const uiSize = spec.ui?.default_size || spec.ui?.size
  if (Array.isArray(uiSize) && uiSize.length >= 2) {
    const width = Number(uiSize[0])
    const height = Number(uiSize[1])
    if (Number.isFinite(width) && Number.isFinite(height)) return [Math.max(NODE_CARD_WIDTH, width), Math.max(NODE_CARD_MIN_HEIGHT, height)]
  }
  const portRows = Math.max(spec.inputs?.length || 0, spec.outputs?.length || 0)
  return [NODE_CARD_WIDTH, Math.max(NODE_CARD_MIN_HEIGHT, 78 + portRows * 26)]
}

function getLiteGraphNodeId(node: LiteGraphNode | LGraphNode | null | undefined) {
  const liteNode = node as LiteGraphNode | null | undefined
  const fromProperty = liteNode?.properties?.[LITEGRAPH_NODE_ID_PROP]
  return String(liteNode?.elysNodeId || fromProperty || liteNode?.id || '')
}

function setLiteGraphNodeId(node: LiteGraphNode, id: string) {
  node.elysNodeId = id
  node.properties = {
    ...(node.properties || {}),
    [LITEGRAPH_NODE_ID_PROP]: id,
  }
}

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
  liteGraphCanvas.setDirty(true, true)
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

function formatParamValue(prop: NodeProperty) {
  const value = selectedNode.value?.params[prop.name]
  if (prop.type === 'channel_list' && Array.isArray(value)) return value.join(', ')
  return value ?? ''
}

function handleParamInput(prop: NodeProperty, event: Event) {
  const value = (event.target as HTMLInputElement | HTMLSelectElement).value
  updateSelectedParam(prop, value)
}

function handleParamCheckbox(prop: NodeProperty, event: Event) {
  updateSelectedParam(prop, (event.target as HTMLInputElement).checked)
}

function updateSelectedParam(prop: NodeProperty, rawValue: unknown) {
  if (!selectedNode.value) return
  selectedNode.value.params = {
    ...selectedNode.value.params,
    [prop.name]: coerceParamValue(prop, rawValue),
  }
  updateLiteGraphNode(selectedNode.value)
  markDirty()
}

function coerceParamValue(prop: NodeProperty, rawValue: unknown) {
  if (prop.type === 'number') {
    const value = Number(rawValue)
    return Number.isFinite(value) ? value : null
  }
  if (prop.type === 'integer') {
    const value = Number(rawValue)
    return Number.isFinite(value) ? Math.trunc(value) : null
  }
  if (prop.type === 'boolean') return Boolean(rawValue)
  if (prop.type === 'channel_list') {
    return String(rawValue || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
  }
  if (prop.type === 'select') {
    const option = prop.options?.find((item) => String(item.value) === String(rawValue))
    return option ? option.value : rawValue
  }
  return rawValue
}

function handleNodeTitleInput(event: Event) {
  if (!selectedNode.value) return
  selectedNode.value.title = (event.target as HTMLInputElement).value
  updateLiteGraphNode(selectedNode.value)
  markDirty()
}

function quickConnectUpstream(upstreamId: string) {
  if (!upstreamId) return
  upstreamNodeId.value = upstreamId
  connectUpstreamToSelected()
}

function upstreamNodeLabel(nodeId: string): string {
  const node = definition.value.graph.nodes.find((item) => item.id === nodeId)
  if (!node) return nodeId
  return node.title || specForNode(node)?.title || node.id
}

function connectUpstreamToSelected() {
  if (!selectedNode.value || !upstreamNodeId.value || !selectedNodeSpec.value) return
  const upstream = definition.value.graph.nodes.find((node) => node.id === upstreamNodeId.value)
  const upstreamSpec = specForNode(upstream)
  if (!upstream || !upstreamSpec) return

  const input = selectedNodeSpec.value.inputs[0]
  const output = upstreamSpec.outputs.find((port) => !input || portTypesCompatible(port.type, input.type)) || upstreamSpec.outputs[0]
  if (!input || !output) {
    statusMessage.value = '该节点缺少可连接端口'
    return
  }

  const exists = definition.value.graph.links.some(
    (link) => link.from.node === upstream.id && link.to.node === selectedNode.value?.id && link.to.port === input.name,
  )
  if (exists) {
    statusMessage.value = '该连接已存在'
    return
  }

  const upstreamGraphNode = findLiteGraphNode(upstream.id)
  const selectedGraphNode = findLiteGraphNode(selectedNode.value.id)
  if (upstreamGraphNode && selectedGraphNode) {
    const outputSlot = Math.max(0, upstreamGraphNode.findOutputSlot(output.name))
    const inputSlot = Math.max(0, selectedGraphNode.findInputSlot(input.name))
    upstreamGraphNode.connect(outputSlot, selectedGraphNode, inputSlot)
    upstreamNodeId.value = ''
    syncDefinitionFromLiteGraph(true)
    return
  }

  definition.value.graph.links.push({
    id: `l_${Date.now().toString(36)}_${definition.value.graph.links.length + 1}`,
    from: { node: upstream.id, port: output.name },
    to: { node: selectedNode.value.id, port: input.name },
  })
  upstreamNodeId.value = ''
  syncDefinitionToLiteGraph()
  markDirty()
}

function removeLink(linkId: string) {
  definition.value.graph.links = definition.value.graph.links.filter((link) => link.id !== linkId)
  syncDefinitionToLiteGraph()
  markDirty()
}

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
  padding: 12px;
  border-left: 1px solid var(--c-border);
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.04);
  min-width: 320px;
  max-width: 800px;
}

.inspector.is-hidden {
  transform: translateX(100%);
  box-shadow: none;
  pointer-events: none;
}

/* 抽屉拖拽手柄 */
.drawer-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: ew-resize;
  background: transparent;
  z-index: 40;
  transition: background 0.15s;
}

.drawer-handle--right {
  right: -3px;
}

.drawer-handle--left {
  left: -3px;
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

.node-template__type {
  font-size: 10px;
  font-family: var(--ff-mono);
  color: var(--c-text-3);
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

.artifact-list {
  display: grid;
  gap: 6px;
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

.property-list,
.connections {
  display: flex;
  flex-direction: column;
  gap: 10px;
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
