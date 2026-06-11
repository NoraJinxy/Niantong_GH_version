<template>
  <!-- 版心对齐主页 .hero__inner(1200)：与 Dashboard 同款覆盖，--content-w=1200 + --page-pad-x=0，内容与主页齐边。仅本页生效。 -->
  <WorkbenchShell active-key="datasets" active-top-key="datasets" :show-sidebar="false" :narrow="true" :style="{ '--content-w': '1200px', '--page-pad-x': '0px' }">
    <div class="page__header dataset-page__header">
      <div>
        <h1 class="page__title">数据集管理</h1>
        <p class="page__subtitle">
          选择数据集，查看导入状态和文件摘要，再继续导入或进入后续处理。处理工作空间只作为导入、质控和运行上下文。
        </p>
      </div>
      <div class="dataset-page__actions">
        <!-- Phase 3 (docs_v2/3-25): 管理员审核入口 -->
        <RouterLink
          v-if="isAdmin"
          class="btn btn--ghost admin-link"
          to="/admin/withdrawals"
          title="审核数据集负责人提交的撤回申请"
        >
          <AppIcon name="alert" :size="15" />
          撤回审核
        </RouterLink>
        <RouterLink
          v-if="isAdmin"
          class="btn btn--ghost admin-link"
          to="/admin/publicizations"
          title="审核数据集负责人提交的转公开申请（shared → public）"
        >
          <AppIcon name="observe" :size="15" />
          转公开审核
        </RouterLink>
        <button class="btn btn--primary" type="button" @click="openCreatePanel">
          <AppIcon name="plus" :size="15" />
          新建数据集
        </button>
      </div>
    </div>

    <!-- #15：页面级成功提示（在详情面板之外，删除后选中清空、面板卸载仍可见） -->
    <div v-if="pageNotice" class="inline-success" role="status" style="margin-bottom: 16px;">{{ pageNotice }}</div>

    <!-- UI Phase (docs_v2/6-05) 统一顶部 stat 条 - 仅展示用户关心的 4 张数字卡 -->
    <section class="page-stat-strip" aria-label="数据集概览">
      <article class="page-stat">
        <span class="page-stat__label">数据集总数</span>
        <strong class="page-stat__value">{{ assetStats.total }}</strong>
      </article>
      <!-- 6-05 §6.2 + B 方案：按可见范围分桶，零值不渲染 -->
      <article v-if="assetStats.private" class="page-stat">
        <span class="page-stat__label">私有</span>
        <strong class="page-stat__value">{{ assetStats.private }}</strong>
      </article>
      <article v-if="assetStats.shared" class="page-stat">
        <span class="page-stat__label">共享</span>
        <strong class="page-stat__value">{{ assetStats.shared }}</strong>
      </article>
      <article v-if="assetStats.public" class="page-stat">
        <span class="page-stat__label">公开</span>
        <strong class="page-stat__value">{{ assetStats.public }}</strong>
      </article>
    </section>

    <section v-if="usesShortcutStudy" class="dataset-shortcut">
      <AppIcon name="studies" :size="18" />
      <div>
        <strong>当前处于处理工作空间快捷入口</strong>
        <span>上传目标会关联到 {{ shortcutStudyLabel }}；普通入口会自动生成处理工作空间。</span>
      </div>
    </section>

    <section class="dataset-workbench">
      <aside class="dataset-catalog" aria-label="数据集目录">
        <div class="dataset-catalog__head">
          <div>
            <h2>数据集</h2>
            <p>{{ filteredDatasetAssets.length }} / {{ datasetAssets.length }}</p>
          </div>
          <button class="icon-btn" type="button" title="刷新" @click="reloadAll">
            <AppIcon name="restore" :size="15" />
          </button>
        </div>

        <div class="dataset-catalog__filters">
          <label class="dataset-search">
            <AppIcon name="search" :size="15" />
            <input v-model.trim="assetSearch" type="search" placeholder="搜索名称或 code" />
          </label>
          <select v-model="assetVisibilityFilter" class="input">
            <option value="all">全部可见范围</option>
            <option value="private">私有</option>
            <option value="shared">共享</option>
            <option value="public">公开</option>
          </select>
        </div>

        <div v-if="isLoadingAssets" class="dataset-list-empty">正在读取数据集...</div>
        <div v-else-if="!datasetAssets.length" class="dataset-list-empty">
          还没有数据集。请先新建一个数据集，然后导入 EEG 原始数据。
        </div>
        <div v-else-if="!filteredDatasetAssets.length" class="dataset-list-empty">
          没有匹配的数据集。
        </div>
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
              这是新的数据资产，不会修改左侧目录中的已有数据集。
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
          </div>
        </div>

        <form v-if="activePanel === 'create'" class="dataset-create-form" @submit.prevent="bootstrapDataset">
          <div class="dataset-create-intro">
            <div>
              <span class="section-kicker">创建流程</span>
              <h3>定义数据集后直接导入</h3>
              <p>创建完成后自动准备处理工作空间，上传区会切到新数据集。</p>
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
                <span class="field__hint">默认 primary；仅在同一处理工作空间关联多个数据集时需要调整。</span>
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

          <section v-if="activeTab === 'overview'" class="dataset-tab-panel" aria-label="数据集概览">
            <div class="dataset-profile">
              <div>
                <span class="section-kicker">数据集概览</span>
                <h3>{{ selectedDatasetAsset.name }}</h3>
                <p>{{ datasetDecisionSummary.message }}</p>
              </div>
              <div class="dataset-profile__badges">
                <!-- 数据集生命周期 v2（3-25）：可见范围与发布解耦。徽章只读展示可见范围（私有/共享/公开）；
                     负责人可显式「开放」——只升不降（私有→共享→公开，可跳级），无降级入口（不可逆释放，类比论文发表）。 -->
                <span
                  class="badge"
                  :class="getVisibilityClass(selectedDatasetAsset.visibility)"
                  :title="visibilityHint(selectedDatasetAsset.visibility)"
                >
                  {{ getVisibilityLabel(selectedDatasetAsset.visibility) }}
                </span>
                <!-- 仅负责人可开放；需至少 1 个已发布版本；只能升级 -->
                <button
                  v-if="canOpenVisibility('shared')"
                  class="btn btn--sm btn--ghost"
                  type="button"
                  title="把可见范围开放为「共享」（邀请制授权用户可用）。开放不可逆。"
                  @click="openVisibilityModalFor('shared')"
                >
                  <AppIcon name="network" :size="14" />
                  开放为共享
                </button>
                <button
                  v-if="canOpenVisibility('public')"
                  class="btn btn--sm btn--ghost"
                  type="button"
                  title="申请把可见范围开放为「公开」（全平台注册用户可用）。先审后开、不可逆。"
                  @click="openVisibilityModalFor('public')"
                >
                  <AppIcon name="observe" :size="14" />
                  申请公开
                </button>
              </div>
            </div>

            <!-- Phase 3 (docs_v2/3-25): 生命周期操作反馈 -->
            <div v-if="lifecycleMessage" class="inline-success" style="margin-top: 10px;">
              {{ lifecycleMessage }}
            </div>

            <!-- Phase 3 (docs_v2/3-25): 版本与发布卡片 -->
            <section v-if="currentVersion" class="dataset-version-card" :class="datasetVersionStateClass(currentVersion.state)">
              <div class="dataset-version-card__header">
                <div>
                  <span class="section-kicker">当前版本</span>
                  <strong>{{ formatVersionLabel(currentVersion.version_label) }}</strong>
                  <span class="version-state-pill" :class="datasetVersionStateClass(currentVersion.state)">
                    {{ datasetVersionStateLabel(currentVersion.state) }}
                  </span>
                </div>
                <div class="dataset-version-card__actions">
                  <button
                    v-if="currentVersion.state === 'unpublished'"
                    class="btn btn--primary"
                    type="button"
                    @click="openPublishModal"
                  >
                    发布版本
                  </button>
                  <button
                    v-else-if="currentVersion.state === 'published'"
                    class="btn btn--ghost"
                    type="button"
                    @click="openWithdrawModal"
                  >
                    申请撤回
                  </button>
                  <!-- 紧急下架仅 admin 可见（3-25 §6.4：superadmin 另作平台治理，不参与数据集生命周期），跳过审核，事后补审计 -->
                  <button
                    v-if="isAdmin && (currentVersion.state === 'published' || currentVersion.state === 'withdraw_requested')"
                    class="btn btn--danger"
                    type="button"
                    title="跳过审核流程直接撤下版本（仅适用于被试隐私泄露 / 法律强制下架等紧急场景）"
                    @click="openEmergencyTakedownModal"
                  >
                    紧急下架
                  </button>
                </div>
              </div>
              <p v-if="currentVersion.state === 'unpublished'" class="dataset-version-card__hint">
                此版本仅主研究项可关联使用。发布后才能被其他研究项引用，且发布后不可修改文件（要改请开新版本）。发布≠分享：发布只冻结并铸 DOI，可见范围默认保持私有，是否对外开放由你单独决定。
              </p>
              <p v-else-if="currentVersion.state === 'published'" class="dataset-version-card__hint">
                已发布版本不可修改。如需变更内容请创建新的未发布版本；如需下架请提交撤回申请由管理员审核。
              </p>
              <p v-else-if="currentVersion.state === 'withdraw_requested'" class="dataset-version-card__hint">
                撤回申请审核中。审核通过后此版本将转为已撤回（终态），已有关联和引用会保留但禁止新引用。
              </p>
              <p v-else-if="currentVersion.state === 'withdrawn'" class="dataset-version-card__hint">
                此版本已撤回。如需继续工作请创建新的未发布版本（前向演进，不可回滚）。
              </p>
              <dl class="dataset-version-card__meta">
                <div>
                  <dt>质控状态</dt>
                  <dd>{{ qaStatusLabel(currentVersion.qa_status) }}</dd>
                </div>
                <div v-if="currentVersion.published_at">
                  <dt>发布时间</dt>
                  <dd>{{ formatDate(currentVersion.published_at) }}</dd>
                </div>
                <div v-if="currentVersion.version_doi">
                  <dt>学术 DOI</dt>
                  <dd>
                    <button class="doi-copy-btn" type="button" @click.prevent="copyDoi(currentVersion.version_doi!)">
                      已注册 · 复制
                    </button>
                  </dd>
                </div>
                <div v-if="selectedDatasetAsset.primary_study_id">
                  <dt>主研究项</dt>
                  <dd>
                    <RouterLink :to="`/studies/${selectedDatasetAsset.primary_study_id}`" class="dataset-primary-link">
                      查看研究项 →
                    </RouterLink>
                  </dd>
                </div>
              </dl>
            </section>

            <!-- Phase 3 (docs_v2/3-25) C: 版本时间线 -->
            <section v-if="sortedVersions.length" class="version-timeline" aria-label="版本时间线">
              <header class="version-timeline__head">
                <div>
                  <span class="section-kicker">版本历史</span>
                  <strong>{{ sortedVersions.length }} 个版本</strong>
                </div>
                <button
                  v-if="canCreateNewDraft"
                  class="btn btn--ghost"
                  type="button"
                  :disabled="isCreatingDraft"
                  @click="createNewDraft"
                >
                  {{ isCreatingDraft ? '创建中...' : '+ 新建未发布版本' }}
                </button>
              </header>
              <ol class="version-timeline__list">
                <li
                  v-for="version in sortedVersions"
                  :key="version.id"
                  class="version-timeline__item"
                  :class="[datasetVersionStateClass(version.state), { 'is-current': version.id === currentVersion?.id }]"
                >
                  <div class="version-timeline__label">
                    <strong>{{ formatVersionLabel(version.version_label) }}</strong>
                    <span class="version-state-pill" :class="datasetVersionStateClass(version.state)">
                      {{ datasetVersionStateLabel(version.state) }}
                    </span>
                    <span v-if="version.id === currentVersion?.id" class="current-marker">默认</span>
                  </div>
                  <div class="version-timeline__center">
                    <span v-if="version.published_at" class="version-timeline__time">发布于 {{ formatDate(version.published_at) }}</span>
                    <span v-else-if="version.created_at" class="version-timeline__time">创建于 {{ formatDate(version.created_at) }}</span>
                    <span v-if="version.version_doi" class="mono">{{ version.version_doi }}</span>
                  </div>
                  <!-- Phase 3 C+ (docs_v2/3-25): 每行的快捷操作 -->
                  <div class="version-timeline__actions">
                    <button
                      v-if="version.state === 'unpublished'"
                      class="btn btn--primary btn--small"
                      type="button"
                      @click="openPublishModalForVersion(version)"
                    >
                      发布
                    </button>
                    <button
                      v-else-if="version.state === 'published'"
                      class="btn btn--ghost btn--small"
                      type="button"
                      @click="openWithdrawModalForVersion(version)"
                    >
                      申请撤回
                    </button>
                    <!-- 规则 4：已发布资产上的 v+1 未发布版本可单独丢弃（仅负责人） -->
                    <button
                      v-if="canDiscardVersion(version)"
                      class="btn btn--danger btn--small"
                      type="button"
                      title="丢弃这个未发布版本（不影响已发布历史）"
                      @click="openDiscardVersionModal(version)"
                    >
                      丢弃
                    </button>
                  </div>
                </li>
              </ol>
              <p v-if="canCreateNewDraftBlockedReason" class="version-timeline__hint">
                {{ canCreateNewDraftBlockedReason }}
              </p>
            </section>

            <!-- 规则 7：邀请制授权用户面板（仅负责人、仅共享态可管理）。
                 共享 = 负责人按用户授权（dataset_members）；被授权者可读、可把数据集关联进自己的研究项。 -->
            <section v-if="showMemberPanel" class="dataset-member-panel" aria-label="授权用户">
              <header class="dataset-member-panel__head">
                <div>
                  <span class="section-kicker">授权用户</span>
                  <strong>{{ datasetMembers.length }} 位已授权</strong>
                  <p>共享数据集为邀请制：仅你授权的用户可读、可把它关联到自己的研究项。授权某用户即信任其及其协作研究项。</p>
                </div>
                <button
                  class="btn btn--sm"
                  type="button"
                  :disabled="isLoadingMembers"
                  @click="loadSelectedAssetMembers"
                >
                  <AppIcon name="restore" :size="14" />
                  刷新
                </button>
              </header>

              <form class="dataset-member-add" @submit.prevent="submitAddMember">
                <input
                  v-model.trim="memberAddUserId"
                  class="input"
                  type="text"
                  placeholder="用户名 / 用户 ID"
                  :disabled="isAddingMember"
                />
                <button class="btn btn--primary btn--sm" type="submit" :disabled="isAddingMember || !memberAddUserId">
                  <span v-if="isAddingMember" class="spinner"></span>
                  {{ isAddingMember ? '授权中...' : '授权' }}
                </button>
              </form>
              <div v-if="memberError" class="inline-error">{{ memberError }}</div>

              <div v-if="isLoadingMembers" class="dataset-list-empty">正在读取授权用户...</div>
              <div v-else-if="!datasetMembers.length" class="dataset-list-empty">
                还没有授权任何用户。在上方输入用户 ID 即可授权。
              </div>
              <ul v-else class="dataset-member-list">
                <li v-for="member in datasetMembers" :key="member.id">
                  <div class="dataset-member-identity">
                    <strong>{{ member.full_name || member.username || member.user_id }}</strong>
                    <small v-if="member.username && (member.full_name || member.username !== member.user_id)">{{ member.username }}</small>
                    <small class="mono">{{ member.user_id }}</small>
                  </div>
                  <span class="dataset-member-time" v-if="member.granted_at">授权于 {{ formatDate(member.granted_at) }}</span>
                  <button
                    class="btn btn--sm btn--danger"
                    type="button"
                    :disabled="removingMemberId === member.user_id"
                    @click="revokeMember(member)"
                  >
                    {{ removingMemberId === member.user_id ? '取消中...' : '取消授权' }}
                  </button>
                </li>
              </ul>
            </section>

            <div class="dataset-decision-panel" :class="datasetDecisionSummary.className">
              <div>
                <span>当前判断</span>
                <strong>{{ datasetDecisionSummary.title }}</strong>
                <p>{{ datasetDecisionSummary.detail }}</p>
              </div>
              <div>
                <span>后续处理</span>
                <strong>{{ datasetDecisionSummary.processing }}</strong>
                <p>{{ datasetDecisionSummary.processingHint }}</p>
              </div>
            </div>

            <!-- UI Phase (docs_v2/6-05) L1: 数据概要 - 用户最关心的"这数据是什么" -->
            <section class="data-overview-card">
              <header class="data-overview-card__head">
                <span class="section-kicker">数据概要</span>
                <span v-if="selectedDatasetAsset.description" class="data-overview-card__desc">
                  {{ selectedDatasetAsset.description }}
                </span>
              </header>
              <!-- 6-05：数据概要四件套 被试/记录数/任务/时长（最近导入移到下方说明，不占四格） -->
              <div class="data-overview-card__grid">
                <div class="data-stat">
                  <IconLine class="data-stat__icon" name="users" :size="20" />
                  <div>
                    <strong>{{ selectedDatasetAsset.subject_count ?? 0 }}</strong>
                    <small>名被试</small>
                  </div>
                </div>
                <div class="data-stat">
                  <IconLine class="data-stat__icon" name="list" :size="20" />
                  <div>
                    <strong>{{ selectedDatasetAsset.recording_count ?? 0 }}</strong>
                    <small>条采集记录</small>
                  </div>
                </div>
                <div class="data-stat">
                  <IconLine class="data-stat__icon" name="clipboard" :size="20" />
                  <div>
                    <strong>{{ (selectedDatasetAsset.task_codes ?? []).length || 0 }}</strong>
                    <small>种采集任务</small>
                  </div>
                </div>
                <div class="data-stat" title="全部采集记录时长之和">
                  <IconLine class="data-stat__icon" name="clock" :size="20" />
                  <div>
                    <strong>{{ formatDuration(selectedDatasetAsset.total_duration_seconds ?? 0) }}</strong>
                    <small>总采集时长</small>
                  </div>
                </div>
              </div>
              <p v-if="selectedDatasetAsset.last_imported_at" class="data-overview-card__imported">
                最近导入：{{ formatRelative(selectedDatasetAsset.last_imported_at) }}
              </p>
              <div v-if="(selectedDatasetAsset.task_codes ?? []).length" class="data-overview-card__tasks">
                <span class="data-overview-card__tasks-label">任务列表</span>
                <span
                  v-for="task in (selectedDatasetAsset.task_codes ?? [])"
                  :key="task"
                  class="task-chip"
                >{{ task }}</span>
              </div>
            </section>

            <div class="dataset-target-panel" :class="{ 'is-ready': isTargetForSelectedAsset }">
              <div>
                <span class="section-kicker">下一步</span>
                <h3>{{ isTargetForSelectedAsset ? '可以继续导入' : '先准备导入目标' }}</h3>
                <p>
                  {{ isTargetForSelectedAsset
                    ? '该数据集已经绑定处理工作空间，可进入导入页继续追加原始数据。'
                    : '系统会自动创建或复用处理工作空间，并把该数据集设为导入目标。'
                  }}
                </p>
              </div>
              <button
                v-if="isTargetForSelectedAsset"
                class="btn btn--primary"
                type="button"
                @click="activeTab = 'import'"
              >
                进入导入
              </button>
              <button
                v-else
                class="btn btn--primary"
                type="button"
                :disabled="!canMountSelected"
                @click="mountExistingDatasetAsset"
              >
                <span v-if="isBootstrapping" class="spinner"></span>
                准备导入目标
              </button>
            </div>

            <div v-if="bootstrapError" class="inline-error">{{ bootstrapError }}</div>
            <div v-if="bootstrapSuccess" class="inline-success">{{ bootstrapSuccess }}</div>

            <!-- UI Phase (docs_v2/6-05) L3: 技术信息折叠区 - 平台内部对象、文件统计、ID、DOI 字符串 -->
            <TechnicalFold title="技术信息" hint="平台内部记录，普通研究员可忽略">
              <dl>
                <div>
                  <dt>数据集编码</dt>
                  <dd>{{ selectedDatasetAsset.code }}</dd>
                </div>
                <div>
                  <dt>数据集 ID</dt>
                  <dd>{{ selectedDatasetAsset.id }}</dd>
                </div>
                <div v-if="selectedDatasetAsset.primary_study_id">
                  <dt>主研究项 ID</dt>
                  <dd>{{ selectedDatasetAsset.primary_study_id }}</dd>
                </div>
                <div v-if="selectedDatasetAsset.concept_doi">
                  <dt>Concept DOI</dt>
                  <dd>{{ selectedDatasetAsset.concept_doi }}</dd>
                </div>
                <div v-if="currentVersion?.version_doi">
                  <dt>Version DOI</dt>
                  <dd>{{ currentVersion.version_doi }}</dd>
                </div>
                <div>
                  <dt>文件总数</dt>
                  <dd>{{ selectedAssetFileStats.total }}</dd>
                </div>
                <div>
                  <dt>原始上传文件</dt>
                  <dd>{{ selectedAssetFileStats.original }}</dd>
                </div>
                <div>
                  <dt>标准 FIF 文件</dt>
                  <dd>{{ selectedAssetFileStats.canonicalFif }}</dd>
                </div>
                <div>
                  <dt>存储占用</dt>
                  <dd>{{ formatFileSize(selectedAssetFileStats.totalSize) }}</dd>
                </div>
                <div>
                  <dt>状态枚举</dt>
                  <dd>{{ selectedDatasetAsset.status }} / {{ selectedDatasetAsset.visibility }}</dd>
                </div>
                <div>
                  <dt>创建 / 更新</dt>
                  <dd>{{ formatDate(selectedDatasetAsset.created_at) }} / {{ formatDate(selectedDatasetAsset.updated_at) }}</dd>
                </div>
              </dl>
            </TechnicalFold>

            <!-- 规则 4：纯未发布资产（无任何已发布/已撤回版本）才可整体删除，仅负责人。已发布历史一律不可删、只能撤回。 -->
            <section v-if="canDeleteAsset" class="dataset-danger-zone" aria-label="危险操作">
              <div>
                <span class="section-kicker section-kicker--danger">危险操作</span>
                <strong>删除整个数据集</strong>
                <p>该数据集所有版本均为未发布（从未发布、且无撤回审核中 / 已撤回记录），可整体永久删除（文件、版本、记录一并清除，不可恢复）。一旦发布过版本就只能撤回、无法删除。</p>
              </div>
              <button class="btn btn--danger" type="button" @click="openDeleteAssetModal">
                <AppIcon name="trash" :size="14" />
                删除数据集
              </button>
            </section>
          </section>

          <section v-else-if="activeTab === 'import'" ref="uploadSectionRef" class="dataset-tab-panel" aria-label="导入数据">
            <div class="dataset-target-panel" :class="{ 'is-ready': isTargetForSelectedAsset }">
              <div>
                <span class="section-kicker">导入目标</span>
                <h3>{{ isTargetForSelectedAsset ? '导入目标已准备好' : '尚未准备导入目标' }}</h3>
                <p>
                  {{ isTargetForSelectedAsset
                    ? '继续选择 EEG 原始数据并提交，系统会写入当前数据集的 working 版本。'
                    : '点击后系统会自动创建或复用处理工作空间，并把该数据集设为导入目标。'
                  }}
                </p>
              </div>
              <button
                class="btn btn--primary"
                type="button"
                :disabled="!canMountSelected && !isTargetForSelectedAsset"
                @click="isTargetForSelectedAsset ? scrollToUploadPanel() : mountExistingDatasetAsset()"
              >
                <span v-if="isBootstrapping" class="spinner"></span>
                {{ isTargetForSelectedAsset ? '继续导入' : '准备导入目标' }}
              </button>
            </div>

            <details class="dataset-advanced-settings">
              <summary>高级设置</summary>
              <label class="dataset-mount-field">
                <span>关联名称</span>
                <input
                  v-model.trim="mountName"
                  class="input"
                  placeholder="primary"
                  :disabled="isBootstrapping"
                  @input="clearBootstrapResult"
                />
                <small>默认 primary；通常不需要调整。</small>
              </label>
            </details>

            <div v-if="targetSummary" class="dataset-target-summary">
              <div>
                <span>数据集</span>
                <strong>{{ targetSummary.datasetAssetName }}</strong>
              </div>
              <div>
                <span>处理工作空间</span>
                <strong>{{ formatProcessingWorkspaceName(targetSummary.studyName) }}</strong>
              </div>
              <div>
                <span>导入状态</span>
                <strong>已准备好</strong>
              </div>
            </div>

            <div v-if="bootstrapError" class="inline-error">{{ bootstrapError }}</div>
            <div v-if="bootstrapSuccess" class="inline-success">{{ bootstrapSuccess }}</div>

            <div ref="uploadPanelRef" class="dataset-upload-panel-anchor">
              <BidsUploadPanel
                :study-id="uploadContext?.studyId || ''"
                :study-name="uploadContext?.studyName || undefined"
                :dataset-asset-id="uploadContext?.datasetAssetId || ''"
                :dataset-asset-name="uploadContext?.datasetAssetName || undefined"
                :mount-name="uploadContext?.mountName || ''"
                :upload-context="uploadContext || undefined"
                @uploaded="handleUploaded"
              />
            </div>
          </section>

          <section v-else-if="activeTab === 'records'" class="dataset-tab-panel" aria-label="采集记录">
            <div class="dataset-record-panel">
              <div class="dataset-panel-head">
                <div>
                  <h3>采集记录</h3>
                  <p>按被试 / 任务组织采集记录；文件列表仅在展开详情中查看。</p>
                </div>
                <button
                  class="btn btn--sm"
                  type="button"
                  :disabled="isLoadingRecordings || !recordsStudyContext"
                  @click="loadSelectedAssetRecordings"
                >
                  <AppIcon name="restore" :size="14" />
                  刷新
                </button>
              </div>

              <div class="dataset-record-stats">
                <div>
                  <span>采集记录数</span>
                  <strong>{{ recordingStats.total }}</strong>
                </div>
                <div>
                  <span>已生成标准 FIF</span>
                  <strong>{{ recordingStats.withCanonicalFif }}</strong>
                </div>
                <div>
                  <span>质控通过</span>
                  <strong>{{ recordingStats.qcPassed }}</strong>
                </div>
                <div>
                  <span>所在工作空间</span>
                  <strong>{{ recordsContextLabel }}</strong>
                </div>
              </div>

              <div v-if="!recordsStudyContext" class="dataset-detail-empty">
                <AppIcon name="database" :size="24" />
                <strong>请先准备导入目标</strong>
                <span>采集记录需要先准备好处理工作空间。准备导入目标后，这里会列出该数据集的采集记录。</span>
              </div>
              <div v-else-if="isLoadingRecordings" class="dataset-list-empty">正在读取采集记录...</div>
              <div v-else-if="recordingsError" class="inline-error">{{ recordingsError }}</div>
              <div v-else-if="!selectedAssetRecordings.length" class="dataset-detail-empty">
                <AppIcon name="file" :size="24" />
                <strong>还没有采集记录</strong>
                <span>导入 EEG 原始数据后，这里会按被试 / 任务 / 会话 / 运行汇总显示。</span>
              </div>
              <div v-else class="dataset-record-list">
                <article v-for="recording in selectedAssetRecordings" :key="recording.id" class="dataset-record-row">
                  <button class="dataset-record-main" type="button" @click="toggleRecordingExpanded(recording)">
                    <div class="dataset-record-identity">
                      <strong>{{ recording.subject }}</strong>
                      <span>{{ recording.task || '未记录 task' }}</span>
                    </div>
                    <div>
                      <span>session</span>
                      <strong>{{ recording.session || '-' }}</strong>
                    </div>
                    <div>
                      <span>run</span>
                      <strong>{{ recording.run || '-' }}</strong>
                    </div>
                    <div>
                      <span>原始格式</span>
                      <strong>{{ recording.sourceFormat }}</strong>
                    </div>
                    <div>
                      <span>当前版本</span>
                      <strong>{{ recording.currentVersionLabel }}</strong>
                    </div>
                    <div>
                      <span>质控状态</span>
                      <strong>
                        <span class="badge" :class="getQaStatusClass(recording.qaStatus)">
                          {{ getQaStatusLabel(recording.qaStatus) }}
                        </span>
                      </strong>
                    </div>
                    <div>
                      <span>最近更新</span>
                      <strong>{{ formatDate(recording.updatedAt) }}</strong>
                    </div>
                    <span class="dataset-record-toggle">{{ isRecordingExpanded(recording) ? '收起' : '展开' }}</span>
                  </button>

                  <div v-if="isRecordingExpanded(recording)" class="dataset-record-detail">
                    <div class="dataset-record-detail-grid">
                      <div>
                        <span>subject</span>
                        <strong>{{ recording.subject }}</strong>
                      </div>
                      <div>
                        <span>task / session / run</span>
                        <strong>{{ recording.task || '-' }} / {{ recording.session || '-' }} / {{ recording.run || '-' }}</strong>
                      </div>
                      <div>
                        <span>通道 / 事件</span>
                        <strong>{{ recording.channelEventLabel }}</strong>
                      </div>
                      <div>
                        <span>文件体量</span>
                        <strong>{{ formatFileSize(recording.fileSize || 0) }}</strong>
                      </div>
                    </div>

                    <div class="dataset-record-files-panel">
                      <div class="dataset-record-files-head">
                        <div>
                          <span>文件列表</span>
                          <strong>按需展开查看，不在概览中铺开路径。</strong>
                        </div>
                        <button
                          class="btn btn--sm"
                          type="button"
                          :disabled="recordingFilesLoading[recording.id]"
                          @click.stop="loadRecordingFiles(recording, true)"
                        >
                          刷新文件
                        </button>
                      </div>

                      <div v-if="recordingFilesLoading[recording.id]" class="dataset-list-empty">正在读取该采集记录的文件...</div>
                      <div v-else-if="recordingFilesError[recording.id]" class="inline-error">{{ recordingFilesError[recording.id] }}</div>
                      <div v-else-if="!recordingFilesById[recording.id]?.length" class="dataset-list-empty">
                        该采集记录暂无可显示的文件。
                      </div>
                      <ul v-else class="dataset-record-files">
                        <li v-for="file in recordingFilesById[recording.id]" :key="file.id">
                          <span>{{ getFileShortPath(file) }}</span>
                          <strong>{{ getFileRoleLabel(file.file_role) }}</strong>
                          <small>{{ formatFileSize(file.file_size || 0) }}</small>
                        </li>
                      </ul>
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </section>

          <section v-else-if="activeTab === 'files'" class="dataset-tab-panel" aria-label="文件索引">
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

          <section v-else-if="activeTab === 'data'" class="dataset-tab-panel dataset-files" aria-label="数据文件">
            <!-- 安全承诺：原始文件永久保留 -->
            <div class="df-assure">
              <IconLine name="lock" :size="16" />
              <span><strong>你上传的原始文件永久保留、平台从不修改。</strong>数据按被试 / 类型组织；标准化与追溯用的技术文件折叠在每条记录里。</span>
            </div>

            <div v-if="!recordsStudyContext" class="dataset-detail-empty">
              <AppIcon name="database" :size="24" />
              <strong>请先准备导入目标</strong>
              <span>数据文件需要先准备好处理工作空间。准备导入目标后，这里会列出该数据集的原始数据与标准 FIF。</span>
            </div>
            <div v-else-if="isLoadingRecordings || isLoadingAssetFiles" class="dataset-list-empty">正在读取数据文件...</div>
            <div v-else-if="recordingsError" class="inline-error">{{ recordingsError }}</div>
            <template v-else>
              <!-- 两个大桶汇总 -->
              <div class="df-buckets">
                <div class="df-bucket df-bucket--upload">
                  <div class="df-bucket__top">
                    <span class="df-bucket__ico"><IconLine name="folder" :size="20" /></span>
                    <div>
                      <h4>你上传的原始数据</h4>
                      <span>你提供的原貌，永久保管</span>
                    </div>
                  </div>
                  <div class="df-bucket__stat">
                    <strong>{{ assetBuckets.upload.count }}</strong>
                    <span>份原始文件{{ uploadFormatHint }}</span>
                  </div>
                  <div class="df-bucket__foot">
                    <span class="df-bucket__note">共 {{ formatFileSize(assetBuckets.upload.size) }}</span>
                    <button class="btn btn--sm" type="button" disabled title="文件下载功能接入中">全部下载</button>
                  </div>
                </div>
                <div class="df-bucket df-bucket--fif">
                  <div class="df-bucket__top">
                    <span class="df-bucket__ico"><IconLine name="sparkles" :size="20" /></span>
                    <div>
                      <h4>平台标准格式（FIF）</h4>
                      <span>平台生成，可直接分析</span>
                    </div>
                  </div>
                  <div class="df-bucket__stat">
                    <strong>{{ assetBuckets.fif.count }}</strong>
                    <span>份标准 FIF · MNE 可用</span>
                  </div>
                  <div class="df-bucket__foot">
                    <span class="df-bucket__note">共 {{ formatFileSize(assetBuckets.fif.size) }} · 可重建</span>
                    <button class="btn btn--sm" type="button" disabled title="文件下载功能接入中">全部下载</button>
                  </div>
                </div>
              </div>

              <div v-if="assetBuckets.tech.count" class="df-note">
                另有 {{ assetBuckets.tech.count }} 个技术与元数据文件（sidecar、BIDS 逻辑视图、导入清单等）由平台自动生成，折叠在每条记录的「技术文件」中，普通分析无需关心。
              </div>

              <!-- 工具栏：视图切换 -->
              <div class="df-toolbar">
                <div class="df-seg">
                  <button type="button" :class="{ 'is-active': dataView === 'by-subject' }" @click="dataView = 'by-subject'">按被试浏览</button>
                  <button type="button" :class="{ 'is-active': dataView === 'by-type' }" @click="dataView = 'by-type'">按类型浏览</button>
                </div>
                <div class="df-toolbar__spacer"></div>
                <button class="btn btn--sm" type="button" :disabled="isLoadingRecordings || !recordsStudyContext" @click="loadSelectedAssetRecordings">
                  <AppIcon name="restore" :size="14" />
                  刷新
                </button>
              </div>

              <div v-if="!selectedAssetRecordings.length" class="dataset-detail-empty">
                <AppIcon name="file" :size="24" />
                <strong>还没有采集记录</strong>
                <span>导入 EEG 原始数据后，这里会按被试 / 任务列出原始数据与标准 FIF。</span>
              </div>

              <!-- 视图 A：按被试 -->
              <div v-else-if="dataView === 'by-subject'" class="df-view">
                <div v-for="group in recordingsBySubject" :key="group.subject" class="df-subject">
                  <div class="df-subject__head">
                    <IconLine name="users" :size="16" />
                    <strong>{{ group.subject }}</strong>
                    <span class="df-subject__meta">{{ group.recordings.length }} 条采集记录 · {{ formatFileSize(group.size) }}</span>
                  </div>
                  <div v-for="rec in group.recordings" :key="rec.id" class="df-rec">
                    <div class="df-rec__title">
                      <b>{{ rec.task }}</b>
                      <span v-if="rec.session && rec.session !== '-'" class="df-chip">ses-{{ rec.session }}</span>
                      <span v-if="rec.run && rec.run !== '-'" class="df-chip">run-{{ rec.run }}</span>
                      <span v-if="rec.hasCanonicalFif" class="df-bids-ok"><AppIcon name="check" :size="13" /> 已生成标准 FIF</span>
                    </div>

                    <div v-if="recordingFilesLoading[rec.id]" class="dataset-list-empty">正在读取文件...</div>
                    <div v-else-if="recordingFilesError[rec.id]" class="inline-error">{{ recordingFilesError[rec.id] }}</div>
                    <template v-else>
                      <!-- 原始数据行 -->
                      <div class="df-data-row df-data-row--upload">
                        <span class="df-data-row__ico"><IconLine name="folder" :size="17" /></span>
                        <div class="df-data-row__main">
                          <strong>你上传的原始数据 · {{ rec.sourceFormat }}</strong>
                          <span class="df-data-row__sub">{{ recordingBucketsById[rec.id]?.upload.length || 0 }} 个原始文件，永久保留</span>
                        </div>
                        <span class="df-data-row__size">{{ formatFileSize(recordingBucketsById[rec.id]?.uploadSize || 0) }}</span>
                        <button class="btn btn--sm" type="button" disabled title="文件下载功能接入中">下载</button>
                      </div>
                      <!-- 标准 FIF 行（有才显示） -->
                      <div v-if="recordingBucketsById[rec.id]?.fif.length" class="df-data-row df-data-row--fif">
                        <span class="df-data-row__ico"><IconLine name="sparkles" :size="17" /></span>
                        <div class="df-data-row__main">
                          <strong>平台标准格式 · 标准 FIF</strong>
                          <span class="df-data-row__sub">可直接用于预处理 / MNE 分析</span>
                        </div>
                        <span class="df-data-row__size">{{ formatFileSize(recordingBucketsById[rec.id]?.fifSize || 0) }}</span>
                        <button class="btn btn--sm" type="button" disabled title="文件下载功能接入中">下载</button>
                      </div>
                      <!-- 技术文件折叠（BIDS 幽灵层 + sidecar + provenance） -->
                      <details v-if="recordingBucketsById[rec.id]?.tech.length" class="df-tech">
                        <summary>技术与元数据文件（{{ recordingBucketsById[rec.id]?.tech.length }}） · 排错 / 高级用户</summary>
                        <div class="df-tech__list">
                          <div class="df-tech__hint">下列文件由平台自动生成，用于标准化、追溯和重建，普通分析无需关心：</div>
                          <div v-for="f in recordingBucketsById[rec.id]?.tech" :key="f.id" class="df-tech__item">
                            <span class="df-tech__name">{{ getFileShortPath(f) }}</span>
                            <span class="df-tech__role">{{ getFileRoleLabel(f.file_role) }}</span>
                            <span class="df-tech__size">{{ formatFileSize(f.file_size || 0) }}</span>
                          </div>
                        </div>
                      </details>
                    </template>
                  </div>
                </div>
              </div>

              <!-- 视图 B：按类型 -->
              <div v-else class="df-view">
                <div class="df-type df-type--upload">
                  <div class="df-type__head">
                    <IconLine name="folder" :size="16" />
                    <strong>你上传的原始数据</strong>
                    <span class="df-type__meta">{{ assetBuckets.upload.count }} 份 · {{ formatFileSize(assetBuckets.upload.size) }}</span>
                  </div>
                  <div v-if="!assetBuckets.upload.files.length" class="dataset-list-empty">暂无原始上传文件。</div>
                  <div v-for="f in assetBuckets.upload.files" :key="f.id" class="df-type__file">
                    <div class="df-type__main">
                      <strong>{{ getFileShortPath(f) }}</strong>
                      <span>{{ getFileRoleLabel(f.file_role) }}</span>
                    </div>
                    <span class="df-type__size">{{ formatFileSize(f.file_size || 0) }}</span>
                    <button class="btn btn--sm" type="button" disabled title="文件下载功能接入中">下载</button>
                  </div>
                </div>
                <div class="df-type df-type--fif">
                  <div class="df-type__head">
                    <IconLine name="sparkles" :size="16" />
                    <strong>平台标准格式（FIF）</strong>
                    <span class="df-type__meta">{{ assetBuckets.fif.count }} 份 · {{ formatFileSize(assetBuckets.fif.size) }}</span>
                  </div>
                  <div v-if="!assetBuckets.fif.files.length" class="dataset-list-empty">暂无标准 FIF 文件。</div>
                  <div v-for="f in assetBuckets.fif.files" :key="f.id" class="df-type__file">
                    <div class="df-type__main">
                      <strong>{{ getFileShortPath(f) }}</strong>
                      <span>{{ getFileRoleLabel(f.file_role) }}</span>
                    </div>
                    <span class="df-type__size">{{ formatFileSize(f.file_size || 0) }}</span>
                    <button class="btn btn--sm" type="button" disabled title="文件下载功能接入中">下载</button>
                  </div>
                </div>
                <details v-if="assetBuckets.tech.count" class="df-tech df-tech--global">
                  <summary>技术与元数据文件（全部 {{ assetBuckets.tech.count }} 个） · 排错 / 高级用户</summary>
                  <div class="df-tech__list">
                    <div class="df-tech__hint">sidecar 元数据、provenance、导入清单、BIDS 逻辑索引等由平台自动生成与维护；完整 logical_path / sha256 在「概览 → 技术信息」查看。</div>
                    <div v-for="f in assetBuckets.tech.files" :key="f.id" class="df-tech__item">
                      <span class="df-tech__name">{{ getFileShortPath(f) }}</span>
                      <span class="df-tech__role">{{ getFileRoleLabel(f.file_role) }}</span>
                      <span class="df-tech__size">{{ formatFileSize(f.file_size || 0) }}</span>
                    </div>
                  </div>
                </details>
              </div>
            </template>
          </section>

          <section v-else class="dataset-tab-panel" aria-label="技术信息">
            <details class="dataset-technical-details">
              <summary>
                <span>技术追溯信息</span>
                <small>{{ copyStatus || '按需展开查看 ID、关联和上传端点' }}</small>
              </summary>
              <div class="dataset-technical-grid">
                <div v-for="item in technicalInfoItems" :key="item.key">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <button
                    class="icon-btn dataset-copy-btn"
                    type="button"
                    :title="`复制${item.label}`"
                    @click="copyTechnicalValue(item.value, item.label)"
                  >
                    <AppIcon name="copy" :size="14" />
                  </button>
                </div>
              </div>
            </details>
          </section>
        </div>

        <div v-else class="dataset-detail-empty">
          <AppIcon name="database" :size="28" />
          <strong>请选择一个数据集，或新建数据集。</strong>
        </div>
      </section>
    </section>

    <!-- Phase 3 (docs_v2/3-25): 发布版本弹窗 -->
    <div v-if="publishModal.open" class="modal-backdrop" role="presentation" @click.self="closePublishModal">
      <form class="modal-card lifecycle-modal" @submit.prevent="submitPublish">
        <header>
          <div>
            <p class="eyebrow">发布数据集版本 ({{ publishTargetLabel }} → {{ publishModal.versionLabel || '?.?.?' }})</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closePublishModal">x</button>
        </header>
        <p class="modal-copy">
          发布后该版本将变为只读（不可修改），并铸造学术 DOI。版本号必须遵循语义化版本（SemVer）规则
          <code>x.y.z</code>，且严格大于已发布的最新版本。
          <strong>发布≠分享</strong>：发布只冻结并铸 DOI，可见范围默认保持私有；是否对外开放由你在发布后单独决定。
        </p>
        <label>
          <span>新版本号</span>
          <input
            v-model.trim="publishModal.versionLabel"
            type="text"
            placeholder="1.0.0"
            pattern="\d+\.\d+\.\d+"
            :class="{ 'has-error': publishModal.error }"
            required
            autofocus
          />
          <small class="field-hint" :class="{ 'is-error': publishModal.error }">
            {{ publishModal.error || '格式 主版本.次版本.修订号；主版本=实验设计变更 / 次版本=加被试 / 修订号=元数据修正' }}
          </small>
        </label>

        <!-- 规则 3：发布为 PII / 伦理 / 版权关口，每次发布都需重做。三项缺一不可。 -->
        <div class="publish-compliance">
          <p class="publish-compliance__title">发布合规确认（每个已发布版本都是独立不可变制品，需逐次确认）</p>
          <label class="publish-compliance__check">
            <input v-model="publishModal.deidentified" type="checkbox" />
            <span>我确认本版本数据已完成<strong>去标识化（脱敏）</strong>，不含可识别被试身份的个人信息（姓名、住院号、人脸等）。</span>
          </label>
          <label>
            <span>伦理声明（必填）</span>
            <textarea
              v-model.trim="publishModal.ethics"
              rows="2"
              placeholder="例如：本研究经 XX 单位伦理委员会批准（批件号 …），受试者均已知情同意。"
            />
          </label>
          <label>
            <span>版权 / 许可声明（必填）</span>
            <textarea
              v-model.trim="publishModal.license"
              rows="2"
              placeholder="例如：CC BY 4.0；或注明数据归属与允许的使用范围。"
            />
          </label>
        </div>

        <footer>
          <button class="btn btn--ghost" type="button" @click="closePublishModal">取消</button>
          <button class="btn btn--primary" type="submit" :disabled="publishModal.submitting || !canSubmitPublish">
            {{ publishModal.submitting ? '发布中...' : '发布' }}
          </button>
        </footer>
      </form>
    </div>

    <!-- Phase 3 (docs_v2/3-25): 撤回申请弹窗 -->
    <div v-if="withdrawModal.open" class="modal-backdrop" role="presentation" @click.self="closeWithdrawModal">
      <form class="modal-card lifecycle-modal" @submit.prevent="submitWithdraw">
        <header>
          <div>
            <p class="eyebrow">申请撤回</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }} {{ formatVersionLabel(currentVersion?.version_label) }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeWithdrawModal">x</button>
        </header>
        <p class="modal-copy">
          撤回申请将由平台管理员审核。审核通过后版本将转为<strong>已撤回</strong>（终态），
          已有关联和引用保留但禁止新引用。要继续工作请创建新版本（不能从已撤回状态回退）。
        </p>
        <label>
          <span>撤回原因（必填）</span>
          <textarea
            v-model.trim="withdrawModal.reason"
            rows="4"
            placeholder="例如：数据中发现被试隐私信息泄露，需要修正后重发布"
            :class="{ 'has-error': withdrawModal.error }"
            required
            autofocus
          />
          <small class="field-hint" :class="{ 'is-error': withdrawModal.error }">
            {{ withdrawModal.error || '审核管理员会看到此原因，建议详细写明触发场景' }}
          </small>
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeWithdrawModal">取消</button>
          <button class="btn btn--danger" type="submit" :disabled="withdrawModal.submitting">
            {{ withdrawModal.submitting ? '提交中...' : '提交申请' }}
          </button>
        </footer>
      </form>
    </div>

    <!-- 紧急下架弹窗（仅 admin 触发，3-25 §6.4） -->
    <div v-if="emergencyModal.open" class="modal-backdrop" role="presentation" @click.self="closeEmergencyModal">
      <form class="modal-card lifecycle-modal lifecycle-modal--danger" @submit.prevent="submitEmergencyTakedown">
        <header>
          <div>
            <p class="eyebrow eyebrow--danger">紧急下架（高危）</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }} {{ formatVersionLabel(currentVersion?.version_label) }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeEmergencyModal">x</button>
        </header>
        <p class="modal-copy modal-copy--danger">
          <strong>这是绕过审核流程的兜底通道，仅适用于：</strong>
          被试隐私泄露、法律强制下架、严重数据错误。<br />
          操作不可撤销，版本立刻进入<strong>已撤回</strong>状态（终态）。原因将永久写入审计日志。
        </p>
        <label>
          <span>紧急下架原因（必填，事后审计必看）</span>
          <textarea
            v-model.trim="emergencyModal.reason"
            rows="4"
            placeholder="例如：发现 sub-007 的 BIDS 元数据中包含被试真实姓名，需立即下架"
            :class="{ 'has-error': emergencyModal.error }"
            required
            autofocus
          />
          <small class="field-hint" :class="{ 'is-error': emergencyModal.error }">
            {{ emergencyModal.error || '描述触发场景，会写入撤回审计记录永久保留' }}
          </small>
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeEmergencyModal">取消</button>
          <button class="btn btn--danger" type="submit" :disabled="emergencyModal.submitting">
            {{ emergencyModal.submitting ? '执行中...' : '确认紧急下架' }}
          </button>
        </footer>
      </form>
    </div>

    <!-- 数据集生命周期 v2（3-25）规则 5：可见范围「开放」单向确认弹窗（只升不降，不可逆释放） -->
    <div v-if="visibilityModal.open" class="modal-backdrop" role="presentation" @click.self="closeVisibilityModal">
      <form class="modal-card lifecycle-modal lifecycle-modal--danger" @submit.prevent="submitOpenVisibility">
        <header>
          <div>
            <p class="eyebrow eyebrow--danger">开放可见范围（不可逆）</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }} → {{ getVisibilityLabel(visibilityModal.target) }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeVisibilityModal">x</button>
        </header>
        <p class="modal-copy modal-copy--danger">
          你正要把可见范围从「{{ getVisibilityLabel(selectedDatasetAsset?.visibility) }}」开放为
          <strong>「{{ getVisibilityLabel(visibilityModal.target) }}」</strong>。
          <template v-if="visibilityModal.target === 'shared'">
            共享后由你授权的用户可读、可把数据集关联进其研究项。
          </template>
          <template v-else>
            公开后<strong>全平台所有注册用户</strong>都可读取并关联此数据集。
            转公开<strong>先审后开</strong>：提交后由平台管理员审核，通过才真正公开（调试期自动通过）。
          </template>
          <br />
          <strong>开放不可逆、无降级入口</strong>：开放即等于把数据交出去（对方可能已复制，无法真正收回）。
          要可撤销地给特定人用，请改用「私有 + 把人加进主研究项」。
        </p>
        <div v-if="visibilityModal.error" class="inline-error">{{ visibilityModal.error }}</div>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeVisibilityModal">取消</button>
          <button class="btn btn--danger" type="submit" :disabled="visibilityModal.submitting">
            {{
              visibilityModal.submitting
                ? '提交中...'
                : visibilityModal.target === 'public'
                  ? '提交公开申请'
                  : `确认开放为${getVisibilityLabel(visibilityModal.target)}`
            }}
          </button>
        </footer>
      </form>
    </div>

    <!-- 规则 4：删除整个数据集（仅纯未发布资产）强确认弹窗 -->
    <div v-if="deleteAssetModal.open" class="modal-backdrop" role="presentation" @click.self="closeDeleteAssetModal">
      <form class="modal-card lifecycle-modal lifecycle-modal--danger" @submit.prevent="submitDeleteAsset">
        <header>
          <div>
            <p class="eyebrow eyebrow--danger">删除数据集（不可恢复）</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeDeleteAssetModal">x</button>
        </header>
        <p class="modal-copy modal-copy--danger">
          这将<strong>永久删除</strong>该数据集及其全部版本、文件与采集记录，无法恢复。
          仅当数据集从未发布过任何版本时才允许删除。
        </p>
        <label>
          <span>请输入数据集名称 <code>{{ selectedDatasetAsset?.name }}</code> 以确认</span>
          <input
            v-model.trim="deleteAssetModal.confirmName"
            type="text"
            :class="{ 'has-error': deleteAssetModal.error }"
            placeholder="逐字输入数据集名称"
            autofocus
          />
          <small class="field-hint" :class="{ 'is-error': deleteAssetModal.error }">
            {{ deleteAssetModal.error || '名称一致才会启用删除按钮' }}
          </small>
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeDeleteAssetModal">取消</button>
          <button
            class="btn btn--danger"
            type="submit"
            :disabled="deleteAssetModal.submitting || deleteAssetModal.confirmName !== selectedDatasetAsset?.name"
          >
            {{ deleteAssetModal.submitting ? '删除中...' : '永久删除' }}
          </button>
        </footer>
      </form>
    </div>

    <!-- 规则 4：丢弃已发布资产上的 v+1 未发布版本强确认弹窗 -->
    <div v-if="discardVersionModal.open" class="modal-backdrop" role="presentation" @click.self="closeDiscardVersionModal">
      <form class="modal-card lifecycle-modal lifecycle-modal--danger" @submit.prevent="submitDiscardVersion">
        <header>
          <div>
            <p class="eyebrow eyebrow--danger">丢弃未发布版本</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }} {{ formatVersionLabel(discardVersionModal.versionLabel) }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeDiscardVersionModal">x</button>
        </header>
        <p class="modal-copy modal-copy--danger">
          这将丢弃当前正在编辑的<strong>未发布版本</strong>及其未发布内容，不可恢复。
          已发布的历史版本不受影响。
        </p>
        <div v-if="discardVersionModal.error" class="inline-error">{{ discardVersionModal.error }}</div>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeDiscardVersionModal">取消</button>
          <button class="btn btn--danger" type="submit" :disabled="discardVersionModal.submitting">
            {{ discardVersionModal.submitting ? '丢弃中...' : '确认丢弃' }}
          </button>
        </footer>
      </form>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import BidsUploadPanel from '@/components/BidsUploadPanel.vue'
import TechnicalFold from '@/components/TechnicalFold.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { useAuthStore } from '@/stores/auth'
import { datasetAssetApi, datasetMemberApi, recordingApi, studyDatasetMountApi } from '@/api/datasetAssets'
import {
  datasetVersionApi,
  datasetVersionStateClass,
  datasetVersionStateLabel,
} from '@/api/datasetVersions'
import { studyApi } from '@/api/studies'
import type {
  DatasetAsset,
  DatasetAssetVisibility,
  DatasetBootstrapResponse,
  DatasetFile,
  DatasetMember,
  DatasetUploadContext,
  DatasetVersion,
  Recording,
  Study,
  StudyDatasetMount,
} from '@/types'

const STUDY_CODE_MAX_LENGTH = 64
const FILE_INDEX_PAGE_SIZE = 30
type DatasetWorkbenchTab = 'overview' | 'import' | 'data' | 'records' | 'files' | 'technical'
type DatasetFileRoleFilter = 'all' | 'original' | 'raw-bids' | 'canonical-fif' | 'other'
interface TechnicalInfoItem {
  key: string
  label: string
  value: string
}

interface DatasetRecordingRow {
  id: string
  subject: string
  session: string | null
  task: string
  run: string | null
  sourceFormat: string
  currentVersionLabel: string
  hasCanonicalFif: boolean
  channelEventLabel: string
  qaStatus: string | null
  updatedAt: string | null
  fileSize: number | null
  datasetAssetId: string | null
}

interface RecordsStudyContext {
  studyId: string
  studyName: string
  mountId?: string
  mountName?: string
}

const datasetTabs: Array<{ key: DatasetWorkbenchTab; label: string }> = [
  { key: 'overview', label: '概览' },
  { key: 'import', label: '导入' },
  { key: 'data', label: '数据文件' },
]

const fileRoleOptions: Array<{ value: DatasetFileRoleFilter; label: string }> = [
  { value: 'all', label: '全部角色' },
  { value: 'original', label: '原始上传' },
  { value: 'raw-bids', label: 'BIDS 逻辑视图' },
  { value: 'canonical-fif', label: '标准 FIF' },
  { value: 'other', label: '其他' },
]

const route = useRoute()
const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.roles?.includes('admin') ?? false)
const studies = ref<Study[]>([])
const datasetAssets = ref<DatasetAsset[]>([])
const selectedAssetFiles = ref<DatasetFile[]>([])
const selectedAssetRecordings = ref<DatasetRecordingRow[]>([])
const expandedRecordingIds = ref<string[]>([])
const recordingFilesById = ref<Record<string, DatasetFile[]>>({})
const recordingFilesLoading = ref<Record<string, boolean>>({})
const recordingFilesError = ref<Record<string, string>>({})
const activePanel = ref<'catalog' | 'create'>('catalog')
const activeTab = ref<DatasetWorkbenchTab>('overview')
const assetSearch = ref('')
const assetVisibilityFilter = ref<'all' | 'private' | 'shared' | 'public'>('all')
const datasetName = ref('')
const datasetCode = ref('')
const datasetDescription = ref('')
const selectedStudyId = ref('')
const selectedDatasetAssetId = ref('')
const mountName = ref('primary')
const fileSearch = ref('')
const fileRoleFilter = ref<DatasetFileRoleFilter>('all')
const fileDisplayLimit = ref(FILE_INDEX_PAGE_SIZE)
const uploadSectionRef = ref<HTMLElement | null>(null)
const uploadPanelRef = ref<HTMLElement | null>(null)
const bootstrapResponse = ref<DatasetBootstrapResponse | null>(null)
const mountedTarget = ref<{
  asset: DatasetAsset
  study: Study
  mount: StudyDatasetMount
} | null>(null)
const isBootstrapping = ref(false)
const isLoadingAssets = ref(false)
const isLoadingAssetFiles = ref(false)
const isLoadingRecordings = ref(false)
const selectedAssetFilesError = ref('')
const recordingsError = ref('')
const bootstrapError = ref('')
const bootstrapSuccess = ref('')
const copyStatus = ref('')

