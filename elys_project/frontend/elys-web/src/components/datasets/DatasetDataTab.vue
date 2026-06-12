<template>
          <section class="dataset-tab-panel dataset-files" aria-label="数据文件">
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

</template>

<script setup lang="ts">
// 数据集详情「数据文件」tab：上传/FIF 两桶 + 按被试视图。状态经 datasetContext inject。
import { inject } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import { formatFileSize, getFileShortPath, getFileRoleLabel } from '@/composables/datasets/datasetsFormatters'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
const ctx = inject(datasetContextKey)!
const { assetBuckets, isLoadingAssetFiles } = ctx.files
const {
  selectedAssetRecordings, isLoadingRecordings, recordingsError, uploadFormatHint,
  recordingsBySubject, recordingBucketsById, recordingFilesById, recordingFilesLoading,
  recordingFilesError, loadRecordingFiles, loadSelectedAssetRecordings,
} = ctx.recordings
const { recordsStudyContext } = ctx.importTarget
const { dataView } = ctx
</script>
