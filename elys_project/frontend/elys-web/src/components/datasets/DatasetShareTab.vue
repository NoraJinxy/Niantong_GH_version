<template>
  <section class="dataset-tab-panel" aria-label="发布与共享">
    <div class="dataset-profile">
      <div>
        <span class="section-kicker">发布与共享</span>
        <h3>{{ selectedDatasetAsset.name }}</h3>
        <p>管理这个数据集的版本发布、对外可见范围与授权成员。发布会冻结当前文件并生成 DOI（可被论文引用的唯一标识）；发布≠公开，是否对外开放由你单独决定。</p>
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
        此版本仅主研究项可关联使用。发布后才能被其他研究项引用，且发布后不可修改文件（要改请开新版本）。发布≠分享：发布只冻结并生成 DOI，可见范围默认保持私有，是否对外开放由你单独决定。
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
          placeholder="对方的用户名或邮箱"
          :disabled="isAddingMember"
        />
        <button class="btn btn--primary btn--sm" type="submit" :disabled="isAddingMember || !memberAddUserId">
          <span v-if="isAddingMember" class="spinner"></span>
          {{ isAddingMember ? '授权中...' : '授权' }}
        </button>
      </form>
      <div v-if="memberError" class="inline-error">{{ memberError }}</div>

      <EmptyState v-if="isLoadingMembers" description="正在读取授权用户…" compact />
      <EmptyState
        v-else-if="!datasetMembers.length"
        description="还没有授权任何用户。在上方输入对方的用户名或邮箱即可授权。"
        compact
      />
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
</template>

<script setup lang="ts">
// 数据集详情「发布与共享」tab：可见范围开放 + 版本发布/撤回/丢弃 + 授权成员 + 删除数据集。
// 由原「概览」tab 抽出权限/生命周期部分（概览已废弃；数据概要并入左栏卡片与「数据文件」，导入目标并入「上传」）。
// 状态经 datasetContext inject 取用，CSS 走全局（DatasetsPage.css）。
import { inject } from 'vue'
import { RouterLink } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { datasetVersionStateClass, datasetVersionStateLabel } from '@/api/datasetVersions'
import {
  formatDate,
  formatVersionLabel,
  getVisibilityClass,
  getVisibilityLabel,
  qaStatusLabel,
} from '@/composables/datasets/datasetsFormatters'
import { datasetContextKey } from '@/composables/datasets/datasetContext'

const ctx = inject(datasetContextKey)!
const { selectedDatasetAsset } = ctx.catalog
const {
  lifecycleMessage, currentVersion, sortedVersions,
  canCreateNewDraft, isCreatingDraft, createNewDraft, canCreateNewDraftBlockedReason,
  openPublishModal, openWithdrawModal, openEmergencyTakedownModal,
  openPublishModalForVersion, openWithdrawModalForVersion,
  canDiscardVersion, openDiscardVersionModal,
  showMemberPanel, datasetMembers, isLoadingMembers, loadSelectedAssetMembers,
  memberAddUserId, isAddingMember, submitAddMember, memberError, removingMemberId, revokeMember,
  visibilityHint, canOpenVisibility, openVisibilityModalFor,
  canDeleteAsset, openDeleteAssetModal,
} = ctx.lifecycle
const { isAdmin, copyDoi } = ctx
</script>