// Phase 3 (docs_v2/3-25): 数据集版本生命周期
const datasetVersions = ref<DatasetVersion[]>([])
const isLoadingVersions = ref(false)
const isCreatingDraft = ref(false)
const lifecycleMessage = ref('')
const publishModal = ref<{
  open: boolean
  versionLabel: string
  submitting: boolean
  error: string
  targetVersionId: string | null
  // 规则 3：发布合规关口（每次发布都需重做）
  deidentified: boolean
  ethics: string
  license: string
}>({ open: false, versionLabel: '1.0.0', submitting: false, error: '', targetVersionId: null, deidentified: false, ethics: '', license: '' })
const withdrawModal = ref<{
  open: boolean
  reason: string
  submitting: boolean
  error: string
  targetVersionId: string | null
}>({ open: false, reason: '', submitting: false, error: '', targetVersionId: null })
const emergencyModal = ref<{
  open: boolean
  reason: string
  submitting: boolean
  error: string
}>({ open: false, reason: '', submitting: false, error: '' })

// 数据集生命周期 v2（3-25）：可见范围「开放」（只升不降，目标只能是 shared/public）
const visibilityModal = ref<{
  open: boolean
  target: Extract<DatasetAssetVisibility, 'shared' | 'public'>
  submitting: boolean
  error: string
}>({ open: false, target: 'shared', submitting: false, error: '' })

