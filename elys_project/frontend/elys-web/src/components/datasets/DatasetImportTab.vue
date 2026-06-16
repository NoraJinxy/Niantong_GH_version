<template>
          <section ref="uploadSectionRef" class="dataset-tab-panel" aria-label="导入数据">
            <div class="dataset-target-panel" :class="{ 'is-ready': isTargetForSelectedAsset }">
              <div>
                <span class="section-kicker">上传</span>
                <h3>{{ isTargetForSelectedAsset ? '可以上传了' : (isBootstrapping ? '正在准备…' : '准备上传位置') }}</h3>
                <p>
                  {{ isTargetForSelectedAsset
                    ? '选择或拖入 EEG 数据并提交，会保存到这个数据集。'
                    : (isBootstrapping
                      ? '系统正在自动准备，稍候即可上传。'
                      : '系统会自动准备；若没有自动开始，点右侧按钮即可。')
                  }}
                </p>
              </div>
              <button
                class="btn btn--primary"
                type="button"
                :disabled="(!canMountSelected && !isTargetForSelectedAsset) || isBootstrapping"
                @click="isTargetForSelectedAsset ? scrollToUploadPanel() : mountExistingDatasetAsset()"
              >
                <span v-if="isBootstrapping" class="spinner"></span>
                {{ isTargetForSelectedAsset ? '继续上传' : '准备上传位置' }}
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

</template>

<script setup lang="ts">
// 数据集详情「导入」tab：导入目标准备 + BidsUploadPanel。状态经 datasetContext inject。
import { inject, onMounted } from 'vue'
import BidsUploadPanel from '@/components/BidsUploadPanel.vue'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
const ctx = inject(datasetContextKey)!
const {
  isTargetForSelectedAsset, canMountSelected, mountExistingDatasetAsset, isBootstrapping,
  scrollToUploadPanel, mountName, clearBootstrapResult,
  bootstrapError, bootstrapSuccess, uploadContext, uploadSectionRef, uploadPanelRef,
} = ctx.importTarget
const { handleUploaded } = ctx

onMounted(() => {
  // 隐形化「准备导入目标」：进入上传页时，若尚未就绪且可自动准备，则后台静默准备，
  // 用户无需先点按钮。ensureTargetStudy 优先复用 primary_study_id，不会误建研究项。
  if (!isTargetForSelectedAsset.value && canMountSelected.value) {
    void mountExistingDatasetAsset({ silent: true })
  }
})
</script>
