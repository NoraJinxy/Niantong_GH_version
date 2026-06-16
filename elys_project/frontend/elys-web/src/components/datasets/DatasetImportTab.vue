<template>
  <section ref="uploadSectionRef" class="dataset-tab-panel" aria-label="导入数据">
    <div v-if="bootstrapError" class="inline-error">{{ bootstrapError }}</div>
    <div v-if="bootstrapSuccess" class="inline-success">{{ bootstrapSuccess }}</div>

    <BidsUploadPanel
      :study-id="uploadContext?.studyId || ''"
      :study-name="uploadContext?.studyName || undefined"
      :dataset-asset-id="uploadContext?.datasetAssetId || ''"
      :dataset-asset-name="uploadContext?.datasetAssetName || undefined"
      :mount-name="uploadContext?.mountName || ''"
      :upload-context="uploadContext || undefined"
      @uploaded="handleUploaded"
    />
  </section>
</template>

<script setup lang="ts">
// 数据集详情「导入」tab：进页时静默准备导入目标（自动建/复用研究项 + mount），再由 BidsUploadPanel
// 承载选数据 → 导入的主流程。状态经 datasetContext inject。
import { inject, onMounted } from 'vue'
import BidsUploadPanel from '@/components/BidsUploadPanel.vue'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
const ctx = inject(datasetContextKey)!
const {
  isTargetForSelectedAsset, canMountSelected, mountExistingDatasetAsset,
  bootstrapError, bootstrapSuccess, uploadContext, uploadSectionRef,
} = ctx.importTarget
const { handleUploaded } = ctx

onMounted(() => {
  // 进入上传页时，若尚未就绪且可自动准备，则后台静默准备导入目标，用户无需先点按钮。
  // ensureTargetStudy 优先复用 primary_study_id，不会误建研究项。
  if (!isTargetForSelectedAsset.value && canMountSelected.value) {
    void mountExistingDatasetAsset({ silent: true })
  }
})
</script>