// 规则 7：邀请制授权用户面板
const datasetMembers = ref<DatasetMember[]>([])
const isLoadingMembers = ref(false)
const isAddingMember = ref(false)
const memberAddUserId = ref('')
const memberError = ref('')
const removingMemberId = ref('')

// 规则 4：删除整个数据集（仅纯未发布资产）
const deleteAssetModal = ref<{
  open: boolean
  confirmName: string
  submitting: boolean
  error: string
}>({ open: false, confirmName: '', submitting: false, error: '' })
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

// 规则 4：丢弃已发布资产上的 v+1 未发布版本
const discardVersionModal = ref<{
  open: boolean
  versionId: string | null
  versionLabel: string
  submitting: boolean
  error: string
}>({ open: false, versionId: null, versionLabel: '', submitting: false, error: '' })

const queryStudyId = computed(() => queryString(route.query.study_id) || queryString(route.query.studyId))
const selectedStudy = computed(() =>
  studies.value.find((study) => study.id === selectedStudyId.value),
)
const usesShortcutStudy = computed(() => Boolean(queryStudyId.value && selectedStudyId.value))
const shortcutStudyLabel = computed(() => {
  const study = selectedStudy.value
  if (study) return `${study.name} · ${study.id}`
  return selectedStudyId.value || queryStudyId.value
})
const selectedDatasetAsset = computed(() =>
  datasetAssets.value.find((asset) => asset.id === selectedDatasetAssetId.value) || null,
)

