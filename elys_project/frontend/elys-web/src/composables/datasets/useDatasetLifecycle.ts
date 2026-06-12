// 数据集页 · 生命周期（版本 + 授权用户 + 开放/转公开 + 删除）
//
// 从 DatasetsPage.vue 抽出数据集生命周期 v2（docs_v2/3-25）的整块状态与动作：
//   · 版本：加载 / 发布 / 撤回 / 紧急下架 / 新建未发布 / 丢弃未发布；
//   · 授权用户（dataset_members）：共享态邀请制授权 / 取消授权；
//   · 可见范围「开放」（只升不降）与「转公开」先审后开；
//   · 整个数据集删除（仅纯未发布资产）。
// 这些动作互相耦合（版本载入后拉授权、开放为共享后拉授权、共用 isAssetOwner 与
// lifecycleMessage），故合成一个 composable。依赖经 options 注入：selectedDatasetAsset /
// selectedDatasetAssetId（catalog）、loadDatasetAssets（提交后刷新列表）、showPageNotice
// （删除成功后详情面板卸载，提示走页面级）。owner 判定内部自取 auth store。
//
// 工程债评审（日志/6_工程债评审260612「工程债评审与重构路线」§2.2 前端上帝组件）：
// DatasetsPage.vue 拆分批 5。

import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { datasetAssetApi, datasetMemberApi } from '@/api/datasetAssets'
import { datasetVersionApi } from '@/api/datasetVersions'
import type { DatasetAsset, DatasetAssetVisibility, DatasetMember, DatasetVersion } from '@/types'
import { getVisibilityLabel, lifecycleErrorMessage } from './datasetsFormatters'

interface DatasetLifecycleOptions {
  selectedDatasetAsset: ComputedRef<DatasetAsset | null>
  selectedDatasetAssetId: Ref<string>
  loadDatasetAssets: () => Promise<void>
  showPageNotice: (message: string) => void
}

export function useDatasetLifecycle(options: DatasetLifecycleOptions) {
  const { selectedDatasetAsset, selectedDatasetAssetId, loadDatasetAssets, showPageNotice } = options
  const auth = useAuthStore()

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

  // 规则 4：丢弃已发布资产上的 v+1 未发布版本
  const discardVersionModal = ref<{
    open: boolean
    versionId: string | null
    versionLabel: string
    submitting: boolean
    error: string
  }>({ open: false, versionId: null, versionLabel: '', submitting: false, error: '' })

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

  return {
    datasetVersions,
    isLoadingVersions,
    isCreatingDraft,
    lifecycleMessage,
    publishModal,
    withdrawModal,
    emergencyModal,
    visibilityModal,
    discardVersionModal,
    datasetMembers,
    isLoadingMembers,
    isAddingMember,
    memberAddUserId,
    memberError,
    removingMemberId,
    deleteAssetModal,
    currentVersion,
    sortedVersions,
    hasOpenDraft,
    hasAnyPublished,
    hasPublishedHistory,
    hasCurrentlyPublished,
    canCreateNewDraft,
    canCreateNewDraftBlockedReason,
    isAssetOwner,
    showMemberPanel,
    canDeleteAsset,
    canSubmitPublish,
    publishTargetLabel,
    visibilityHint,
    canOpenVisibility,
    canDiscardVersion,
    loadSelectedAssetVersions,
    loadSelectedAssetMembers,
    openPublishModal,
    openPublishModalForVersion,
    closePublishModal,
    submitPublish,
    openWithdrawModal,
    openWithdrawModalForVersion,
    closeWithdrawModal,
    submitWithdraw,
    openEmergencyTakedownModal,
    closeEmergencyModal,
    submitEmergencyTakedown,
    createNewDraft,
    openVisibilityModalFor,
    closeVisibilityModal,
    submitOpenVisibility,
    submitAddMember,
    revokeMember,
    openDeleteAssetModal,
    closeDeleteAssetModal,
    submitDeleteAsset,
    openDiscardVersionModal,
    closeDiscardVersionModal,
    submitDiscardVersion,
  }
}
