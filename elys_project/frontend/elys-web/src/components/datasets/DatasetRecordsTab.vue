<template>
          <section class="dataset-tab-panel" aria-label="采集记录">
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

</template>

<script setup lang="ts">
// 数据集详情「采集记录」tab。状态经 datasetContext inject。
import { inject } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import { formatDate, formatFileSize, getQaStatusClass, getQaStatusLabel, getFileShortPath, getFileRoleLabel } from '@/composables/datasets/datasetsFormatters'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
const ctx = inject(datasetContextKey)!
const {
  selectedAssetRecordings, isLoadingRecordings, recordingsError, recordingStats,
  loadSelectedAssetRecordings, isRecordingExpanded, toggleRecordingExpanded,
  recordingFilesById, recordingFilesLoading, recordingFilesError, loadRecordingFiles,
} = ctx.recordings
const { recordsStudyContext, recordsContextLabel } = ctx.importTarget
</script>