// Phase 3 (docs_v2/3-25): 当前展示的版本 = asset.current_version_id 对应的版本，回退到第一个
const currentVersion = computed<DatasetVersion | null>(() => {
  if (!datasetVersions.value.length) return null
  const asset = selectedDatasetAsset.value
  const targetId = asset?.current_version_id
  if (targetId) {
    const found = datasetVersions.value.find((v) => v.id === targetId)
    if (found) return found
  }
  return datasetVersions.value[0]
})

// Phase 3 (docs_v2/3-25) C: 版本时间线排序（未发布在最上，其次按发布时间倒序）
const sortedVersions = computed<DatasetVersion[]>(() => {
  return [...datasetVersions.value].sort((a, b) => {
    const stateOrder: Record<string, number> = { unpublished: 0, withdraw_requested: 1, published: 2, withdrawn: 3 }
    const ao = stateOrder[a.state || 'published'] ?? 4
    const bo = stateOrder[b.state || 'published'] ?? 4
    if (ao !== bo) return ao - bo
    const at = a.published_at || a.created_at || ''
    const bt = b.published_at || b.created_at || ''
    return bt.localeCompare(at)
  })
})

// 数据集生命周期 v2（3-25）：可见范围与发布解耦。徽章只读展示，开放走专门的单向「开放」动作（只升不降）。
function visibilityHint(visibility: string) {
  if (visibility === 'private') return '仅主研究项可见（负责人 / 管理员 / 主研究项成员）。开放为共享 / 公开后才能被其他研究项引用。'
  if (visibility === 'shared') return '邀请制：仅负责人授权的用户可读、可关联到自己的研究项。开放不可逆，无降级入口。'
  if (visibility === 'public') return '全平台所有注册用户可读 / 可关联。开放不可逆。'
  return ''
}

const hasOpenDraft = computed<boolean>(() =>
  datasetVersions.value.some((v) => v.state === 'unpublished' || v.state === 'withdraw_requested'),
)
const hasAnyPublished = computed<boolean>(() =>
  datasetVersions.value.some((v) => v.state === 'published' || v.state === 'withdrawn'),
)
// 删除口径（与后端「整体删除」一致）：资产有任何 published / withdraw_requested / withdrawn 版本即视为「发布过」，不可删，只能撤回。
const hasPublishedHistory = computed<boolean>(() =>
  datasetVersions.value.some(
    (v) => v.state === 'published' || v.state === 'withdraw_requested' || v.state === 'withdrawn',
  ),
)
// 开放口径（与后端 asset_has_published_version 一致）：仅当「当前存在 state==='published' 的版本」才允许开放可见范围。withdrawn 终态不算。
const hasCurrentlyPublished = computed<boolean>(() =>
  datasetVersions.value.some((v) => v.state === 'published'),
)
const canCreateNewDraft = computed<boolean>(() => hasAnyPublished.value && !hasOpenDraft.value)
const canCreateNewDraftBlockedReason = computed<string>(() => {
  if (!datasetVersions.value.length) return ''
  if (!hasAnyPublished.value) return ''
  if (hasOpenDraft.value) return '已有未完结的版本（未发布 / 撤回审核中），请先处理完毕再创建新版本。'
  return ''
})

// 数据集生命周期 v2（3-25）：负责人（owner）专属操作判定。发布/授权/撤回/开放/删除一律仅 owner。
const isAssetOwner = computed<boolean>(() => {
  const asset = selectedDatasetAsset.value
  const uid = auth.user?.id
  return Boolean(asset && uid && asset.owner_id === uid)
})

// 规则 5 + 边界规则 J：开放需「仅 owner」+「至少 1 个已发布版本」+「目标开放度严格高于当前」。
const visibilityRank: Record<string, number> = { private: 0, shared: 1, public: 2 }
function canOpenVisibility(target: 'shared' | 'public'): boolean {
  const asset = selectedDatasetAsset.value
  if (!asset || !isAssetOwner.value) return false
  if (!hasCurrentlyPublished.value) return false
  const current = visibilityRank[asset.visibility] ?? 0
  return visibilityRank[target] > current
}

// 规则 7：共享态 + 仅 owner 才显示授权用户面板
const showMemberPanel = computed<boolean>(
  () => isAssetOwner.value && selectedDatasetAsset.value?.visibility === 'shared',
)

// 规则 4：纯未发布资产（无任何 published/withdraw_requested/withdrawn 版本）+ 仅 owner 才可整体删除
const canDeleteAsset = computed<boolean>(
  () => isAssetOwner.value && datasetVersions.value.length > 0 && !hasPublishedHistory.value,
)

// 规则 4：已发布资产上的 v+1 未发布版本可单独丢弃（仅 owner）；纯未发布资产用「删除数据集」而非丢弃单版本
function canDiscardVersion(version: DatasetVersion): boolean {
  return isAssetOwner.value && version.state === 'unpublished' && hasAnyPublished.value
}

// 规则 3：发布合规三项齐全才允许提交
const canSubmitPublish = computed<boolean>(
  () => publishModal.value.deidentified && Boolean(publishModal.value.ethics) && Boolean(publishModal.value.license),
)

// 发布弹窗里显示"要发布的源版本号"（默认 working，但可能是手动选其他未发布版本）
const publishTargetLabel = computed<string>(() => {
  const id = publishModal.value.targetVersionId
  if (!id) return 'working'
  return datasetVersions.value.find((v) => v.id === id)?.version_label || 'working'
})
const filteredDatasetAssets = computed(() => {
  const keyword = assetSearch.value.trim().toLowerCase()
  return datasetAssets.value
    .filter((asset) => {
      if (assetVisibilityFilter.value !== 'all' && asset.visibility !== assetVisibilityFilter.value) return false
      if (!keyword) return true
      return [asset.name, asset.code, asset.description || '']
        .some((text) => text.toLowerCase().includes(keyword))
    })
    .sort((a, b) => getDateValue(b.updated_at || b.created_at) - getDateValue(a.updated_at || a.created_at))
})
const assetStats = computed(() => ({
  total: datasetAssets.value.length,
  private: datasetAssets.value.filter((asset) => asset.visibility === 'private').length,
  shared: datasetAssets.value.filter((asset) => asset.visibility === 'shared').length,
  public: datasetAssets.value.filter((asset) => asset.visibility === 'public').length,
}))
const selectedAssetFileStats = computed(() => {
  const files = selectedAssetFiles.value
  return {
    total: files.length,
    original: countFilesByRole(files, ['original', 'upload', 'source']),
    // 两层重构：raw_bids 角色已下线（降纯逻辑），原「BIDS 逻辑视图」统计退役。canonicalFif 仍按 'fif' 子串匹配新角色。
    canonicalFif: countFilesByRole(files, ['canonical', 'fif']),
    totalSize: files.reduce((sum, file) => sum + (file.file_size || 0), 0),
  }
})
// ===== 数据文件管理器（filemanager 视图）：后台 3 类文件角色 → 用户 2 个桶 =====
const dataView = ref<'by-subject' | 'by-type'>('by-subject')

// original/upload/source → 你上传的；canonical/fif → 标准 FIF；raw/bids(幽灵) + sidecar + 其它 → 技术文件
function fileBucketOf(file: DatasetFile): 'upload' | 'fif' | 'tech' {
  const role = (file.file_role || '').toLowerCase()
  if (role.includes('original') || role.includes('upload') || role.includes('source')) return 'upload'
  if (role.includes('canonical') || role.includes('fif')) return 'fif'
  return 'tech'
}
function sumFileSize(files: DatasetFile[]) {
  return files.reduce((sum, file) => sum + (file.file_size || 0), 0)
}

// 资产级 2 桶（用于顶部汇总卡 + 按类型视图）
const assetBuckets = computed(() => {
  const buckets = {
    upload: { count: 0, size: 0, files: [] as DatasetFile[] },
    fif: { count: 0, size: 0, files: [] as DatasetFile[] },
    tech: { count: 0, size: 0, files: [] as DatasetFile[] },
  }
  for (const file of selectedAssetFiles.value) {
    const bucket = buckets[fileBucketOf(file)]
    bucket.files.push(file)
    bucket.count += 1
    bucket.size += file.file_size || 0
  }
  return buckets
})

// 原始数据格式提示（取记录里出现过的源格式，如 BrainVision / EDF）
const uploadFormatHint = computed(() => {
  const formats = Array.from(
    new Set(selectedAssetRecordings.value.map((r) => r.sourceFormat).filter((f) => f && f !== '-')),
  )
  return formats.length ? ` · ${formats.join(' / ')}` : ''
})

// 按被试分组（按被试视图）
const recordingsBySubject = computed(() => {
  const groups = new Map<string, { subject: string; recordings: DatasetRecordingRow[]; size: number }>()
  for (const recording of selectedAssetRecordings.value) {
    let group = groups.get(recording.subject)
    if (!group) {
      group = { subject: recording.subject, recordings: [], size: 0 }
      groups.set(recording.subject, group)
    }
    group.recordings.push(recording)
    group.size += recording.fileSize || 0
  }
  return Array.from(groups.values())
})

// 每条记录的文件按 2 桶 + 技术拆分（按被试视图每条记录的数据行）
const recordingBucketsById = computed(() => {
  const out: Record<
    string,
    { upload: DatasetFile[]; fif: DatasetFile[]; tech: DatasetFile[]; uploadSize: number; fifSize: number }
  > = {}
  for (const [id, files] of Object.entries(recordingFilesById.value)) {
    const upload = files.filter((f) => fileBucketOf(f) === 'upload')
    const fif = files.filter((f) => fileBucketOf(f) === 'fif')
    const tech = files.filter((f) => fileBucketOf(f) === 'tech')
    out[id] = { upload, fif, tech, uploadSize: sumFileSize(upload), fifSize: sumFileSize(fif) }
  }
  return out
})

