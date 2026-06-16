// 数据集页 · 导入目标准备（bootstrap / mount + study 自动配对）
//
// 从 DatasetsPage.vue 抽出"把数据集准备成导入目标"的整块：新建数据集（bootstrap，连带
// 自动建研究项）或为已有数据集挂载（mount）一个研究项，产出 targetSummary /
// uploadContext（喂给 BidsUploadPanel）/ recordsStudyContext（喂给采集记录）/ technicalInfoItems。
// 含 study 自动配对的全部退避逻辑（code 冲突重试、复用既有 mount 等）。
//
// 依赖经 options 注入：selectedDatasetAsset / selectedDatasetAssetId（catalog）、
// loadDatasetAssets（建成后刷新列表）、loadSelectedAssetFiles（建成后刷新文件）、
// activePanel / activeTab（建成后切到导入视图，导航 ref 由页面持有）。route 内部自取。
//
// 工程债评审（日志/6_工程债评审260612「工程债评审与重构路线」§2.2 前端上帝组件）：
// DatasetsPage.vue 拆分批 6（末批）。

import { computed, nextTick, ref, type ComputedRef, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { studyApi } from '@/api/studies'
import { datasetAssetApi, studyDatasetMountApi } from '@/api/datasetAssets'
import type {
  DatasetAsset,
  DatasetBootstrapResponse,
  DatasetUploadContext,
  Study,
  StudyDatasetMount,
} from '@/types'
import {
  formatDate,
  formatStudyName,
  getErrorMessage,
  queryString,
  sanitizeCode,
} from './datasetsFormatters'
import type { RecordsStudyContext } from './useDatasetRecordings'

const STUDY_CODE_MAX_LENGTH = 64

export interface TechnicalInfoItem {
  key: string
  label: string
  value: string
}

type DatasetWorkbenchTab = 'data' | 'import' | 'share'

interface DatasetImportTargetOptions {
  selectedDatasetAsset: ComputedRef<DatasetAsset | null>
  selectedDatasetAssetId: Ref<string>
  activePanel: Ref<'catalog' | 'create'>
  activeTab: Ref<DatasetWorkbenchTab>
  loadDatasetAssets: () => Promise<void>
  loadSelectedAssetFiles: () => Promise<void>
}

export function useDatasetImportTarget(options: DatasetImportTargetOptions) {
  const { selectedDatasetAsset, selectedDatasetAssetId, activePanel, activeTab, loadDatasetAssets, loadSelectedAssetFiles } = options
  const route = useRoute()

  const studies = ref<Study[]>([])
  const datasetName = ref('')
  const datasetCode = ref('')
  const datasetDescription = ref('')
  const selectedStudyId = ref('')
  const mountName = ref('primary')
  const uploadSectionRef = ref<HTMLElement | null>(null)
  const bootstrapResponse = ref<DatasetBootstrapResponse | null>(null)
  const mountedTarget = ref<{
    asset: DatasetAsset
    study: Study
    mount: StudyDatasetMount
  } | null>(null)
  const isBootstrapping = ref(false)
  const bootstrapError = ref('')
  const bootstrapSuccess = ref('')

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

    // 优先用资产自带的 primary_study_id 配对（脚本 / 页面建集时都会写这个真实指针）；
    // 找不到再退回「数据集 code + -study」的猜测 —— 后者只对页面新建的数据集成立，
    // 脚本（setup.py）起的研究项 code 可能不带 -study 后缀，曾导致记录列不出来。
    const pairedStudy =
      (asset.primary_study_id
        ? studies.value.find((study) => study.id === asset.primary_study_id)
        : undefined)
      || studies.value.find((study) => study.code === trimStudyCode(resolvedPairedStudyCode(asset)))
    if (!pairedStudy) return null
    return {
      studyId: pairedStudy.id,
      studyName: pairedStudy.name,
      // 这条路拿不到具体 mount；按 dataset_asset_id 在该研究项下列全部记录，不猜 mount_name（避免误过滤）。
    }
  })
  const recordsContextLabel = computed(() => {
    const context = recordsStudyContext.value
    if (!context) return '未准备'
    return context.mountName
      ? `${formatStudyName(context.studyName)} / ${context.mountName}`
      : formatStudyName(context.studyName)
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

  async function loadStudies() {
    try {
      const res = await studyApi.list()
      studies.value = res.data.studies
    } catch {
      studies.value = []
    }
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

  // silent=true 用于「隐形化准备」：进入上传页时后台静默准备导入目标，不弹成功提示、不滚动、
  // 失败也不报红（回退到手动按钮）。手动点击仍走非静默路径，给明确反馈。
  async function mountExistingDatasetAsset(options?: { silent?: boolean }) {
    const asset = selectedDatasetAsset.value
    if (!asset || isBootstrapping.value) return
    const silent = options?.silent === true
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
      if (!silent) {
        bootstrapSuccess.value = '已准备好，可以上传了。'
        await loadStudies()
        await scrollToUploadSection()
      } else {
        await loadStudies()
      }
    } catch (err: any) {
      mountedTarget.value = null
      if (!silent) bootstrapError.value = getErrorMessage(err)
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
    // 优先用资产自带 primary_study_id（与 recordsStudyContext 一致）：脚本建的研究项 code
    // 未必符合「{code}-study」约定，仅按 code 找会落空而误建重复研究项。自动准备导入目标
    // 依赖这条保证——找到既有主研究项就复用，绝不新建。
    if (asset.primary_study_id) {
      const primary = studies.value.find((study) => study.id === asset.primary_study_id)
      if (primary) return primary
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
    return baseName ? `${baseName} 研究项` : '数据集研究项'
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

  function clearBootstrapResult() {
    bootstrapResponse.value = null
    mountedTarget.value = null
    bootstrapSuccess.value = ''
    bootstrapError.value = ''
  }

  async function scrollToUploadSection() {
    await nextTick()
    uploadSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return {
    studies,
    datasetName,
    datasetCode,
    datasetDescription,
    selectedStudyId,
    mountName,
    uploadSectionRef,
    isBootstrapping,
    bootstrapError,
    bootstrapSuccess,
    queryStudyId,
    selectedStudy,
    usesShortcutStudy,
    shortcutStudyLabel,
    canCreateDataset,
    canMountSelected,
    targetSummary,
    isTargetForSelectedAsset,
    recordsStudyContext,
    recordsContextLabel,
    uploadContext,
    technicalInfoItems,
    loadStudies,
    resetDatasetCreateForm,
    clearBootstrapResult,
    bootstrapDataset,
    mountExistingDatasetAsset,
  }
}
