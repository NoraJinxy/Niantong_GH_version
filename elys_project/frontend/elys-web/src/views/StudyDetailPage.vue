<template>
  <div class="study-data-tab">
    <div class="row gap-2 row--wrap mb-4">
      <button class="btn btn--sm" type="button" :disabled="loading" @click="loadStudy">
        <AppIcon name="clock" :size="16" />
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div v-if="error" class="alert alert--danger mb-4">
      <AppIcon name="admin" :size="18" />
      <div class="alert__body">{{ error }}</div>
    </div>

    <div v-if="warnings.length" class="alert alert--warning mb-4">
      <AppIcon name="clock" :size="18" />
      <div class="alert__body">{{ warnings.join('；') }}</div>
    </div>

    <div v-if="loading && !study" class="empty">
      <div class="empty__icon"><span class="spinner spinner--dark"></span></div>
      正在加载采集记录...
    </div>

    <template v-else>
      <section class="study-section mb-5">
        <div class="section-head">
          <div>
            <h2>数据</h2>
            <p>本研究项引用的数据集、采集记录与标准化 FIF 状态。</p>
          </div>
          <RouterLink class="btn btn--sm" :to="importTarget">导入数据集</RouterLink>
        </div>

        <div class="data-subsection">
          <div class="subsection-title">
            <h3>引用的数据集</h3>
            <span>{{ mounts.length ? `${mounts.length} 个` : mountStatusLabel }}</span>
          </div>
          <div v-if="mounts.length" class="mount-list">
            <article v-for="mount in mounts" :key="mount.id" class="mount-item">
              <div>
                <strong>{{ mount.mount_name }}</strong>
                <p>{{ mount.dataset_asset?.name || mount.dataset_asset_id }}</p>
              </div>
              <span class="status-pill" :class="mount.is_active ? 'status-pill--ok' : ''">
                {{ mount.is_active ? '启用中' : '未启用' }}
              </span>
            </article>
          </div>
          <div v-else class="empty compact-empty">
            <div class="empty__icon"><AppIcon name="database" :size="22" /></div>
            {{ mountStatusLabel }}
          </div>
        </div>

        <div class="data-subsection">
          <div class="subsection-title">
            <h3>采集记录</h3>
            <span>{{ recordings.length }} 条</span>
          </div>
          <div v-if="!recordings.length" class="empty compact-empty">
            <div class="empty__icon"><AppIcon name="file" :size="22" /></div>
            暂无采集记录。可以先导入数据集，或等待采集记录功能接入。
          </div>
          <div v-else class="table-wrap">
            <table class="table table--compact">
              <thead>
                <tr>
                  <th>被试</th>
                  <th>会话</th>
                  <th>任务</th>
                  <th>轮次</th>
                  <th>格式</th>
                  <th>标准化 FIF</th>
                  <th>通道 / 事件</th>
                  <th>质量状态</th>
                  <th>导入时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="recording in recordings" :key="recording.id">
                  <td><strong>{{ recording.subject }}</strong></td>
                  <td>{{ recording.session || '-' }}</td>
                  <td>{{ recording.task || '-' }}</td>
                  <td>{{ recording.run || '-' }}</td>
                  <td>{{ recording.sourceFormat || '-' }}</td>
                  <td>
                    <span class="status-pill" :class="recording.hasCanonicalFif ? 'status-pill--ok' : ''">
                      {{ recording.hasCanonicalFif ? '已生成' : '待生成' }}
                    </span>
                  </td>
                  <td>{{ recording.channelEventLabel }}</td>
                  <td>
                    <span class="status-pill" :class="qualityPillClass(recording.qaStatus)">
                      {{ qaStatusLabel(recording.qaStatus) }}
                    </span>
                  </td>
                  <td class="muted">{{ formatDate(recording.importedAt) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import { recordingApi, studyDatasetMountApi } from '@/api/datasetAssets'
import { studyApi } from '@/api/studies'
import type { Recording, Study, StudyDatasetMount } from '@/types'

interface RecordingRow {
  id: string
  subject: string
  session: string | null
  task: string
  run: string | null
  sourceFormat: string
  hasCanonicalFif: boolean
  channelEventLabel: string
  qaStatus: string | null
  importedAt: string | null
}

const route = useRoute()
const studyId = computed(() => String(route.params.studyId || ''))
const importTarget = computed(() => `/datasets?study_id=${encodeURIComponent(studyId.value)}`)

const study = ref<Study | null>(null)
const mounts = ref<StudyDatasetMount[]>([])
const recordings = ref<RecordingRow[]>([])
const loading = ref(false)
const error = ref('')
const warnings = ref<string[]>([])
const mountsLoaded = ref(false)

const mountStatusLabel = computed(() => {
  if (!mountsLoaded.value) return '数据集引用功能待接入'
  return '暂无引用的数据集'
})

onMounted(loadStudy)

watch(studyId, () => {
  void loadStudy()
})

async function loadStudy() {
  loading.value = true
  error.value = ''
  warnings.value = []
  mountsLoaded.value = false
  recordings.value = []

  try {
    const studyRes = await studyApi.get(studyId.value)
    study.value = studyRes.data
    await Promise.all([loadMounts(), loadRecordings()])
  } catch (err: any) {
    error.value = err.response?.data?.detail || '采集记录加载失败'
  } finally {
    loading.value = false
  }
}

async function loadMounts() {
  try {
    const res = await studyDatasetMountApi.list(studyId.value)
    mounts.value = res.data.mounts
    mountsLoaded.value = true
  } catch {
    mounts.value = []
    mountsLoaded.value = false
  }
}

async function loadRecordings() {
  try {
    const res = await recordingApi.list(studyId.value)
    recordings.value = res.data.recordings.map(normalizeRecording)
  } catch {
    recordings.value = []
    warnings.value.push('采集记录摘要暂不可用')
  }
}

function normalizeRecording(recording: Recording): RecordingRow {
  return {
    id: recording.id,
    subject: recording.bids_subject_id || recording.subject_id,
    session: recording.session || null,
    task: recording.task,
    run: recording.run || null,
    sourceFormat: recording.source_format,
    hasCanonicalFif: !!recording.fif_path,
    channelEventLabel: formatChannelEvent(recording.n_channels, recording.n_events),
    qaStatus: recording.qa_status || null,
    importedAt: recording.imported_at || null,
  }
}

function formatChannelEvent(channels?: number | null, events?: number | null) {
  const channelLabel = channels == null ? '-' : `${channels} ch`
  const eventLabel = events == null ? '-' : `${events} evt`
  return `${channelLabel} / ${eventLabel}`
}

function qaStatusLabel(status: string | null) {
  const labels: Record<string, string> = {
    checked: '已校验',
    converted: '已转换',
    pending: '待校验',
    failed: '校验失败',
    rejected: '已驳回',
  }
  return status ? labels[status] || status : '未校验'
}

function qualityPillClass(status: string | null) {
  if (status === 'checked') return 'status-pill--ok'
  if (status === 'failed' || status === 'rejected') return 'status-pill--danger'
  if (status === 'pending' || status === 'converted') return 'status-pill--warn'
  return 'status-pill--muted'
}

function formatDate(value: string | null | undefined) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.study-header {
  align-items: flex-start;
}

.study-section {
  min-width: 0;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: var(--s-5);
  box-shadow: var(--shadow-sm);
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: var(--s-4);
  align-items: flex-start;
  margin-bottom: var(--s-4);
}

.section-head h2,
.subsection-title h3 {
  margin: 0 0 4px;
  color: var(--c-text);
  font-size: 15px;
  font-weight: 700;
}

.section-head p,
.subsection-title span,
.mount-item p {
  margin: 0;
  color: var(--c-text-3);
  font-size: 12px;
  line-height: 1.6;
}

.data-subsection + .data-subsection {
  margin-top: var(--s-5);
}

.data-subsection,
.table-wrap {
  min-width: 0;
  max-width: 100%;
}

.table-wrap {
  overflow-x: auto;
}

.subsection-title {
  display: flex;
  justify-content: space-between;
  gap: var(--s-3);
  align-items: center;
  margin-bottom: var(--s-3);
}

.mount-list {
  display: grid;
  gap: var(--s-3);
}

.mount-item {
  display: flex;
  justify-content: space-between;
  gap: var(--s-3);
  align-items: center;
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.mount-item > div {
  min-width: 0;
}

.mount-item strong {
  display: block;
  overflow: hidden;
  color: var(--c-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-empty {
  min-height: 150px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 22px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--c-bg-tint);
  color: var(--c-text-3);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}

.status-pill--ok {
  background: var(--c-success-soft);
  color: var(--c-success);
}

.status-pill--warn {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}

.status-pill--danger {
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

.status-pill--muted {
  background: var(--c-bg-tint);
  color: var(--c-text-3);
}

@media (max-width: 720px) {
  .study-section {
    padding: var(--s-4);
  }

  .section-head,
  .subsection-title,
  .mount-item {
    align-items: stretch;
    flex-direction: column;
  }

  .table-wrap {
    width: 100%;
  }
}
</style>
