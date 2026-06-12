<template>
          <section ref="uploadSectionRef" class="dataset-tab-panel" aria-label="导入数据">
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

</template>

<script setup lang="ts">
// 数据集详情「导入」tab：导入目标准备 + BidsUploadPanel。状态经 datasetContext inject。
import { inject } from 'vue'
import BidsUploadPanel from '@/components/BidsUploadPanel.vue'
import { formatProcessingWorkspaceName } from '@/composables/datasets/datasetsFormatters'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
const ctx = inject(datasetContextKey)!
const {
  isTargetForSelectedAsset, canMountSelected, mountExistingDatasetAsset, isBootstrapping,
  scrollToUploadPanel, mountName, clearBootstrapResult, targetSummary,
  bootstrapError, bootstrapSuccess, uploadContext, uploadSectionRef, uploadPanelRef,
} = ctx.importTarget
const { handleUploaded } = ctx
</script>
