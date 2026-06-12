<template>
          <section class="dataset-tab-panel" aria-label="技术信息">
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
</template>

<script setup lang="ts">
// 数据集详情「技术信息」tab。状态经 datasetContext inject。
import { inject } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
const ctx = inject(datasetContextKey)!
const { technicalInfoItems } = ctx.importTarget
const { copyStatus, copyTechnicalValue } = ctx
</script>