const recordingStats = computed(() => ({
  total: selectedAssetRecordings.value.length,
  withCanonicalFif: selectedAssetRecordings.value.filter((recording) => recording.hasCanonicalFif).length,
  qcPassed: selectedAssetRecordings.value.filter((recording) => isQaPassed(recording.qaStatus)).length,
}))
const datasetDecisionSummary = computed(() => {
  const stats = selectedAssetFileStats.value
  if (isLoadingAssetFiles.value) {
    return {
      className: 'is-syncing',
      title: '正在读取文件摘要',
      message: '正在同步该数据集的 working 文件索引摘要。',
      detail: '请稍候，概览会在读取完成后更新。',
      processing: '等待摘要',
      processingHint: '文件摘要完成后再判断是否可进入后续处理。',
    }
  }
  if (selectedAssetFilesError.value) {
    return {
      className: 'is-warning',
      title: '文件摘要待确认',
      message: '文件索引读取失败，暂时无法判断该数据集的导入完整度。',
      detail: '可以刷新文件索引，或先进入导入页继续准备上传。',
      processing: '暂缓处理',
      processingHint: '建议先确认文件索引状态，再进入 QC 或 Pipeline。',
    }
  }
  if (!stats.total) {
    return {
      className: 'is-empty',
      title: '尚未导入',
      message: isTargetForSelectedAsset.value
        ? '该数据集已准备导入目标，可以继续上传 EEG 原始数据。'
        : '该数据集还没有文件摘要，请先准备导入目标并上传原始数据。',
      detail: isTargetForSelectedAsset.value
        ? '进入导入页选择 EDF、BDF 或 BrainVision 文件。'
        : '准备目标后，系统会把上传写入 Dataset working 版本。',
      processing: '暂不可进入',
      processingHint: '后续处理需要至少完成原始数据导入和文件索引写入。',
    }
  }
  if (stats.canonicalFif > 0) {
    return {
      className: 'is-ready',
      title: '已导入，可进入后续处理',
      message: '该数据集已有文件索引和标准 FIF 摘要，可继续导入，也可进入 QC 或 Pipeline。',
      detail: '如需追加数据，可进入导入页；如需处理分析，可在工作流中选择该数据集。',
      processing: '可进入',
      processingHint: '标准 FIF 已生成，适合进入质控、预览或工作流处理。',
    }
  }
  return {
    className: 'is-partial',
    title: '已导入，等待标准文件',
    message: '该数据集已有原始上传或 BIDS 逻辑视图，但标准 FIF 摘要尚未出现。',
    detail: '可以继续导入，或等待/触发标准 FIF 生成后再进入后续处理。',
    processing: '需确认',
    processingHint: '进入 QC 或 Pipeline 前，建议确认标准 FIF 和文件索引已完整。',
  }
})
const filteredAssetFiles = computed(() => {
  const keyword = fileSearch.value.trim().toLowerCase()
  return selectedAssetFiles.value.filter((file) => {
    if (!matchesFileRoleFilter(file, fileRoleFilter.value)) return false
    if (!keyword) return true
    return [
      getFileShortPath(file),
      getFileDisplayPath(file),
      getFileRoleLabel(file.file_role),
      file.file_role,
      file.sha256 || '',
    ].some((text) => text.toLowerCase().includes(keyword))
  })
})
const visibleAssetFiles = computed(() => filteredAssetFiles.value.slice(0, fileDisplayLimit.value))
const hiddenAssetFileCount = computed(() => Math.max(0, filteredAssetFiles.value.length - visibleAssetFiles.value.length))
const canCreateDataset = computed(() =>
  Boolean(datasetName.value && sanitizeCode(datasetCode.value) && sanitizeCode(mountName.value)),
)
const canMountSelected = computed(() =>
  Boolean(!isBootstrapping.value && selectedDatasetAsset.value && sanitizeCode(mountName.value) && (!usesShortcutStudy.value || selectedStudyId.value)),
)
const targetSummary = computed(() => {
  if (bootstrapResponse.value) {
    return {
      datasetAssetName: bootstrapResponse.value.dataset_asset.name,
      datasetAssetId: bootstrapResponse.value.dataset_asset.id,
      studyName: bootstrapResponse.value.study.name,
      studyId: bootstrapResponse.value.study.id,
      mountName: bootstrapResponse.value.mount.mount_name,
      mountId: bootstrapResponse.value.mount.id,
    }
  }
  if (mountedTarget.value) {
    return {
      datasetAssetName: mountedTarget.value.asset.name,
      datasetAssetId: mountedTarget.value.asset.id,
      studyName: mountedTarget.value.study.name,
      studyId: mountedTarget.value.study.id,
      mountName: mountedTarget.value.mount.mount_name,
      mountId: mountedTarget.value.mount.id,
    }
  }
  return null
})
const isTargetForSelectedAsset = computed(() =>
  Boolean(targetSummary.value && selectedDatasetAsset.value && targetSummary.value.datasetAssetId === selectedDatasetAsset.value.id),
)
const recordsStudyContext = computed<RecordsStudyContext | null>(() => {
  const asset = selectedDatasetAsset.value
  if (!asset) return null

  const target = targetSummary.value
  if (target?.datasetAssetId === asset.id) {
    return {
      studyId: target.studyId,
      studyName: target.studyName,
      mountId: target.mountId,
      mountName: target.mountName,
    }
  }

  if (usesShortcutStudy.value && selectedStudyId.value) {
    return {
      studyId: selectedStudyId.value,
      studyName: selectedStudy.value?.name || selectedStudyId.value,
      mountName: sanitizeCode(mountName.value || 'primary'),
    }
  }

  const pairedStudy = studies.value.find((study) => study.code === trimStudyCode(resolvedPairedStudyCode(asset)))
  if (!pairedStudy) return null
  return {
    studyId: pairedStudy.id,
    studyName: pairedStudy.name,
    mountName: sanitizeCode(mountName.value || 'primary'),
  }
})
const recordsContextLabel = computed(() => {
  const context = recordsStudyContext.value
  if (!context) return '未准备'
  return context.mountName
    ? `${formatProcessingWorkspaceName(context.studyName)} / ${context.mountName}`
    : formatProcessingWorkspaceName(context.studyName)
})
const uploadContext = computed<DatasetUploadContext | null>(() => {
  const response = bootstrapResponse.value
  if (response) {
    return {
      studyId: response.next_upload.study_id,
      datasetAssetId: response.next_upload.dataset_asset_id,
      datasetVersionId: response.next_upload.dataset_version_id,
      mountId: response.next_upload.mount_id,
      mountName: response.next_upload.mount_name,
      uploadEndpoint: response.next_upload.upload_endpoint,
      uploadMethod: response.next_upload.upload_method,
      studyName: response.study.name,
      datasetAssetName: response.dataset_asset.name,
    }
  }
  const mounted = mountedTarget.value
  if (!mounted) return null
  return {
    studyId: mounted.study.id,
    datasetAssetId: mounted.asset.id,
    mountId: mounted.mount.id,
    mountName: mounted.mount.mount_name,
    uploadEndpoint: `/api/v1/studies/${mounted.study.id}/recordings/import`,
    uploadMethod: 'POST',
    studyName: mounted.study.name,
    datasetAssetName: mounted.asset.name,
  }
})
const technicalInfoItems = computed<TechnicalInfoItem[]>(() => {
  const items: Array<TechnicalInfoItem | null> = [
    selectedDatasetAsset.value
      ? { key: 'dataset-asset-id', label: '数据集 ID', value: selectedDatasetAsset.value.id }
      : null,
    targetSummary.value
      ? { key: 'study-id', label: 'Study ID', value: targetSummary.value.studyId }
      : null,
    targetSummary.value
      ? { key: 'mount-name', label: 'mount_name', value: targetSummary.value.mountName }
      : null,
    targetSummary.value
      ? { key: 'mount-id', label: 'mount_id', value: targetSummary.value.mountId }
      : null,
    uploadContext.value?.datasetVersionId
      ? { key: 'dataset-version-id', label: 'dataset_version_id', value: uploadContext.value.datasetVersionId }
      : null,
    uploadContext.value?.uploadEndpoint
      ? { key: 'upload-endpoint', label: 'upload endpoint', value: uploadContext.value.uploadEndpoint }
      : null,
  ]
  return items.filter((item): item is TechnicalInfoItem => Boolean(item?.value))
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
watch(selectedAssetRecordings, (recordings) => {
  if (activeTab.value !== 'data') return
  for (const recording of recordings) void loadRecordingFiles(recording)
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

async function loadStudies() {
  try {
    const res = await studyApi.list()
    studies.value = res.data.studies
  } catch {
    studies.value = []
  }
}

async function loadDatasetAssets() {
  isLoadingAssets.value = true
  try {
    const res = await datasetAssetApi.list()
    datasetAssets.value = res.data.assets
    if (!selectedDatasetAssetId.value && datasetAssets.value.length) {
      selectedDatasetAssetId.value = sortedAssets(datasetAssets.value)[0].id
    } else if (selectedDatasetAssetId.value && !datasetAssets.value.some((asset) => asset.id === selectedDatasetAssetId.value)) {
      selectedDatasetAssetId.value = datasetAssets.value.length ? sortedAssets(datasetAssets.value)[0].id : ''
    }
  } catch {
    datasetAssets.value = []
  } finally {
    isLoadingAssets.value = false
  }
}

async function loadSelectedAssetFiles() {
  const assetId = selectedDatasetAssetId.value
  selectedAssetFilesError.value = ''
  selectedAssetFiles.value = []
  fileDisplayLimit.value = FILE_INDEX_PAGE_SIZE
  if (!assetId) return
  isLoadingAssetFiles.value = true
  try {
    const res = await datasetAssetApi.listFiles(assetId, { version_label: 'working' })
    selectedAssetFiles.value = res.data.files
  } catch {
    selectedAssetFilesError.value = '文件索引读取失败，请确认该数据集是否已完成导入或稍后重试。'
  } finally {
    isLoadingAssetFiles.value = false
  }
}

// Phase 3 (docs_v2/3-25): 加载所选 Asset 的所有版本，给版本卡片用
async function loadSelectedAssetVersions() {
  const assetId = selectedDatasetAssetId.value
  datasetVersions.value = []
  if (!assetId) return
  isLoadingVersions.value = true
  try {
    const res = await datasetAssetApi.listVersions(assetId)
    datasetVersions.value = res.data.versions
  } catch {
    // 静默失败：旧 Asset 可能还没版本数据；不阻塞页面
    datasetVersions.value = []
  } finally {
    isLoadingVersions.value = false
  }
  // 规则 7：版本载入后同步授权用户面板（函数内部按 owner + 共享态自守卫，否则为空操作）
  void loadSelectedAssetMembers()
}

function qaStatusLabel(status: string | null | undefined): string {
  if (status === 'pass') return '已通过'
  if (status === 'fail') return '未通过'
  return '未运行'
}

function lifecycleErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string } | string
    const msg = typeof first === 'string' ? first : first?.msg
    if (msg) return msg
  }
  const message = err instanceof Error ? err.message : ''
  return message || fallback
}

// 推荐下一个 SemVer：在最大已发布版本上 +0.1.0；没有已发布则 1.0.0
function suggestNextVersionLabel(): string {
  const published = datasetVersions.value
    .map((v) => v.version_label)
    .filter((label) => /^\d+\.\d+\.\d+$/.test(label))
    .map((label) => label.split('.').map((n) => parseInt(n, 10)) as [number, number, number])
    .sort((a, b) => b[0] - a[0] || b[1] - a[1] || b[2] - a[2])
  if (!published.length) return '1.0.0'
  const [major, minor] = published[0]
  return `${major}.${minor + 1}.0`
}

function openPublishModal() {
  openPublishModalForVersion(currentVersion.value)
}
function openPublishModalForVersion(version: DatasetVersion | null) {
  if (!version) return
  publishModal.value = {
    open: true,
    versionLabel: suggestNextVersionLabel(),
    submitting: false,
    error: '',
    targetVersionId: version.id,
    deidentified: false,
    ethics: '',
    license: '',
  }
}
function closePublishModal() {
  if (publishModal.value.submitting) return
  publishModal.value.open = false
  publishModal.value.error = ''
}
async function submitPublish() {
  const versionId = publishModal.value.targetVersionId
  if (!versionId) return
  const label = publishModal.value.versionLabel.trim()
  if (!/^\d+\.\d+\.\d+$/.test(label)) {
    publishModal.value.error = '版本号必须是 SemVer x.y.z 格式（如 1.0.0）'
    return
  }
  // 规则 3：发布合规关口，三项缺一不可
  if (!publishModal.value.deidentified) {
    publishModal.value.error = '请先勾选「已完成去标识化（脱敏）」确认'
    return
  }
  const ethics = publishModal.value.ethics.trim()
  const license = publishModal.value.license.trim()
  if (!ethics || !license) {
    publishModal.value.error = '请填写伦理声明与版权 / 许可声明'
    return
  }
  publishModal.value.submitting = true
  publishModal.value.error = ''
  try {
    await datasetVersionApi.publish(versionId, {
      version_label: label,
      deidentified_confirmed: true,
      ethics_statement: ethics,
      license_statement: license,
    })
    lifecycleMessage.value = `已发布 ${label}`
    publishModal.value.open = false
    await Promise.all([loadDatasetAssets(), loadSelectedAssetVersions()])
  } catch (err) {
    publishModal.value.error = lifecycleErrorMessage(err, '发布失败')
  } finally {
    publishModal.value.submitting = false
  }
}

function openWithdrawModal() {
  openWithdrawModalForVersion(currentVersion.value)
}
function openWithdrawModalForVersion(version: DatasetVersion | null) {
  if (!version) return
  withdrawModal.value = {
    open: true,
    reason: '',
    submitting: false,
    error: '',
    targetVersionId: version.id,
  }
}
function closeWithdrawModal() {
  if (withdrawModal.value.submitting) return
  withdrawModal.value.open = false
  withdrawModal.value.error = ''
}
async function submitWithdraw() {
  const versionId = withdrawModal.value.targetVersionId
  if (!versionId) return
  const reason = withdrawModal.value.reason.trim()
  if (!reason) {
    withdrawModal.value.error = '撤回原因不能为空'
    return
  }
  withdrawModal.value.submitting = true
  withdrawModal.value.error = ''
  try {
    await datasetVersionApi.requestWithdrawal(versionId, { reason })
    lifecycleMessage.value = '撤回申请已提交，等待管理员审核'
    withdrawModal.value.open = false
    await loadSelectedAssetVersions()
  } catch (err) {
    withdrawModal.value.error = lifecycleErrorMessage(err, '提交失败')
  } finally {
    withdrawModal.value.submitting = false
  }
}

// 紧急下架（仅 admin，3-25 §6.4）
function openEmergencyTakedownModal() {
  emergencyModal.value = { open: true, reason: '', submitting: false, error: '' }
}
function closeEmergencyModal() {
  if (emergencyModal.value.submitting) return
  emergencyModal.value.open = false
  emergencyModal.value.error = ''
}
async function submitEmergencyTakedown() {
  const version = currentVersion.value
  if (!version) return
  const reason = emergencyModal.value.reason.trim()
  if (!reason) {
    emergencyModal.value.error = '紧急下架原因不能为空（事后审计必需）'
    return
  }
  emergencyModal.value.submitting = true
  emergencyModal.value.error = ''
  try {
    await datasetVersionApi.emergencyTakedown(version.id, { reason })
    lifecycleMessage.value = '版本已紧急下架（已写入审计日志）'
    emergencyModal.value.open = false
    await loadSelectedAssetVersions()
  } catch (err) {
    emergencyModal.value.error = lifecycleErrorMessage(err, '紧急下架失败')
  } finally {
    emergencyModal.value.submitting = false
  }
}

// Phase 3 (docs_v2/3-25) C: 创建新未发布版本（已发布过的 Asset 推 v+1）
async function createNewDraft() {
  const asset = selectedDatasetAsset.value
  if (!asset) return
  if (!canCreateNewDraft.value) return
  isCreatingDraft.value = true
  try {
    const res = await datasetAssetApi.createDraftVersion(asset.id)
    lifecycleMessage.value = `已新建未发布版本（${res.data.version_label}）`
    await loadSelectedAssetVersions()
  } catch (err) {
    lifecycleMessage.value = lifecycleErrorMessage(err, '创建新未发布版本失败')
  } finally {
    isCreatingDraft.value = false
  }
}

// ===== 数据集生命周期 v2（3-25）：可见范围「开放」（只升不降，单向不可逆） =====
function openVisibilityModalFor(target: 'shared' | 'public') {
  if (!canOpenVisibility(target)) return
  visibilityModal.value = { open: true, target, submitting: false, error: '' }
}
function closeVisibilityModal() {
  if (visibilityModal.value.submitting) return
  visibilityModal.value.open = false
  visibilityModal.value.error = ''
}
async function submitOpenVisibility() {
  const asset = selectedDatasetAsset.value
  if (!asset) return
  const target = visibilityModal.value.target
  visibilityModal.value.submitting = true
  visibilityModal.value.error = ''
  try {
    if (target === 'public') {
      // 转公开「先审后开」：走申请端点。调试期 auto-approve → 即时升 public、decision='auto'。
      const res = await datasetAssetApi.requestPublicization(asset.id)
      lifecycleMessage.value =
        res.data.decision === 'auto'
          ? '转公开申请已自动通过（调试期），可见范围已开放为「公开」'
          : '转公开申请已提交，待管理员审核通过后才会公开'
    } else {
      await datasetAssetApi.openVisibility(asset.id, { target })
      lifecycleMessage.value = `可见范围已开放为「${getVisibilityLabel(target)}」`
    }
    visibilityModal.value.open = false
    await loadDatasetAssets()
    // 开放为共享后立即拉取授权用户列表（面板随之出现）
    if (target === 'shared') await loadSelectedAssetMembers()
  } catch (err) {
    visibilityModal.value.error = lifecycleErrorMessage(err, target === 'public' ? '申请公开失败' : '开放失败')
  } finally {
    visibilityModal.value.submitting = false
  }
}

// ===== 规则 7：邀请制授权用户（dataset_members）=====
async function loadSelectedAssetMembers() {
  const asset = selectedDatasetAsset.value
  datasetMembers.value = []
  memberError.value = ''
  if (!asset || !isAssetOwner.value || asset.visibility !== 'shared') return
  isLoadingMembers.value = true
  try {
    const res = await datasetMemberApi.list(asset.id)
    datasetMembers.value = res.data.members
  } catch (err) {
    memberError.value = lifecycleErrorMessage(err, '读取授权用户失败')
  } finally {
    isLoadingMembers.value = false
  }
}
async function submitAddMember() {
  const asset = selectedDatasetAsset.value
  const userId = memberAddUserId.value.trim()
  if (!asset || !userId) return
  isAddingMember.value = true
  memberError.value = ''
  try {
    // #14：原样把输入值（用户名 / 邮箱 / UUID）传给后端，不在前端做格式校验
    await datasetMemberApi.add(asset.id, { user_identifier: userId })
    memberAddUserId.value = ''
    await loadSelectedAssetMembers()
  } catch (err) {
    memberError.value = lifecycleErrorMessage(err, '授权失败')
  } finally {
    isAddingMember.value = false
  }
}
async function revokeMember(member: DatasetMember) {
  const asset = selectedDatasetAsset.value
  if (!asset) return
  removingMemberId.value = member.user_id
  memberError.value = ''
  try {
    await datasetMemberApi.remove(asset.id, member.user_id)
    await loadSelectedAssetMembers()
  } catch (err) {
    memberError.value = lifecycleErrorMessage(err, '取消授权失败')
  } finally {
    removingMemberId.value = ''
  }
}

// ===== 规则 4：删除整个数据集（仅纯未发布资产，仅 owner）=====
function openDeleteAssetModal() {
  if (!canDeleteAsset.value) return
  deleteAssetModal.value = { open: true, confirmName: '', submitting: false, error: '' }
}
function closeDeleteAssetModal() {
  if (deleteAssetModal.value.submitting) return
  deleteAssetModal.value.open = false
  deleteAssetModal.value.error = ''
}
async function submitDeleteAsset() {
  const asset = selectedDatasetAsset.value
  if (!asset) return
  if (deleteAssetModal.value.confirmName !== asset.name) {
    deleteAssetModal.value.error = '名称不一致'
    return
  }
  // #15：删之前先存好名字，删完详情面板会卸载，提示要用页面级 pageNotice 展示
  const assetName = asset.name
  deleteAssetModal.value.submitting = true
  deleteAssetModal.value.error = ''
  try {
    await datasetAssetApi.remove(asset.id)
    deleteAssetModal.value.open = false
    lifecycleMessage.value = ''
    selectedDatasetAssetId.value = ''
    datasetVersions.value = []
    await loadDatasetAssets()
    showPageNotice(`已永久删除数据集「${assetName}」`)
  } catch (err) {
    deleteAssetModal.value.error = lifecycleErrorMessage(err, '删除失败')
  } finally {
    deleteAssetModal.value.submitting = false
  }
}

// ===== 规则 4：丢弃已发布资产上的 v+1 未发布版本（仅 owner）=====
function openDiscardVersionModal(version: DatasetVersion) {
  if (!canDiscardVersion(version)) return
  discardVersionModal.value = {
    open: true,
    versionId: version.id,
    versionLabel: version.version_label,
    submitting: false,
    error: '',
  }
}
function closeDiscardVersionModal() {
  if (discardVersionModal.value.submitting) return
  discardVersionModal.value.open = false
  discardVersionModal.value.error = ''
}
async function submitDiscardVersion() {
  const versionId = discardVersionModal.value.versionId
  if (!versionId) return
  discardVersionModal.value.submitting = true
  discardVersionModal.value.error = ''
  try {
    await datasetVersionApi.discardDraft(versionId)
    discardVersionModal.value.open = false
    lifecycleMessage.value = '已丢弃未发布版本'
    await Promise.all([loadDatasetAssets(), loadSelectedAssetVersions()])
  } catch (err) {
    discardVersionModal.value.error = lifecycleErrorMessage(err, '丢弃失败')
  } finally {
    discardVersionModal.value.submitting = false
  }
}

async function loadSelectedAssetRecordings() {
  const asset = selectedDatasetAsset.value
  const context = recordsStudyContext.value
  recordingsError.value = ''
  selectedAssetRecordings.value = []
  expandedRecordingIds.value = []
  recordingFilesById.value = {}
  recordingFilesLoading.value = {}
  recordingFilesError.value = {}
  if (!asset || !context) return

  isLoadingRecordings.value = true
  try {
    const res = await recordingApi.list(context.studyId, {
      dataset_asset_id: asset.id,
      mount_id: context.mountId,
      mount_name: context.mountName,
    })
    selectedAssetRecordings.value = res.data.recordings
      .map(normalizeRecording)
      .sort((a, b) => getDateValue(b.updatedAt) - getDateValue(a.updatedAt))
  } catch (err: any) {
    selectedAssetRecordings.value = []
    recordingsError.value = getRecordingErrorMessage(err)
  } finally {
    isLoadingRecordings.value = false
  }
}

function resetRecordsView() {
  selectedAssetRecordings.value = []
  expandedRecordingIds.value = []
  recordingFilesById.value = {}
  recordingFilesLoading.value = {}
  recordingFilesError.value = {}
  recordingsError.value = ''
}

function normalizeRecording(recording: Recording): DatasetRecordingRow {
  return {
    id: recording.id,
    subject: recording.bids_subject_id || recording.subject_id || '-',
    session: recording.session || null,
    task: recording.task || '-',
    run: recording.run || null,
    sourceFormat: formatSourceFormat(recording.source_format),
    currentVersionLabel: getCurrentVersionLabel(recording),
    hasCanonicalFif: Boolean(recording.fif_path || recording.current_version_id),
    channelEventLabel: formatChannelEvent(recording.n_channels, recording.n_events),
    qaStatus: recording.qa_status || null,
    updatedAt: getRecordingUpdatedAt(recording),
    fileSize: recording.file_size || null,
    datasetAssetId: recording.dataset_asset_id || null,
  }
}

function isRecordingExpanded(recording: DatasetRecordingRow) {
  return expandedRecordingIds.value.includes(recording.id)
}

async function toggleRecordingExpanded(recording: DatasetRecordingRow) {
  if (isRecordingExpanded(recording)) {
    expandedRecordingIds.value = expandedRecordingIds.value.filter((id) => id !== recording.id)
    return
  }
  expandedRecordingIds.value = [...expandedRecordingIds.value, recording.id]
  await loadRecordingFiles(recording)
}

async function loadRecordingFiles(recording: DatasetRecordingRow, force = false) {
  const context = recordsStudyContext.value
  if (!context) return
  if (!force && recordingFilesById.value[recording.id]) return

  setRecordingFileLoading(recording.id, true)
  setRecordingFileError(recording.id, '')
  try {
    const res = await recordingApi.listFiles(context.studyId, recording.id)
    recordingFilesById.value = {
      ...recordingFilesById.value,
      [recording.id]: res.data.files,
    }
  } catch (err: any) {
    setRecordingFileError(recording.id, getRecordingFilesErrorMessage(err))
    recordingFilesById.value = {
      ...recordingFilesById.value,
      [recording.id]: [],
    }
  } finally {
    setRecordingFileLoading(recording.id, false)
  }
}

function setRecordingFileLoading(recordingId: string, value: boolean) {
  recordingFilesLoading.value = {
    ...recordingFilesLoading.value,
    [recordingId]: value,
  }
}

function setRecordingFileError(recordingId: string, value: string) {
  recordingFilesError.value = {
    ...recordingFilesError.value,
    [recordingId]: value,
  }
}

function resetFileIndexView(clearFilters = false) {
  fileDisplayLimit.value = FILE_INDEX_PAGE_SIZE
  if (!clearFilters) return
  fileSearch.value = ''
  fileRoleFilter.value = 'all'
}

function showMoreAssetFiles() {
  fileDisplayLimit.value += FILE_INDEX_PAGE_SIZE
}

function selectDatasetAsset(assetId: string) {
  if (selectedDatasetAssetId.value === assetId) {
    activePanel.value = 'catalog'
    activeTab.value = 'overview'
    return
  }
  selectedDatasetAssetId.value = assetId
  activePanel.value = 'catalog'
  activeTab.value = 'overview'
  clearBootstrapResult()
}

function openCreatePanel() {
  resetDatasetCreateForm()
  activePanel.value = 'create'
  activeTab.value = 'overview'
}

function returnToDatasetWorkbench() {
  activePanel.value = 'catalog'
  activeTab.value = 'overview'
  clearBootstrapResult()
}

function resetDatasetCreateForm() {
  const defaults = buildTestDatasetDefaults()
  datasetName.value = defaults.name
  datasetCode.value = defaults.code
  datasetDescription.value = defaults.description
  mountName.value = 'primary'
  clearBootstrapResult()
}

function buildTestDatasetDefaults() {
  const now = new Date()
  const stamp = formatDatasetDraftStamp(now)
  return {
    name: `测试数据集 ${stamp}`,
    code: `test-dataset-${stamp}`,
    description: `用于测试 Dataset-first 导入流程的临时数据集，生成时间：${formatDate(now.toISOString())}。`,
  }
}

function formatDatasetDraftStamp(date: Date) {
  const parts = [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
    String(date.getHours()).padStart(2, '0'),
    String(date.getMinutes()).padStart(2, '0'),
    String(date.getSeconds()).padStart(2, '0'),
  ]
  return `${parts[0]}${parts[1]}${parts[2]}-${parts[3]}${parts[4]}${parts[5]}`
}

async function bootstrapDataset() {
  if (!canCreateDataset.value || isBootstrapping.value) return
  isBootstrapping.value = true
  bootstrapError.value = ''
  bootstrapSuccess.value = ''
  try {
    const res = await datasetAssetApi.bootstrap({
      dataset: {
        name: datasetName.value,
        code: sanitizeCode(datasetCode.value),
        description: datasetDescription.value || null,
        visibility: 'private',
        metadata_json: {},
      },
      paired_study: buildPairedStudyPayload(),
      mount_name: sanitizeCode(mountName.value || 'primary'),
      selection_json: {},
      is_active: true,
    })
    bootstrapResponse.value = res.data
    mountedTarget.value = null
    selectedStudyId.value = res.data.study.id
    selectedDatasetAssetId.value = res.data.dataset_asset.id
    activePanel.value = 'catalog'
    activeTab.value = 'import'
    bootstrapSuccess.value = '数据集已创建，并已准备为导入目标。'
    await Promise.all([loadStudies(), loadDatasetAssets()])
    await loadSelectedAssetFiles()
    await scrollToUploadSection()
  } catch (err: any) {
    bootstrapResponse.value = null
    mountedTarget.value = null
    bootstrapError.value = getErrorMessage(err)
  } finally {
    isBootstrapping.value = false
  }
}

async function mountExistingDatasetAsset() {
  const asset = selectedDatasetAsset.value
  if (!asset || isBootstrapping.value) return
  isBootstrapping.value = true
  bootstrapError.value = ''
  bootstrapSuccess.value = ''
  try {
    const study = await ensureTargetStudy(asset)
    const mount = await ensureStudyDatasetMount(study, asset)
    bootstrapResponse.value = null
    mountedTarget.value = { asset, study, mount }
    selectedStudyId.value = study.id
    activeTab.value = 'import'
    bootstrapSuccess.value = '数据集已设为导入目标。'
    await loadStudies()
    await scrollToUploadSection()
  } catch (err: any) {
    mountedTarget.value = null
    bootstrapError.value = getErrorMessage(err)
  } finally {
    isBootstrapping.value = false
  }
}

async function ensureTargetStudy(asset: DatasetAsset) {
  if (usesShortcutStudy.value) {
    const study = selectedStudy.value
    if (study) return study
    return {
      id: selectedStudyId.value,
      code: selectedStudyId.value,
      name: selectedStudyId.value,
      description: null,
      status: 'active',
      owner_id: '',
      bids_root: '',
      storage_quota_bytes: 0,
      created_at: null,
      updated_at: null,
    } satisfies Study
  }
  const reusableStudy = await findReusablePairedStudy(asset)
  if (reusableStudy) return reusableStudy
  return createAutoPairedStudy(asset)
}

async function findReusablePairedStudy(asset: DatasetAsset) {
  const targetCode = trimStudyCode(resolvedPairedStudyCode(asset))
  const study = studies.value.find((item) => item.code === targetCode)
  if (!study) return null
  const mounts = await loadStudyDatasetMounts(study.id)
  const targetMountName = sanitizeCode(mountName.value || 'primary')
  const sameMount = mounts.find(
    (item) => item.dataset_asset_id === asset.id && item.mount_name === targetMountName,
  )
  if (sameMount) return study
  const hasMountNameConflict = mounts.some(
    (item) => item.is_active && item.mount_name === targetMountName && item.dataset_asset_id !== asset.id,
  )
  return hasMountNameConflict ? null : study
}

async function ensureStudyDatasetMount(study: Study, asset: DatasetAsset) {
  const targetMountName = sanitizeCode(mountName.value || 'primary')
  const mounts = await loadStudyDatasetMounts(study.id)
  const existingMount = mounts.find(
    (item) => item.dataset_asset_id === asset.id && item.mount_name === targetMountName,
  )
  if (existingMount) {
    if (existingMount.is_active) return existingMount
    const res = await studyDatasetMountApi.update(study.id, existingMount.id, { is_active: true })
    return res.data
  }
  const res = await studyDatasetMountApi.create(study.id, {
    dataset_asset_id: asset.id,
    mount_name: targetMountName,
    selection_json: {},
    is_active: true,
  })
  return res.data
}

async function loadStudyDatasetMounts(studyId: string) {
  try {
    const res = await studyDatasetMountApi.list(studyId)
    return res.data.mounts
  } catch {
    return [] as StudyDatasetMount[]
  }
}

async function createAutoPairedStudy(asset: DatasetAsset) {
  let lastConflict: any = null
  for (const code of pairedStudyCodeCandidates(asset)) {
    try {
      const res = await studyApi.create({
        code,
        name: resolvedPairedStudyName(asset),
        description: null,
        storage_quota_gb: 1024,
      })
      const study = res.data
      studies.value = [study, ...studies.value.filter((item) => item.id !== study.id)]
      return study
    } catch (err: any) {
      if (!isStudyCodeConflict(err)) throw err
      lastConflict = err
    }
  }
  throw lastConflict || new Error('Failed to create processing workspace')
}

function buildPairedStudyPayload() {
  if (usesShortcutStudy.value) {
    return {
      mode: 'existing' as const,
      study_id: selectedStudyId.value,
    }
  }
  return {
    mode: 'create' as const,
    code: resolvedPairedStudyCode(),
    name: resolvedPairedStudyName(),
    description: null,
    storage_quota_gb: 1024,
  }
}

function pairedStudyCodeCandidates(asset: DatasetAsset) {
  const baseCode = trimStudyCode(resolvedPairedStudyCode(asset))
  const assetSuffix = asset.id.slice(0, 8)
  const timeSuffix = new Date().toISOString().replace(/\D/g, '').slice(0, 14)
  return Array.from(
    new Set([
      baseCode,
      withStudyCodeSuffix(baseCode, assetSuffix),
      withStudyCodeSuffix(baseCode, timeSuffix),
    ].filter(Boolean)),
  )
}

function resolvedPairedStudyName(asset?: DatasetAsset) {
  const baseName = asset?.name || datasetName.value
  return baseName ? `${baseName} 处理工作空间` : '数据集处理工作空间'
}

function resolvedPairedStudyCode(asset?: DatasetAsset) {
  const baseCode = asset?.code || datasetCode.value
  return sanitizeCode(baseCode ? `${baseCode}-study` : 'dataset-study')
}

function withStudyCodeSuffix(baseCode: string, suffix: string) {
  const cleanSuffix = sanitizeCode(suffix)
  const maxBaseLength = Math.max(1, STUDY_CODE_MAX_LENGTH - cleanSuffix.length - 1)
  const cleanBase = trimStudyCode(baseCode).slice(0, maxBaseLength).replace(/[-_]+$/g, '')
  return `${cleanBase || 'dataset'}-${cleanSuffix}`.slice(0, STUDY_CODE_MAX_LENGTH)
}

function trimStudyCode(value: string) {
  return sanitizeCode(value).slice(0, STUDY_CODE_MAX_LENGTH).replace(/[-_]+$/g, '') || 'dataset-study'
}

function isStudyCodeConflict(err: any) {
  return err.response?.status === 409
}

function queryString(value: unknown) {
  if (Array.isArray(value)) return typeof value[0] === 'string' ? value[0] : ''
  return typeof value === 'string' ? value : ''
}

function sanitizeCode(value: string) {
  return value
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^A-Za-z0-9-_]/g, '')
    .replace(/-+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')
}

function getErrorMessage(err: any) {
  const detail = err.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join('，')
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (err.response?.status) return `准备失败 (HTTP ${err.response.status})`
  return err.message ? `准备失败：${err.message}` : '准备失败'
}

function clearBootstrapResult() {
  bootstrapResponse.value = null
  mountedTarget.value = null
  bootstrapSuccess.value = ''
  bootstrapError.value = ''
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

async function scrollToUploadSection() {
  await nextTick()
  uploadSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function scrollToUploadPanel() {
  await nextTick()
  uploadPanelRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function sortedAssets(assets: DatasetAsset[]) {
  return [...assets].sort((a, b) => getDateValue(b.updated_at || b.created_at) - getDateValue(a.updated_at || a.created_at))
}

function getDateValue(value?: string | null) {
  if (!value) return 0
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? 0 : time
}

function formatDate(value?: string | null) {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// UI Phase (docs_v2/6-05): 数据概要展示用 helper
function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '0 分'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (hours < 24) return mins ? `${hours} 时 ${mins} 分` : `${hours} 时`
  const days = Math.floor(hours / 24)
  const h = hours % 24
  return h ? `${days} 天 ${h} 时` : `${days} 天`
}

function formatRelative(value?: string | null): string {
  if (!value) return '尚未导入'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const diffMs = Date.now() - date.getTime()
  if (diffMs < 0) return formatDate(value)
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return '刚刚'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH} 小时前`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 30) return `${diffD} 天前`
  return formatDate(value)
}

async function copyDoi(doi: string) {
  try {
    await navigator.clipboard.writeText(doi)
    lifecycleMessage.value = `已复制 DOI 到剪贴板：${doi}`
  } catch {
    lifecycleMessage.value = `DOI：${doi}（剪贴板写入失败，请手动复制）`
  }
}

function formatProcessingWorkspaceName(value?: string | null) {
  if (!value) return '处理工作空间已准备'
  return value.replace(/\s*Study$/i, ' 处理工作空间')
}

// 6-05 §9：内部版本标识 "working" 对用户翻成"工作版本"；已发布版本保留其 SemVer 号（如 1.0.0）
function formatVersionLabel(label?: string | null) {
  if (!label || label === 'working') return '工作版本'
  return label
}

// 6-05 B 方案：可见范围徽章配色（开放度递增：私有→灰中性，共享→主色蓝，公开→成功绿）
function getVisibilityClass(visibility: string) {
  if (visibility === 'public') return 'badge--success'
  if (visibility === 'shared') return 'badge--primary'
  return 'badge--outline'
}

function getVisibilityLabel(visibility: string) {
  const labels: Record<string, string> = {
    private: '私有',
    shared: '共享',
    public: '公开',
  }
  return labels[visibility] || visibility
}

function formatSourceFormat(value?: string | null) {
  if (!value) return '未知'
  const normalized = value.toLowerCase()
  if (normalized === 'brainvision') return 'BrainVision'
  return value.toUpperCase()
}

function getCurrentVersionLabel(recording: Recording) {
  if (recording.current_version_seq != null) return `v${recording.current_version_seq}`
  if (recording.current_version_id) return '当前版本'
  return '待生成'
}

function getRecordingUpdatedAt(recording: Recording) {
  const withTimestamps = recording as Recording & { updated_at?: string | null; created_at?: string | null }
  return withTimestamps.updated_at || recording.imported_at || withTimestamps.created_at || null
}

function formatChannelEvent(channels?: number | null, events?: number | null) {
  const channelLabel = channels == null ? '-' : `${channels} ch`
  const eventLabel = events == null ? '-' : `${events} evt`
  return `${channelLabel} / ${eventLabel}`
}

function isQaPassed(status?: string | null) {
  const normalized = (status || '').toLowerCase()
  return ['pass', 'passed', 'ok', 'accepted', 'approved'].includes(normalized)
}

function getQaStatusLabel(status?: string | null) {
  const normalized = (status || '').toLowerCase()
  const labels: Record<string, string> = {
    pass: '通过',
    passed: '通过',
    ok: '通过',
    accepted: '通过',
    approved: '通过',
    pending: '待质控',
    queued: '待质控',
    failed: '未通过',
    fail: '未通过',
    rejected: '未通过',
    warning: '需复核',
    review: '需复核',
  }
  return labels[normalized] || status || '未质控'
}

function getQaStatusClass(status?: string | null) {
  const normalized = (status || '').toLowerCase()
  if (isQaPassed(normalized)) return 'badge--success'
  if (['failed', 'fail', 'rejected'].includes(normalized)) return 'badge--danger'
  if (['warning', 'review'].includes(normalized)) return 'badge--warning'
  return 'badge--outline'
}

function getRecordingErrorMessage(err: any) {
  const detail = err.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join('，')
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (err.response?.status) {
    return `采集记录读取失败 (HTTP ${err.response.status})。`
  }
  return err.message ? `采集记录读取失败：${err.message}` : '采集记录读取失败'
}

function getRecordingFilesErrorMessage(err: any) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (err.response?.status) return `文件列表读取失败 (HTTP ${err.response.status})`
  return err.message ? `文件列表读取失败：${err.message}` : '文件列表读取失败'
}

function countFilesByRole(files: DatasetFile[], keywords: string[]) {
  return files.filter((file) => {
    const role = file.file_role.toLowerCase()
    return keywords.some((keyword) => role.includes(keyword))
  }).length
}

function getFileDisplayPath(file: DatasetFile) {
  return file.logical_path || file.relative_path || file.id
}

function getFileShortPath(file: DatasetFile) {
  const path = normalizeFilePath(getFileDisplayPath(file))
  const parts = path.split('/').filter(Boolean)
  if (parts.length <= 3) return path
  return parts.slice(-3).join('/')
}

function getFileFullLogicalPath(file: DatasetFile) {
  return file.logical_path ? normalizeFilePath(file.logical_path) : '未返回 logical_path'
}

function getFileRelativePath(file: DatasetFile) {
  return file.relative_path ? normalizeFilePath(file.relative_path) : '未返回 relative_path'
}

function getFileRoleLabel(role: string) {
  const normalized = role.toLowerCase()
  if (normalized.includes('original') || normalized.includes('upload')) return 'original'
  if (normalized.includes('raw') || normalized.includes('bids')) return 'Raw BIDS'
  if (normalized.includes('fif') || normalized.includes('canonical')) return 'canonical FIF'
  return role
}

function getFileRoleGroup(file: DatasetFile): DatasetFileRoleFilter {
  const normalized = file.file_role.toLowerCase()
  if (normalized.includes('original') || normalized.includes('upload') || normalized.includes('source')) {
    return 'original'
  }
  if (normalized.includes('raw') || normalized.includes('bids')) return 'raw-bids'
  if (normalized.includes('fif') || normalized.includes('canonical')) return 'canonical-fif'
  return 'other'
}

function matchesFileRoleFilter(file: DatasetFile, filter: DatasetFileRoleFilter) {
  return filter === 'all' || getFileRoleGroup(file) === filter
}

function normalizeFilePath(path: string) {
  return path.replace(/\\/g, '/')
}

function formatFileSize(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}
</script>

<style scoped>
.dataset-page__header {
  align-items: flex-start;
  gap: var(--s-4);
}

/* 统计条与下方主区之间留块级间距（原为 0，上下太挤）*/
.page-stat-strip {
  margin-bottom: var(--s-6);
}

.dataset-page__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.admin-link {
  border-color: var(--c-warning-soft) !important;
  background: var(--c-warning-soft) !important;
  color: var(--c-warning) !important;
  text-decoration: none;
}
.admin-link:hover {
  background: var(--c-warning-soft) !important;
}

/* .dataset-overview 已由通用 .page-stat-strip 替代（见 style.css） */
.dataset-shortcut,
.dataset-current-target,
.dataset-workbench {
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  box-shadow: var(--shadow-sm);
}

.dataset-meta-grid span,
.dataset-decision-panel span,
.dataset-summary-grid span,
.dataset-overview-action span,
.dataset-file-stats span,
.dataset-file-toolbar span,
.dataset-file-detail span,
.dataset-record-stats span,
.dataset-record-main span,
.dataset-record-detail-grid span,
.dataset-record-files-head span,
.dataset-mount-field span,
.dataset-target-summary span,
.dataset-technical-grid span {
  display: block;
  color: var(--c-text-3);
  font-size: 12px;
}

/* .dataset-overview 系列样式（dataset-overview, __main, __current, __metrics, strong/small）
   已统一替换为通用 .page-stat-strip / .page-stat，见 style.css。 */

.dataset-shortcut {
  display: flex;
  align-items: flex-start;
  gap: var(--s-3);
  margin-bottom: var(--s-4);
  padding: var(--s-3) var(--s-4);
  color: var(--c-text-2);
}

.dataset-shortcut strong {
  display: block;
  margin-bottom: 2px;
  color: var(--c-text);
}

.dataset-workbench {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  min-height: 560px;
  margin-bottom: var(--s-5);
  overflow: hidden;
}

.dataset-catalog {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 10px;
  padding: 12px;
  border-right: 1px solid var(--c-border);
  /* 左侧目录面板用白色，与灰色页面背景(--c-bg-soft)拉开；与右侧详情靠 border-right 分隔 */
  background: var(--c-surface);
}

.dataset-catalog__head,
.dataset-detail__head,
.dataset-panel-head,
.dataset-row__top,
.dataset-action-bar,
.dataset-target-panel {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--s-3);
}

.dataset-catalog__head h2,
.dataset-detail__head h2,
.dataset-panel-head h3,
.dataset-profile h3,
.dataset-target-panel h3 {
  margin: 0;
}

.dataset-catalog__head p,
.dataset-panel-head p,
.dataset-profile p,
.dataset-target-panel p {
  margin: 4px 0 0;
  color: var(--c-text-2);
  font-size: 13px;
  line-height: 1.55;
}

.dataset-catalog__head h2 {
  font-size: 18px;
  line-height: 1.2;
}

.dataset-catalog__head p {
  font-size: 12px;
}

.dataset-catalog__filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(92px, 108px);
  gap: var(--s-2);
}

.dataset-search {
  height: 34px;
  display: flex;
  align-items: center;
  gap: var(--s-2);
  padding: 0 10px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  color: var(--c-text-3);
}

.dataset-catalog__filters .input {
  min-height: 34px;
  height: 34px;
  padding: 0 10px;
  font-size: 13px;
}

.dataset-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--c-text);
  font: inherit;
}

.dataset-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 6px;
  overflow-y: auto;
  padding-right: 2px;
}

.dataset-list-empty,
.dataset-detail-empty {
  min-height: 120px;
  display: grid;
  place-items: center;
  gap: var(--s-2);
  padding: var(--s-4);
  color: var(--c-text-3);
  text-align: center;
  background: var(--c-bg);
  border: 1px dashed var(--c-border);
  border-radius: var(--r);
}

.dataset-row {
  width: 100%;
  min-width: 0;
  display: grid;
  gap: 6px;
  padding: 10px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  color: var(--c-text);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--t-fast), background var(--t-fast), box-shadow var(--t-fast);
}

.dataset-row:hover,
.dataset-row.is-active {
  border-color: rgba(63, 94, 143, .42);
  background: var(--c-primary-soft);
}

.dataset-row.is-active {
  box-shadow: inset 3px 0 0 var(--c-primary), 0 8px 18px rgba(63, 94, 143, .08);
}

.dataset-row strong {
  min-width: 0;
  font-size: 14px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.dataset-row__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-2);
  color: var(--c-text-2);
  font-size: 12px;
}

/* UI Phase (docs_v2/6-05) 列表概要预览 */
.dataset-row__emoji {
  color: var(--c-text-2);
  margin-right: 2px;
}
.dataset-row__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--c-text-2);
  font-size: 12px;
  margin: 4px 0 2px;
}
.dataset-row__summary span {
  white-space: nowrap;
}

.dataset-row__meta span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataset-row__meta span:last-child {
  flex: 0 0 auto;
  color: var(--c-text-3);
  font-size: 11px;
}

.dataset-detail {
  min-width: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  grid-template-columns: minmax(0, 1fr); /* 单列定宽：详情内容不被任一 tab 的内容撑出不同宽度 */
  gap: var(--s-3);
  padding: var(--s-4);
}

.dataset-detail--create {
  background: #fbfcff;
}

.dataset-detail--create .dataset-detail__head {
  align-items: center;
  padding: 12px var(--s-4);
  border: 1px solid #cbdcff;
  border-radius: var(--r);
  background: #f5f8ff;
}

.dataset-detail--create .dataset-detail__head h2 {
  font-size: 20px;
  line-height: 1.25;
}

.dataset-detail__subtitle {
  margin: 4px 0 0;
  color: var(--c-text-2);
  font-size: 12px;
  line-height: 1.55;
}

.dataset-detail__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-2);
}

.section-kicker {
  display: block;
  margin-bottom: 4px;
  color: var(--c-primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.dataset-create-form,
.dataset-detail__body {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr); /* 同上：tab 区整体单列定宽 */
  align-content: start;
  gap: var(--s-3);
}

.dataset-create-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-3);
  padding: 10px 12px;
  border: 1px solid #d7e3ff;
  border-radius: var(--r);
  background: #fff;
  box-shadow: inset 3px 0 0 var(--c-primary);
}

.dataset-create-intro h3 {
  margin: 0;
  color: var(--c-text);
  font-size: 15px;
  line-height: 1.3;
}

.dataset-create-intro p {
  margin: 3px 0 0;
  color: var(--c-text-2);
  font-size: 12px;
  line-height: 1.45;
}

.dataset-create-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.dataset-create-steps span {
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  border: 1px solid #d7e3ff;
  border-radius: 999px;
  background: #f5f8ff;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
  padding: 0 9px;
  white-space: nowrap;
}

.dataset-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-2);
  padding: 4px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.dataset-tab {
  min-height: 34px;
  padding: 0 var(--s-3);
  border: 1px solid transparent;
  border-radius: calc(var(--r) - 2px);
  background: transparent;
  color: var(--c-text-2);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background var(--t-fast), border-color var(--t-fast), color var(--t-fast);
}

.dataset-tab:hover,
.dataset-tab.is-active {
  border-color: rgba(63, 94, 143, .18);
  background: var(--c-surface);
  color: var(--c-primary);
}

.dataset-tab-panel {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr); /* 每个 tab 面板等宽：彻底消除切 tab 时的左右跳动 */
  align-content: start;
  gap: var(--s-4);
}

.dataset-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--s-4);
}

.dataset-form-grid--create {
  padding: 12px;
  border: 1px solid #dfe8ff;
  border-radius: var(--r);
  background: var(--c-surface);
}

.dataset-advanced-settings,
.dataset-technical-details {
  min-width: 0;
  grid-column: 1 / -1;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.dataset-advanced-settings summary,
.dataset-technical-details summary {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-3);
  padding: 0 var(--s-3);
  color: var(--c-text-2);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.dataset-advanced-settings summary small,
.dataset-technical-details summary small {
  color: var(--c-text-3);
  font-weight: 500;
}

.dataset-advanced-settings .field,
.dataset-advanced-settings .dataset-mount-field {
  padding: 0 var(--s-3) var(--s-3);
}

.dataset-mount-field small {
  color: var(--c-text-3);
  font-size: 12px;
  line-height: 1.5;
}

.field--wide {
  grid-column: 1 / -1;
}

.dataset-action-bar {
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.dataset-detail--create .dataset-action-bar {
  border-color: #cbdcff;
  background: #f5f8ff;
}

.dataset-action-bar span {
  color: var(--c-text-2);
  font-size: 13px;
}

.dataset-profile {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--s-4);
}

.dataset-profile__badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--s-2);
}


.dataset-meta-grid,
.dataset-decision-panel,
.dataset-summary-grid,
.dataset-file-stats,
.import-scope,
.dataset-target-summary,
.dataset-technical-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--s-2);
}

.dataset-meta-grid div,
.dataset-decision-panel div,
.dataset-summary-grid div,
.dataset-file-stats div,
.import-scope div,
.dataset-target-summary div,
.dataset-technical-grid div {
  min-width: 0;
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg);
}

.dataset-meta-grid strong,
.dataset-decision-panel strong,
.dataset-summary-grid strong,
.dataset-file-stats strong,
.dataset-record-stats strong,
.dataset-record-main strong,
.dataset-record-detail-grid strong,
.dataset-record-files-head strong,
.import-scope strong,
.dataset-target-summary strong,
.dataset-technical-grid strong {
  display: block;
  margin-top: 4px;
  color: var(--c-text);
  font-size: 13px;
  overflow-wrap: anywhere;
}

.dataset-decision-panel {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.dataset-decision-panel div {
  background: var(--c-surface);
}

.dataset-decision-panel strong {
  font-size: 15px;
}

.dataset-decision-panel p {
  margin: 6px 0 0;
  color: var(--c-text-2);
  font-size: 12px;
  line-height: 1.55;
}

.dataset-decision-panel.is-ready {
  border-color: rgba(16, 185, 129, .28);
  background: #f6fefb;
}

.dataset-decision-panel.is-partial,
.dataset-decision-panel.is-warning {
  border-color: rgba(245, 158, 11, .3);
  background: var(--c-warning-soft);
}

.dataset-decision-panel.is-empty,
.dataset-decision-panel.is-syncing {
  border-color: rgba(63, 94, 143, .2);
  background: var(--c-primary-soft);
}

.dataset-summary-grid--identity,
.dataset-summary-grid--files {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}

.dataset-summary-grid__desc {
  grid-column: 1 / -1;
}

.dataset-summary-grid__desc strong {
  white-space: pre-wrap;
  line-height: 1.55;
}

.dataset-overview-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-3);
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.dataset-overview-action strong {
  display: block;
  margin-top: 4px;
  color: var(--c-text);
  font-size: 14px;
}

.dataset-overview-action p {
  margin: 4px 0 0;
  color: var(--c-text-2);
  font-size: 12px;
  line-height: 1.55;
}

.dataset-file-panel,
.dataset-record-panel {
  display: grid;
  gap: var(--s-3);
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.dataset-file-stats {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}

.dataset-record-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--s-2);
}

.dataset-record-stats div {
  min-width: 0;
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
}

.dataset-record-list {
  display: grid;
  gap: var(--s-2);
}

.dataset-record-row {
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  overflow: hidden;
}

.dataset-record-main {
  width: 100%;
  min-width: 0;
  display: grid;
  grid-template-columns:
    minmax(140px, 1.25fr)
    minmax(82px, .7fr)
    minmax(72px, .55fr)
    minmax(96px, .75fr)
    minmax(82px, .7fr)
    minmax(90px, .75fr)
    minmax(118px, .9fr)
    auto;
  align-items: center;
  gap: var(--s-2);
  padding: var(--s-2) var(--s-3);
  border: 0;
  background: transparent;
  text-align: left;
}

.dataset-record-main:hover {
  background: var(--c-bg-soft);
}

.dataset-record-main > div,
.dataset-record-identity {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.dataset-record-identity strong,
.dataset-record-main strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataset-record-toggle {
  justify-self: end;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
}

.dataset-record-detail {
  display: grid;
  gap: var(--s-3);
  padding: var(--s-3);
  border-top: 1px solid var(--c-border);
  background: var(--c-bg-soft);
}

.dataset-record-detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--s-2);
}

.dataset-record-detail-grid div,
.dataset-record-files-panel {
  min-width: 0;
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
}

.dataset-record-files-panel {
  display: grid;
  gap: var(--s-2);
}

.dataset-record-files-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--s-3);
}

.dataset-record-files {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.dataset-record-files li {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: var(--s-2);
  padding: var(--s-2);
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-bg);
}

.dataset-record-files li span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--c-text-2);
  font-size: 12px;
}

.dataset-record-files li strong,
.dataset-record-files li small {
  color: var(--c-text);
  font-size: 12px;
  white-space: nowrap;
}

.dataset-file-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(160px, 220px) minmax(110px, auto);
  align-items: end;
  gap: var(--s-2);
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
}

.dataset-file-search,
.dataset-file-filter {
  display: grid;
  gap: 6px;
}

.dataset-file-search div {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  padding-left: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg);
}

.dataset-file-search .input {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.dataset-file-counter {
  min-height: 40px;
  display: grid;
  align-content: center;
  padding: 0 var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg);
}

.dataset-file-counter strong {
  color: var(--c-text);
  font-size: 14px;
}

.dataset-target-summary {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.dataset-technical-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  padding: var(--s-3);
}

.dataset-technical-grid div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  column-gap: var(--s-2);
}

.dataset-technical-grid span,
.dataset-technical-grid strong {
  grid-column: 1;
}

.dataset-copy-btn {
  grid-column: 2;
  grid-row: 1 / span 2;
}

.dataset-file-list {
  display: grid;
  gap: var(--s-2);
}

.dataset-file-row {
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-surface);
  overflow: hidden;
}

.dataset-file-row summary {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--s-3);
  padding: var(--s-2) var(--s-3);
  cursor: pointer;
  list-style-position: inside;
}

.dataset-file-name {
  min-width: 0;
  color: var(--c-text-2);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataset-file-meta {
  display: inline-flex;
  align-items: center;
  gap: var(--s-2);
}

.dataset-file-meta strong {
  color: var(--c-text);
  font-size: 12px;
}

.dataset-file-meta small {
  color: var(--c-text-3);
  font-size: 12px;
}

.dataset-file-detail {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--s-2);
  padding: var(--s-3);
  border-top: 1px solid var(--c-border);
  background: var(--c-bg-soft);
}

.dataset-file-detail div {
  min-width: 0;
  padding: var(--s-2);
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-bg);
}

.dataset-file-detail strong {
  display: block;
  margin-top: 4px;
  color: var(--c-text);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.dataset-file-more {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-3);
  color: var(--c-text-2);
  font-size: 12px;
}

.dataset-target-panel {
  align-items: center;
  padding: var(--s-3);
  border: 1px solid rgba(63, 94, 143, .24);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.dataset-target-panel.is-ready {
  border-color: rgba(16, 185, 129, .32);
  background: #f7fefb;
}

.dataset-mount-field {
  width: min(220px, 100%);
  display: grid;
  gap: 4px;
}

.dataset-current-target {
  display: grid;
  gap: var(--s-3);
  margin-bottom: var(--s-5);
  padding: var(--s-4);
}

.dataset-upload-panel-anchor {
  scroll-margin-top: var(--s-4);
}

.import-scope {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.import-scope span {
  display: block;
  color: var(--c-text-3);
  font-size: 11px;
}

.import-scope small {
  display: block;
  margin-top: 2px;
  color: var(--c-text-3);
  overflow-wrap: anywhere;
}

/* ===== 数据文件管理器（filemanager 视图）===== */
.df-assure {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid #CFE2D7;
  border-radius: var(--r);
  background: var(--c-success-soft);
  color: var(--c-success);
  font-size: 13px;
  line-height: 1.6;
}
.df-assure strong { font-weight: 700; }

.df-buckets {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--s-3);
}
.df-bucket {
  padding: 16px 18px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
}
.df-bucket--upload { background: var(--c-primary-soft); border-color: #D2DEED; }
.df-bucket--fif { background: var(--c-success-soft); border-color: #D3E2D3; }
.df-bucket__top { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.df-bucket__ico {
  width: 38px; height: 38px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r); background: #fff; color: var(--c-primary);
}
.df-bucket--fif .df-bucket__ico { color: var(--c-success); }
.df-bucket__top h4 { margin: 0; font-size: 14px; font-weight: 700; }
.df-bucket__top span { font-size: 12px; color: var(--c-text-2); }
.df-bucket__stat { display: flex; align-items: baseline; gap: 8px; margin: 10px 0; }
.df-bucket__stat strong { font-size: 24px; font-weight: 800; }
.df-bucket__stat span { font-size: 13px; color: var(--c-text-2); }
.df-bucket__foot { display: flex; align-items: center; justify-content: space-between; gap: var(--s-2); }
.df-bucket__note { font-size: 11px; color: var(--c-text-3); }

.df-note {
  padding: 10px 14px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
  color: var(--c-text-2);
  font-size: 12px;
  line-height: 1.7;
}

.df-toolbar { display: flex; align-items: center; gap: var(--s-3); }
.df-toolbar__spacer { flex: 1; }
.df-seg {
  display: inline-flex;
  gap: 3px;
  padding: 3px;
  border-radius: var(--r);
  background: var(--c-bg-tint);
}
.df-seg button {
  border: 0;
  border-radius: var(--r-sm);
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-2);
  background: transparent;
  cursor: pointer;
}
.df-seg button.is-active { background: #fff; color: var(--c-primary); box-shadow: var(--shadow-sm); }

.df-view { display: grid; gap: var(--s-3); }

.df-subject {
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: var(--c-surface);
  overflow: hidden;
}
.df-subject__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--c-bg-soft);
  border-bottom: 1px solid var(--c-border);
}
.df-subject__head strong { font-size: 14px; }
.df-subject__meta { margin-left: auto; font-size: 12px; color: var(--c-text-3); }

.df-rec { padding: 14px 16px; border-bottom: 1px solid var(--c-bg-soft); }
.df-rec:last-child { border-bottom: 0; }
.df-rec__title { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.df-rec__title b { font-size: 14px; }
.df-chip {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-primary);
  background: var(--c-primary-soft);
  border-radius: var(--r-sm);
  padding: 2px 8px;
}
.df-bids-ok {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--c-success);
}

.df-data-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  margin-bottom: 8px;
  border: 1px solid var(--c-border);
  border-radius: var(--r);
}
.df-data-row:last-child { margin-bottom: 0; }
.df-data-row--upload { background: var(--c-primary-soft); border-color: #D9E3EF; }
.df-data-row--fif { background: var(--c-success-soft); border-color: #D9E6D9; }
.df-data-row__ico {
  width: 32px; height: 32px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-sm); background: #fff; color: var(--c-primary);
}
.df-data-row--fif .df-data-row__ico { color: var(--c-success); }
.df-data-row__main { flex: 1; min-width: 0; }
.df-data-row__main strong { display: block; font-size: 13px; }
.df-data-row__sub { font-size: 12px; color: var(--c-text-2); }
.df-data-row__size { width: 72px; text-align: right; font-size: 13px; font-weight: 700; }

.df-tech { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--c-border); }
.df-tech > summary {
  list-style: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-3);
}
.df-tech > summary::-webkit-details-marker { display: none; }
.df-tech > summary::before { content: "▸"; display: inline-block; transition: transform var(--t-fast); }
.df-tech[open] > summary::before { transform: rotate(90deg); }
.df-tech--global {
  margin-top: 0;
  padding: 14px 16px;
  border: 1px solid var(--c-border);
  border-top: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: var(--c-surface);
}
.df-tech__list { margin-top: 10px; }
.df-tech__hint { font-size: 11px; color: var(--c-text-3); line-height: 1.7; margin-bottom: 8px; }
.df-tech__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  font-size: 12px;
  border-bottom: 1px solid var(--c-bg-soft);
}
.df-tech__item:last-child { border-bottom: 0; }
.df-tech__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--ff-mono);
  color: var(--c-text-2);
}
.df-tech__role { font-size: 11px; font-weight: 600; color: var(--c-accent); }
.df-tech__size { width: 56px; text-align: right; color: var(--c-text-3); }

.df-type {
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: var(--c-surface);
  overflow: hidden;
}
.df-type__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--c-border);
}
.df-type--upload .df-type__head { background: var(--c-primary-soft); }
.df-type--fif .df-type__head { background: var(--c-success-soft); }
.df-type__head strong { font-size: 14px; }
.df-type__meta { margin-left: auto; font-size: 12px; color: var(--c-text-2); }
.df-type__file {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--c-bg-soft);
}
.df-type__file:last-child { border-bottom: 0; }
.df-type__main { flex: 1; min-width: 0; }
.df-type__main strong { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.df-type__main span { font-size: 12px; color: var(--c-text-3); }
.df-type__size { width: 72px; text-align: right; font-size: 13px; font-weight: 700; }

@media (max-width: 1080px) {
  .dataset-workbench {
    grid-template-columns: 1fr;
  }

  .dataset-catalog {
    border-right: 0;
    border-bottom: 1px solid var(--c-border);
  }

  .dataset-list {
    max-height: 360px;
  }
}

@media (max-width: 1280px) {
  .dataset-record-main {
    grid-template-columns:
      minmax(160px, 1.25fr)
      repeat(3, minmax(86px, .8fr))
      minmax(96px, .8fr)
      auto;
    align-items: start;
  }

  .dataset-record-main > div:nth-of-type(6),
  .dataset-record-main > div:nth-of-type(7) {
    grid-column: span 2;
  }

  .dataset-file-toolbar {
    grid-template-columns: minmax(200px, 1fr) minmax(150px, 200px);
  }

  .dataset-file-counter {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .dataset-overview,
  .dataset-form-grid,
  .dataset-meta-grid,
  .dataset-decision-panel,
  .dataset-summary-grid,
  .dataset-file-stats,
  .dataset-record-stats,
  .dataset-record-detail-grid,
  .import-scope,
  .dataset-target-summary,
  .dataset-technical-grid {
    grid-template-columns: 1fr;
  }

  .dataset-page__header,
  .dataset-create-intro,
  .dataset-profile,
  .dataset-action-bar,
  .dataset-overview-action,
  .dataset-target-panel,
  .dataset-panel-head,
  .dataset-record-files-head,
  .dataset-file-more {
    flex-direction: column;
    align-items: stretch;
  }

  .dataset-create-steps {
    justify-content: flex-start;
  }

  .dataset-create-intro {
    flex-direction: row;
    align-items: center;
  }

  .dataset-form-grid--create {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dataset-form-grid--create .field--wide,
  .dataset-form-grid--create .dataset-advanced-settings {
    grid-column: 1 / -1;
  }

  .dataset-detail--create .dataset-action-bar {
    flex-direction: row;
    align-items: center;
  }

  .dataset-file-toolbar,
  .dataset-file-detail,
  .dataset-record-main,
  .dataset-record-files li {
    grid-template-columns: 1fr;
  }

  .dataset-file-row summary {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .dataset-create-intro {
    flex-direction: column;
    align-items: stretch;
  }

  .dataset-form-grid--create {
    grid-template-columns: 1fr;
  }

  .dataset-detail--create .dataset-action-bar {
    flex-direction: column;
    align-items: stretch;
  }
}

/* Phase 3 (docs_v2/3-25): 版本与发布卡片 */
.dataset-version-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
  border: 1px solid #dde6f4;
  border-radius: 10px;
  background: #fff;
  padding: 16px 18px;
}
.dataset-version-card.state-unpublished {
  border-color: var(--c-warning-soft);
  background: var(--c-warning-soft);
}
.dataset-version-card.state-published {
  border-color: #b7e4c7;
  background: #f3fbf6;
}
.dataset-version-card.state-pending {
  border-color: #ffd5b1;
  background: #fff5ec;
}
.dataset-version-card.state-withdrawn {
  border-color: #fbb6b6;
  background: var(--c-danger-soft);
}
.dataset-version-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.dataset-version-card__header > div:first-child {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}
.dataset-version-card__header strong {
  font-size: 22px;
  color: var(--c-text);
}
.version-state-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: var(--c-bg-tint);
  color: var(--c-text-2);
}
.version-state-pill.state-unpublished {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}
.version-state-pill.state-published {
  background: var(--c-success-soft);
  color: var(--c-success);
}
.version-state-pill.state-pending {
  background: #fff5ec;
  color: #c2410c;
}
.version-state-pill.state-withdrawn {
  background: var(--c-danger-soft);
  color: var(--c-danger);
}
.dataset-version-card__hint {
  margin: 0;
  color: var(--c-text-2);
  font-size: 13px;
  line-height: 1.6;
}
.dataset-version-card__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin: 6px 0 0;
}
.dataset-version-card__meta dt {
  margin: 0;
  color: var(--c-text-3);
  font-size: 12px;
}
.dataset-version-card__meta dd {
  margin: 4px 0 0;
  color: var(--c-text);
  font-weight: 600;
  font-size: 13px;
  word-break: break-all;
}
.dataset-version-card__meta .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  font-weight: 500;
}

/* 数据集生命周期 v2（3-25）：授权用户面板（规则 7 邀请制） */
.dataset-member-panel {
  border: 1px solid var(--c-border);
  border-radius: 14px;
  background: #fff;
  padding: 16px 18px;
  display: grid;
  gap: 12px;
}
.dataset-member-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.dataset-member-panel__head p {
  margin: 6px 0 0;
  color: var(--c-text-2);
  font-size: 13px;
  line-height: 1.6;
}
.dataset-member-add {
  display: flex;
  gap: 8px;
}
.dataset-member-add .input {
  flex: 1;
  min-width: 0;
}
.dataset-member-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}
.dataset-member-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--c-border);
  border-radius: 10px;
  background: var(--c-bg-tint);
}
.dataset-member-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.dataset-member-identity strong {
  font-size: 14px;
  color: var(--c-text);
}
.dataset-member-identity small {
  font-size: 12px;
  color: var(--c-text-3);
}
.dataset-member-identity .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.dataset-member-time {
  font-size: 12px;
  color: var(--c-text-3);
  white-space: nowrap;
}

/* 危险删除区（规则 4：纯未发布资产整体删） */
.dataset-danger-zone {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 18px;
  padding: 16px 18px;
  border: 1px solid var(--c-danger-soft);
  border-radius: 14px;
  background: var(--c-danger-soft);
}
.dataset-danger-zone strong {
  display: block;
  margin: 2px 0;
  font-size: 15px;
  color: var(--c-text);
}
.dataset-danger-zone p {
  margin: 0;
  max-width: 60ch;
  color: var(--c-text-2);
  font-size: 13px;
  line-height: 1.6;
}
.section-kicker--danger {
  color: var(--c-danger);
}

/* 发布合规关口（规则 3） */
.publish-compliance {
  display: grid;
  gap: 12px;
  margin-top: 4px;
  padding: 14px;
  border: 1px solid var(--c-border);
  border-radius: 12px;
  background: var(--c-bg-tint);
}
.publish-compliance__title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text);
}
.publish-compliance__check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--c-text-2);
}
.publish-compliance__check input {
  margin-top: 3px;
  flex-shrink: 0;
}

/* lifecycle 弹窗：modal 基础样式 */
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.45);
  padding: 24px;
}
.modal-card {
  width: min(560px, 100%);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.25);
}
.eyebrow {
  margin: 0 0 4px;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
}
.icon-button {
  width: 32px;
  height: 32px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: #fff;
  color: var(--c-text-2);
  cursor: pointer;
}
.modal-copy {
  margin: 0;
  color: var(--c-text-2);
  line-height: 1.6;
  font-size: 14px;
}
.field-hint {
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 400;
}
.field-hint.is-error {
  color: var(--c-danger);
}
.lifecycle-modal .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 36px;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 0 14px;
  font-weight: 700;
  cursor: pointer;
}
.lifecycle-modal .btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.lifecycle-modal .btn--primary {
  background: var(--c-primary);
  color: #fff;
}
.lifecycle-modal .btn--ghost {
  border-color: var(--c-border);
  background: #fff;
  color: var(--c-text-2);
}
.lifecycle-modal .btn--danger {
  background: var(--c-danger);
  color: #fff;
}

.lifecycle-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px;
}
.lifecycle-modal header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.lifecycle-modal h2 {
  margin: 0;
  color: var(--c-text);
  font-size: 18px;
}
.lifecycle-modal label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--c-text-2);
  font-weight: 700;
}
.lifecycle-modal input,
.lifecycle-modal textarea {
  width: 100%;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--c-text);
  font: inherit;
  outline: none;
}
.lifecycle-modal input.has-error,
.lifecycle-modal textarea.has-error {
  border-color: #fca5a5;
  background: #fffafa;
}
.lifecycle-modal textarea {
  resize: vertical;
}
.lifecycle-modal footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.lifecycle-modal code {
  background: var(--c-bg-tint);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.lifecycle-modal--danger {
  border-top: 4px solid var(--c-danger);
}
.eyebrow--danger {
  color: var(--c-danger);
  text-transform: uppercase;
}
.modal-copy--danger {
  border-left: 3px solid var(--c-danger);
  padding: 10px 12px;
  background: var(--c-danger-soft);
  color: #7f1d1d;
}

/* UI Phase (docs_v2/6-05) L1: 数据概要卡片 */
.data-overview-card {
  margin-top: 16px;
  border: 1px solid var(--c-border);
  border-radius: 10px;
  background: #fff;
  padding: 18px 20px;
}
.data-overview-card__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 14px;
}
.data-overview-card__head .section-kicker {
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
}
.data-overview-card__desc {
  color: var(--c-text-2);
  font-size: 13px;
  line-height: 1.6;
}
.data-overview-card__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 14px;
}
.data-overview-card__imported {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--c-text-3);
}
.data-stat {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--c-bg-soft);
  border-radius: 8px;
  padding: 12px 14px;
}
.data-stat__icon {
  color: var(--c-text-2);
}
.data-stat > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.data-stat strong {
  font-size: 22px;
  font-weight: 700;
  color: var(--c-text);
  line-height: 1.1;
}
.data-stat small {
  color: var(--c-text-3);
  font-size: 12px;
}
.data-overview-card__tasks {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--c-bg-tint);
}
.data-overview-card__tasks-label {
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 700;
}
.task-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 6px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 600;
}

.doi-copy-btn {
  border: 1px solid #c9d9ff;
  background: #f4f8ff;
  color: var(--c-primary);
  padding: 3px 9px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.doi-copy-btn:hover {
  background: var(--c-primary-soft);
}
.dataset-primary-link {
  color: var(--c-primary);
  text-decoration: none;
  font-size: 12px;
  font-weight: 600;
}
.dataset-primary-link:hover {
  text-decoration: underline;
}

/* Phase 3 (docs_v2/3-25) C: 版本时间线 */
.version-timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
  border: 1px solid var(--c-border);
  border-radius: 10px;
  background: #fff;
  padding: 16px 18px;
}
.version-timeline__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.version-timeline__head strong {
  margin-left: 8px;
  color: var(--c-text);
  font-size: 14px;
}
.version-timeline__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.version-timeline__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--c-bg-tint);
  border-radius: 8px;
  background: var(--c-bg-soft);
  padding: 10px 12px;
}
.version-timeline__item.is-current {
  border-color: #c9d9ff;
  background: #f4f8ff;
}
.version-timeline__label {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.version-timeline__label strong {
  font-size: 15px;
  color: var(--c-text);
}
.current-marker {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--c-primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}
.version-timeline__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  color: var(--c-text-3);
  font-size: 12px;
}
.version-timeline__meta .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: var(--c-text-2);
}
.version-timeline__center {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  margin: 0 12px;
  color: var(--c-text-3);
  font-size: 12px;
  min-width: 0;
}
.version-timeline__center .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: var(--c-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.version-timeline__time {
  color: var(--c-text-3);
}
.version-timeline__actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.btn--small {
  min-height: 28px;
  padding: 0 10px;
  font-size: 12px;
}
.version-timeline__hint {
  margin: 0;
  color: var(--c-warning);
  font-size: 12px;
}
</style>
