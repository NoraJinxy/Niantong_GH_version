<template>
  <WorkbenchShell active-key="admin" active-top-key="dashboard">
    <div class="page__header ops-header">
      <div class="ops-header__heading">
        <h1 class="page__title">平台运维面板</h1>
        <p class="page__subtitle">面向管理员的平台全量视角：系统在做什么、负荷如何、有什么问题。第一期为只读监测。</p>
      </div>
      <div class="ops-header__actions">
        <span class="ops-refresh-hint" :class="{ 'is-on': autoRefresh }">
          <span class="ops-refresh-hint__dot"></span>
          {{ autoRefresh ? '自动刷新 6s' : '自动刷新已停' }}
        </span>
        <button class="btn btn--sm" type="button" @click="autoRefresh = !autoRefresh">
          {{ autoRefresh ? '暂停' : '恢复' }}
        </button>
        <button class="btn btn--icon" type="button" :disabled="anyLoading" title="刷新" aria-label="刷新" @click="refreshActive()">
          <span v-if="anyLoading" class="spinner spinner--dark"></span>
          <AppIcon v-else name="refresh" :size="16" />
        </button>
      </div>
    </div>

    <div v-if="!isAdmin" class="ops-guard">
      <EmptyState icon="admin" title="需要管理员权限" description="本页面仅平台管理员可见。" />
    </div>

    <template v-else>
      <nav class="ops-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="ops-tab"
          :class="{ 'is-active': activeTab === tab.key }"
          type="button"
          @click="activeTab = tab.key"
        >
          <AppIcon :name="tab.icon" :size="15" />
          <span>{{ tab.label }}</span>
        </button>
      </nav>

      <div v-if="errorMessage" class="alert alert--danger mb-4">
        <AppIcon name="warning" :size="18" />
        <div class="alert__body">{{ errorMessage }}</div>
        <button class="btn btn--sm" type="button" @click="refreshActive()">重试</button>
      </div>

      <!-- ================= 总览 ================= -->
      <!-- 骨架优先：无数据时各区即时显示占位（检测中 / —），不空等整屏 spinner -->
      <section v-show="activeTab === 'overview'" class="ops-section">
        <div class="ops-health">
          <div
            v-for="item in healthItems"
            :key="item.key"
            class="ops-health__light"
            :class="[`is-${healthTone(item.status)}`, { 'is-loading': item.loading }]"
          >
            <span class="ops-health__icon"><AppIcon :name="item.icon" :size="16" /></span>
            <div class="ops-health__text">
              <strong>{{ item.label }}</strong>
              <span>{{ item.detail }}</span>
            </div>
            <span class="ops-health__dot"></span>
          </div>
        </div>

        <div v-if="overview && overview.attention.length" class="ops-attention">
          <div
            v-for="(item, idx) in overview.attention"
            :key="idx"
            class="ops-attention__row"
            :class="`is-${item.severity}`"
          >
            <AppIcon name="warning" :size="16" />
            <span>{{ item.label }}</span>
          </div>
        </div>

        <div class="ops-card">
          <div class="ops-card__head"><h2>平台概览</h2><span>全平台计数</span></div>
          <div class="ops-metrics">
            <div
              v-for="metric in metricCards"
              :key="metric.key"
              class="ops-metric"
              :class="{ 'is-loading': metric.loading }"
            >
              <span class="ops-metric__chip" :class="`is-${metric.tone}`"><AppIcon :name="metric.icon" :size="18" /></span>
              <div class="ops-metric__body">
                <div class="ops-metric__label">{{ metric.label }}</div>
                <div class="ops-metric__value">{{ metric.value }}</div>
                <div class="ops-metric__hint">{{ metric.hint }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="ops-card">
          <div class="ops-card__head"><h2>执行状态分布</h2><span>全平台 · 所有研究项</span></div>
          <template v-if="execTotal > 0">
            <div class="ops-distbar">
              <span
                v-for="s in execSegments"
                :key="s.key"
                class="ops-distbar__seg"
                :class="`is-${s.tone}`"
                :style="{ width: s.pct + '%' }"
                :title="`${s.label} ${s.value}`"
              ></span>
            </div>
            <div class="ops-distlegend">
              <span v-for="s in executionStateCards" :key="s.key" class="ops-distlegend__item">
                <span class="ops-distlegend__dot" :class="`is-${s.tone}`"></span>
                {{ s.label }} <strong>{{ s.value }}</strong>
              </span>
            </div>
          </template>
          <EmptyState v-else icon="pulse" title="暂无执行记录" description="平台还没有任何分析运行。" compact quiet />
        </div>
      </section>

      <!-- ================= 运行与负荷 ================= -->
      <section v-show="activeTab === 'runtime'" class="ops-section">
        <div v-if="loadingRuntime && !runtime" class="ops-loading">
          <span class="spinner spinner--dark"></span> 正在读取运行状态…
        </div>

        <template v-else-if="runtime">
          <div class="ops-grid-2">
            <div class="ops-card">
              <div class="ops-card__head"><h2>执行队列 · 实时</h2><span>全平台</span></div>
              <div class="ops-queue">
                <div class="ops-queue__stat is-info"><strong>{{ runtime.queue.running }}</strong><span>运行中</span></div>
                <div class="ops-queue__stat is-warn"><strong>{{ runtime.queue.queued }}</strong><span>排队</span></div>
                <div class="ops-queue__stat"><strong>{{ runtime.queue.waiting_user_input }}</strong><span>等确认</span></div>
                <div class="ops-queue__stat is-danger"><strong>{{ runtime.queue.failed_recent }}</strong><span>失败(24h)</span></div>
              </div>
              <div class="ops-subtle">
                上传/导入异步任务：{{ runtime.queue.async_running }} 运行 · {{ runtime.queue.async_queued }} 排队
              </div>
            </div>

            <div class="ops-card">
              <div class="ops-card__head">
                <h2>计算 worker</h2>
                <span :class="runtime.workers.online ? 'ops-ok' : 'ops-bad'">
                  {{ runtime.workers.online ? `${runtime.workers.worker_count} 个在线` : '离线 · inline 降级' }}
                </span>
              </div>
              <div class="ops-queue">
                <div class="ops-queue__stat is-info"><strong>{{ runtime.workers.active }}</strong><span>active</span></div>
                <div class="ops-queue__stat is-warn"><strong>{{ runtime.workers.reserved }}</strong><span>reserved</span></div>
              </div>
              <div v-if="runtime.workers.workers.length" class="ops-worker-list">
                <div v-for="w in runtime.workers.workers" :key="w.name" class="ops-worker-row">
                  <code>{{ w.name }}</code>
                  <span>active {{ w.active }} · reserved {{ w.reserved }}</span>
                </div>
              </div>
              <div v-else-if="!runtime.workers.online" class="ops-subtle ops-bad">
                worker 不在线，pipeline 正在 web 请求线程同步执行（共享队列瓶颈）。
              </div>
            </div>
          </div>

          <div class="ops-card">
            <div class="ops-card__head"><h2>计算服负荷</h2><span>{{ resourceHostLabel }}</span></div>
            <div v-if="!runtime.resources.psutil_available" class="ops-subtle">
              psutil 未安装（待云端部署 pip install），仅磁盘可读。
            </div>
            <div class="ops-bars">
              <div class="ops-bar">
                <div class="ops-bar__head"><span>CPU</span><span>{{ pct(runtime.resources.cpu_percent) }}</span></div>
                <div class="ops-bar__track"><div class="ops-bar__fill is-info" :style="{ width: barWidth(runtime.resources.cpu_percent) }"></div></div>
              </div>
              <div class="ops-bar">
                <div class="ops-bar__head"><span>内存</span><span>{{ memLabel }}</span></div>
                <div class="ops-bar__track"><div class="ops-bar__fill is-warn" :style="{ width: barWidth(runtime.resources.mem?.percent) }"></div></div>
              </div>
              <div class="ops-bar">
                <div class="ops-bar__head"><span>磁盘 · 存储盘</span><span>{{ diskLabel }}</span></div>
                <div class="ops-bar__track"><div class="ops-bar__fill" :class="diskFillTone" :style="{ width: barWidth(runtime.resources.disk?.percent) }"></div></div>
              </div>
            </div>
            <div v-if="runtime.resources.load_avg" class="ops-subtle">
              负载均值 (1/5/15min)：{{ runtime.resources.load_avg.join(' · ') }} · {{ runtime.resources.cpu_count }} 核
            </div>
          </div>

          <div class="ops-card" :class="{ 'ops-card--alert': stuckOrLocks.length }">
            <div class="ops-card__head">
              <h2>卡死执行与锁</h2>
              <span>running 超 10 分钟 / 未释放的执行锁</span>
            </div>
            <EmptyState v-if="!stuckOrLocks.length" icon="check" title="没有卡死或泄漏的锁" description="所有执行锁都在正常生命周期内。" compact quiet />
            <div v-else class="ops-list">
              <div v-for="row in stuckOrLocks" :key="row.key" class="ops-list__row is-alert">
                <span class="ops-list__dot is-danger"></span>
                <div class="ops-list__body">
                  <div class="ops-list__title">
                    <strong>{{ row.title }}</strong>
                    <span class="ops-tag is-danger">{{ row.tag }}</span>
                  </div>
                  <p>{{ row.detail }}</p>
                </div>
                <span class="ops-list__meta">{{ formatDuration(row.age) }}</span>
              </div>
            </div>
          </div>

          <div class="ops-card">
            <div class="ops-card__head"><h2>运行中执行</h2><span>{{ runtime.executions.length }} 条</span></div>
            <EmptyState v-if="!runtime.executions.length" icon="clock" title="当前没有运行中的执行" description="没有 running / 排队 / 等确认的执行。" compact quiet />
            <div v-else class="ops-list">
              <RouterLink
                v-for="ex in runtime.executions"
                :key="ex.id"
                class="ops-list__row"
                :to="executionRoute(ex)"
                target="_blank"
                rel="opener"
              >
                <span class="ops-list__dot" :class="`is-${statusTone(ex.status)}`"></span>
                <div class="ops-list__body">
                  <div class="ops-list__title">
                    <strong>{{ ex.pipeline_name || ('Pipeline #' + ex.pipeline_id) }}</strong>
                    <span class="ops-muted">运行 #{{ ex.execution_seq }}</span>
                    <span class="ops-tag">{{ statusLabel(ex.status) }}</span>
                  </div>
                  <p>{{ ex.study_name || ex.study_id }} · {{ ex.node_count }} 节点 · 触发 {{ ex.trigger }}</p>
                </div>
                <span class="ops-list__meta">{{ formatDuration(ex.age_seconds) }}</span>
              </RouterLink>
            </div>
          </div>

          <div class="ops-card">
            <div class="ops-card__head"><h2>最近失败</h2><span>近 24 小时 · 跨研究项</span></div>
            <EmptyState v-if="!runtime.recent_failures.length" icon="check" title="近 24 小时无失败执行" description="平台运行平稳。" compact quiet />
            <div v-else class="ops-list">
              <RouterLink
                v-for="fail in runtime.recent_failures"
                :key="fail.id"
                class="ops-list__row"
                :to="failureRoute(fail)"
                target="_blank"
                rel="opener"
              >
                <span class="ops-list__dot is-danger"></span>
                <div class="ops-list__body">
                  <div class="ops-list__title">
                    <strong>{{ fail.pipeline_name || ('Pipeline #' + fail.pipeline_id) }}</strong>
                    <span class="ops-muted">运行 #{{ fail.execution_seq }}</span>
                  </div>
                  <p>{{ fail.study_name || fail.study_id }} · {{ fail.error_message || '未记录错误摘要' }}</p>
                </div>
                <span class="ops-list__meta">{{ formatRelativeTime(fail.finished_at) }}</span>
              </RouterLink>
            </div>
          </div>
        </template>
      </section>

      <!-- ================= 审计与安全 ================= -->
      <section v-show="activeTab === 'audit'" class="ops-section">
        <div class="ops-card">
          <div class="ops-filters">
            <select v-model="auditFilters.action" class="ops-input" @change="applyAuditFilters()">
              <option value="">全部动作</option>
              <option v-for="a in auditFacetsData?.actions || []" :key="a" :value="a">{{ a }}</option>
            </select>
            <select v-model="auditFilters.resource_kind" class="ops-input" @change="applyAuditFilters()">
              <option value="">全部资源类型</option>
              <option v-for="k in auditFacetsData?.resource_kinds || []" :key="k" :value="k">{{ k }}</option>
            </select>
            <input v-model.trim="auditFilters.study_id" class="ops-input" placeholder="研究项 ID（可选）" @keyup.enter="applyAuditFilters()" />
            <button class="btn btn--sm" type="button" @click="applyAuditFilters()">查询</button>
            <button class="btn btn--sm" type="button" @click="resetAuditFilters()">清空</button>
          </div>

          <div v-if="auditLoading && !auditData" class="ops-loading"><span class="spinner spinner--dark"></span> 正在查询审计日志…</div>

          <template v-else-if="auditData">
            <EmptyState v-if="!auditData.events.length" icon="file" title="没有匹配的审计事件" description="调整筛选条件后重试。" compact quiet />
            <div v-else class="ops-table-wrap">
              <table class="ops-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>操作者</th>
                    <th>动作</th>
                    <th>资源</th>
                    <th>研究项</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="ev in auditData.events" :key="ev.id">
                    <td :title="formatAbsoluteTime(ev.occurred_at)">{{ formatRelativeTime(ev.occurred_at) }}</td>
                    <td>{{ ev.actor_name || '系统' }}</td>
                    <td><code class="ops-action">{{ ev.action }}</code></td>
                    <td>
                      <span v-if="ev.resource_kind" class="ops-muted">{{ ev.resource_kind }}</span>
                      <span v-if="ev.resource_label"> · {{ ev.resource_label }}</span>
                      <span v-if="ev.has_snapshot" class="ops-tag" title="含硬删除快照">快照</span>
                    </td>
                    <td><span class="ops-muted">{{ ev.study_id || '—' }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="ops-pager">
              <span>共 {{ auditData.total }} 条 · 第 {{ auditPage }} / {{ auditPageCount }} 页</span>
              <div class="ops-pager__btns">
                <button class="btn btn--sm" type="button" :disabled="auditOffset <= 0 || auditLoading" @click="auditPrev()">上一页</button>
                <button class="btn btn--sm" type="button" :disabled="auditOffset + auditLimit >= auditData.total || auditLoading" @click="auditNext()">下一页</button>
              </div>
            </div>
          </template>
        </div>
      </section>
    </template>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import { adminApi } from '@/api/admin'
import AppIcon from '@/components/AppIcon.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { formatAbsoluteTime, formatFileSize, formatRelativeTime } from '@/composables/common/formatters'
import { formatPipelineExecutionStatus } from '@/composables/pipeline/pipelineFormatters'
import { useAuthStore } from '@/stores/auth'
import type {
  AdminAuditEventsResponse,
  AdminAuditFacets,
  AdminExecutionItem,
  AdminFailureItem,
  AdminHealthStatus,
  AdminOverviewResponse,
  AdminRuntimeResponse,
} from '@/types'

type TabKey = 'overview' | 'runtime' | 'audit'

const auth = useAuthStore()
const isAdmin = computed(() => !!auth.user?.roles?.includes('admin'))

const tabs: Array<{ key: TabKey; label: string; icon: string }> = [
  { key: 'overview', label: '总览', icon: 'dashboard' },
  { key: 'runtime', label: '运行与负荷', icon: 'pulse' },
  { key: 'audit', label: '审计与安全', icon: 'file' },
]
const activeTab = ref<TabKey>('overview')

const overview = ref<AdminOverviewResponse | null>(null)
const runtime = ref<AdminRuntimeResponse | null>(null)
const loadingOverview = ref(false)
const loadingRuntime = ref(false)
const errorMessage = ref('')
const autoRefresh = ref(true)

const anyLoading = computed(() => loadingOverview.value || loadingRuntime.value || auditLoading.value)

// ---- 总览 ----
async function loadOverview(silent = false) {
  if (!silent) loadingOverview.value = true
  try {
    const res = await adminApi.overview()
    overview.value = res.data
    errorMessage.value = ''
  } catch (err: any) {
    if (!silent) errorMessage.value = err?.response?.data?.detail || '读取平台总览失败'
  } finally {
    loadingOverview.value = false
  }
}

const HEALTH_DEFS = [
  { key: 'api', label: 'API', icon: 'pulse' },
  { key: 'db', label: '数据库', icon: 'database' },
  { key: 'redis', label: 'Redis', icon: 'layers' },
  { key: 'worker', label: '计算 worker', icon: 'cpu' },
  { key: 'disk', label: '磁盘', icon: 'server' },
] as const

const healthItems = computed(() => {
  const h = overview.value?.health
  return HEALTH_DEFS.map((def) => {
    if (!h) {
      return { ...def, status: 'unknown' as AdminHealthStatus, detail: '检测中…', loading: true }
    }
    const node = h[def.key] as { status: AdminHealthStatus; [k: string]: unknown }
    let detail = ''
    if (def.key === 'api') detail = '服务在线'
    else if (def.key === 'db' || def.key === 'redis') detail = node.status === 'healthy' ? '连接正常' : '连接异常'
    else if (def.key === 'worker') detail = h.worker.online ? `${h.worker.worker_count} 个在线` : (h.worker.note || '离线')
    else if (def.key === 'disk') detail = h.disk.percent != null ? `${h.disk.percent}% 已用` : '未知'
    return { ...def, status: node.status, detail, loading: false }
  })
})

function healthTone(status: AdminHealthStatus): string {
  if (status === 'healthy') return 'ok'
  if (status === 'degraded' || status === 'warning') return 'warn'
  if (status === 'down' || status === 'critical') return 'bad'
  return 'muted'
}

const METRIC_DEFS = [
  { key: 'users', label: '活跃用户', icon: 'users', tone: 'info' },
  { key: 'studies', label: '研究项', icon: 'studies', tone: 'accent' },
  { key: 'datasets', label: '数据集', icon: 'database', tone: 'info' },
  { key: 'recordings', label: '采集记录', icon: 'wave', tone: 'ok' },
  { key: 'outputs', label: '产物', icon: 'layers', tone: 'accent' },
  { key: 'pipelines', label: '分析流程', icon: 'pipeline', tone: 'info' },
  { key: 'reviews', label: '待审核', icon: 'check', tone: 'warn' },
  { key: 'tasks', label: '异步任务', icon: 'activity', tone: 'info' },
] as const

const metricCards = computed(() => {
  const c = overview.value?.counts
  return METRIC_DEFS.map((def) => {
    if (!c) return { ...def, value: '—' as string | number, hint: '读取中', loading: true }
    let value = 0
    let hint = ''
    switch (def.key) {
      case 'users': value = c.users.active; hint = `共 ${c.users.total} · ${c.users.admins} 管理员`; break
      case 'studies': value = c.studies.total; hint = `${c.studies.active} 活跃 · ${c.studies.archived} 归档`; break
      case 'datasets': value = c.datasets.total; hint = `${c.dataset_versions.published} 个已发布版本`; break
      case 'recordings': value = c.recordings; hint = `${c.subjects} 名被试`; break
      case 'outputs': value = c.study_outputs.total; hint = `${c.study_outputs.kept} 个保留`; break
      case 'pipelines': value = c.pipelines; hint = `${c.executions.total} 次运行`; break
      case 'reviews': value = c.pending_reviews.withdrawals + c.pending_reviews.publicizations; hint = `撤回 ${c.pending_reviews.withdrawals} · 转公开 ${c.pending_reviews.publicizations}`; break
      case 'tasks': value = c.async_tasks.running + c.async_tasks.queued; hint = `${c.async_tasks.running} 运行 · ${c.async_tasks.queued} 排队`; break
    }
    return { ...def, value: value as string | number, hint, loading: false }
  })
})

const executionStateCards = computed(() => {
  const s = overview.value?.execution_states
  if (!s) return []
  return [
    { key: 'running', label: '运行中', value: s.running || 0, tone: 'info' },
    { key: 'queued', label: '排队', value: (s.queued || 0) + (s.pending || 0), tone: 'warn' },
    { key: 'waiting', label: '等确认', value: s.waiting_user_input || 0, tone: 'warn' },
    { key: 'failed', label: '失败', value: s.failed || 0, tone: 'danger' },
    { key: 'completed', label: '完成', value: s.completed || 0, tone: 'ok' },
    { key: 'canceled', label: '已取消', value: s.canceled || 0, tone: 'muted' },
  ]
})

const execTotal = computed(() => executionStateCards.value.reduce((sum, s) => sum + s.value, 0))
const execSegments = computed(() => {
  const total = execTotal.value
  if (!total) return [] as Array<{ key: string; label: string; value: number; tone: string; pct: number }>
  return executionStateCards.value
    .filter((s) => s.value > 0)
    .map((s) => ({ ...s, pct: Math.round((s.value / total) * 1000) / 10 }))
})

// ---- 运行与负荷 ----
async function loadRuntime(silent = false) {
  if (!silent) loadingRuntime.value = true
  try {
    const res = await adminApi.runtime()
    runtime.value = res.data
    errorMessage.value = ''
  } catch (err: any) {
    if (!silent) errorMessage.value = err?.response?.data?.detail || '读取运行状态失败'
  } finally {
    loadingRuntime.value = false
  }
}

const stuckOrLocks = computed(() => {
  if (!runtime.value) return [] as Array<{ key: string; title: string; tag: string; detail: string; age: number | null }>
  const rows: Array<{ key: string; title: string; tag: string; detail: string; age: number | null }> = []
  for (const ex of runtime.value.stuck_executions) {
    rows.push({
      key: `ex-${ex.id}`,
      title: `${ex.pipeline_name || 'Pipeline #' + ex.pipeline_id} · 运行 #${ex.execution_seq}`,
      tag: '执行卡死',
      detail: `${ex.study_name || ex.study_id} · running 已超 10 分钟阈值`,
      age: ex.age_seconds,
    })
  }
  for (const lock of runtime.value.locks) {
    if (!lock.expired) continue
    rows.push({
      key: `lock-${lock.id}`,
      title: `锁 ${lock.id.slice(0, 8)} · pipeline ${lock.resource_id}`,
      tag: '锁已过期未释放',
      detail: `${lock.study_name || lock.study_id || '未知研究项'} · TTL 已过，待下次运行或人工释放`,
      age: lock.age_seconds,
    })
  }
  return rows
})

const resourceHostLabel = computed(() => {
  const r = runtime.value?.resources
  if (!r) return ''
  if (r.cpu_count) return `${r.cpu_count} 核`
  return ''
})
const memLabel = computed(() => {
  const m = runtime.value?.resources.mem
  if (!m) return '—'
  return `${formatFileSize(m.used)} / ${formatFileSize(m.total)} · ${m.percent}%`
})
const diskLabel = computed(() => {
  const d = runtime.value?.resources.disk
  if (!d) return '—'
  return `${formatFileSize(d.used)} / ${formatFileSize(d.total)} · ${d.percent ?? '?'}%`
})
const diskFillTone = computed(() => {
  const p = runtime.value?.resources.disk?.percent
  if (p == null) return 'is-ok'
  if (p >= 92) return 'is-danger'
  if (p >= 80) return 'is-warn'
  return 'is-ok'
})

// ---- 审计 ----
const auditData = ref<AdminAuditEventsResponse | null>(null)
const auditFacetsData = ref<AdminAuditFacets | null>(null)
const auditLoading = ref(false)
const auditFilters = reactive({ action: '', resource_kind: '', study_id: '' })
const auditLimit = ref(50)
const auditOffset = ref(0)
let auditLoaded = false

const auditPage = computed(() => Math.floor(auditOffset.value / auditLimit.value) + 1)
const auditPageCount = computed(() => Math.max(1, Math.ceil((auditData.value?.total || 0) / auditLimit.value)))

async function loadAuditFacets() {
  try {
    const res = await adminApi.auditFacets()
    auditFacetsData.value = res.data
  } catch {
    auditFacetsData.value = { actions: [], resource_kinds: [] }
  }
}

async function loadAudit() {
  auditLoading.value = true
  try {
    const res = await adminApi.auditEvents({
      action: auditFilters.action || undefined,
      resource_kind: auditFilters.resource_kind || undefined,
      study_id: auditFilters.study_id || undefined,
      limit: auditLimit.value,
      offset: auditOffset.value,
    })
    auditData.value = res.data
    errorMessage.value = ''
  } catch (err: any) {
    errorMessage.value = err?.response?.data?.detail || '查询审计日志失败'
  } finally {
    auditLoading.value = false
  }
}

function applyAuditFilters() {
  auditOffset.value = 0
  void loadAudit()
}
function resetAuditFilters() {
  auditFilters.action = ''
  auditFilters.resource_kind = ''
  auditFilters.study_id = ''
  auditOffset.value = 0
  void loadAudit()
}
function auditPrev() {
  auditOffset.value = Math.max(0, auditOffset.value - auditLimit.value)
  void loadAudit()
}
function auditNext() {
  auditOffset.value = auditOffset.value + auditLimit.value
  void loadAudit()
}

// ---- 共用 ----
function refreshActive() {
  if (activeTab.value === 'overview') void loadOverview()
  else if (activeTab.value === 'runtime') void loadRuntime()
  else void loadAudit()
}

function statusTone(status: string): string {
  if (status === 'running') return 'info'
  if (status === 'queued' || status === 'pending') return 'warn'
  if (status === 'waiting_user_input') return 'warn'
  if (status === 'failed') return 'danger'
  if (status === 'completed') return 'ok'
  return 'muted'
}
function statusLabel(status: string): string {
  return formatPipelineExecutionStatus(status)
}
function formatDuration(sec: number | null | undefined): string {
  if (sec == null) return '—'
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return s ? `${m}m${s}s` : `${m}m`
  const h = Math.floor(m / 60)
  const mm = m % 60
  return mm ? `${h}h${mm}m` : `${h}h`
}
function pct(value: number | null | undefined): string {
  return value == null ? '—' : `${value}%`
}
function barWidth(value: number | null | undefined): string {
  if (value == null) return '0%'
  return `${Math.max(0, Math.min(100, value))}%`
}
function executionRoute(ex: AdminExecutionItem): RouteLocationRaw {
  return {
    path: `/studies/${ex.study_id}/pipeline`,
    query: { pipeline_id: String(ex.pipeline_id), execution_id: ex.id, from: 'admin' },
  }
}
function failureRoute(fail: AdminFailureItem): RouteLocationRaw {
  return {
    path: `/studies/${fail.study_id}/pipeline`,
    query: { pipeline_id: String(fail.pipeline_id), execution_id: fail.id, from: 'admin' },
  }
}

// 切到某 tab 时按需首次加载
watch(activeTab, (tab) => {
  if (tab === 'runtime' && !runtime.value) void loadRuntime()
  if (tab === 'audit' && !auditLoaded) {
    auditLoaded = true
    void loadAuditFacets()
    void loadAudit()
  }
})

// 自动刷新：仅刷当前可见 tab 的监测数据（审计不轮询）
const POLL_INTERVAL_MS = 6000
let pollTimer: ReturnType<typeof setInterval> | null = null
function poll() {
  if (!autoRefresh.value) return
  if (typeof document !== 'undefined' && document.hidden) return
  if (activeTab.value === 'overview' && !loadingOverview.value) void loadOverview(true)
  else if (activeTab.value === 'runtime' && !loadingRuntime.value) void loadRuntime(true)
}

onMounted(() => {
  if (!isAdmin.value) return
  void loadOverview()
  pollTimer = setInterval(poll, POLL_INTERVAL_MS)
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.ops-header {
  align-items: flex-start;
  gap: var(--s-4);
}
.ops-header__heading { min-width: 0; }
.ops-header__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.ops-refresh-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--c-text-3);
  font-size: 12px;
}
.ops-refresh-hint__dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--c-text-3);
}
.ops-refresh-hint.is-on .ops-refresh-hint__dot {
  background: var(--c-success);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, .14);
}
.ops-guard { padding: var(--s-6) 0; }

.ops-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: var(--s-4);
  border-bottom: 1px solid var(--c-border);
}
.ops-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 14px;
  margin-bottom: -1px;
  color: var(--c-text-2);
  font-size: 13px;
  font-weight: 600;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}
.ops-tab:hover { color: var(--c-text); }
.ops-tab.is-active {
  color: var(--c-primary);
  border-bottom-color: var(--c-primary);
}

.ops-section { display: grid; gap: var(--s-4); }
.ops-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: var(--s-6);
  color: var(--c-text-3);
  font-size: 13px;
}

/* 健康灯 */
.ops-health {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.ops-health__light {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 170px;
  padding: 10px 14px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  box-shadow: var(--shadow-sm);
}
.ops-health__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  color: var(--c-text-2);
  background: var(--c-bg-tint);
  border-radius: var(--r-sm);
}
.ops-health__dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: var(--c-text-3);
  flex-shrink: 0;
}
.ops-health__light.is-ok .ops-health__dot { background: var(--c-success); box-shadow: 0 0 0 3px rgba(16,185,129,.14); }
.ops-health__light.is-warn .ops-health__dot { background: var(--c-warning); box-shadow: 0 0 0 3px rgba(245,158,11,.14); }
.ops-health__light.is-bad .ops-health__dot { background: var(--c-danger); box-shadow: 0 0 0 3px rgba(239,68,68,.14); }
.ops-health__light.is-ok .ops-health__icon { color: var(--c-success); background: var(--c-success-soft); }
.ops-health__light.is-warn .ops-health__icon { color: var(--c-warning); background: var(--c-warning-soft); }
.ops-health__light.is-bad .ops-health__icon { color: var(--c-danger); background: var(--c-danger-soft); }
.ops-health__text { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.ops-health__text strong { font-size: 13px; }
.ops-health__text span { color: var(--c-text-3); font-size: 11px; }
.ops-health__light.is-warn .ops-health__text span { color: var(--c-warning); }
.ops-health__light.is-bad .ops-health__text span { color: var(--c-danger); }
.ops-health__light.is-loading,
.ops-metric.is-loading { animation: ops-pulse 1.3s ease-in-out infinite; }
@keyframes ops-pulse { 0%, 100% { opacity: .5; } 50% { opacity: .82; } }

/* 告警条 */
.ops-attention { display: grid; gap: 8px; }
.ops-attention__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--r);
  border-left: 4px solid;
  font-size: 13px;
}
.ops-attention__row.is-danger { background: var(--c-danger-soft); border-left-color: var(--c-danger); color: var(--c-danger); }
.ops-attention__row.is-warn { background: var(--c-warning-soft); border-left-color: var(--c-warning); color: var(--c-warning); }

/* 数字墙 */
.ops-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}
.ops-metric {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  padding: 13px 15px;
}
.ops-metric__chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  color: var(--c-text-2);
  background: var(--c-bg-tint);
  border-radius: var(--r);
}
.ops-metric__chip.is-info { color: var(--c-info); background: var(--c-info-soft); }
.ops-metric__chip.is-accent { color: var(--c-accent); background: var(--c-accent-soft); }
.ops-metric__chip.is-ok { color: var(--c-success); background: var(--c-success-soft); }
.ops-metric__chip.is-warn { color: var(--c-warning); background: var(--c-warning-soft); }
.ops-metric__body { min-width: 0; }
.ops-metric__label { color: var(--c-text-2); font-size: 12px; font-weight: 600; }
.ops-metric__value { font-size: 24px; font-weight: 800; line-height: 1.15; font-variant-numeric: tabular-nums; margin: 1px 0; }
.ops-metric__hint { overflow: hidden; color: var(--c-text-3); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

/* 执行状态分布：比例条 + 图例 */
.ops-distbar {
  display: flex;
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--c-bg-tint);
}
.ops-distbar__seg { height: 100%; min-width: 2px; }
.ops-distbar__seg.is-info { background: var(--c-info); }
.ops-distbar__seg.is-warn { background: var(--c-warning); }
.ops-distbar__seg.is-danger { background: var(--c-danger); }
.ops-distbar__seg.is-ok { background: var(--c-success); }
.ops-distbar__seg.is-muted { background: var(--c-text-3); }
.ops-distlegend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin-top: 14px;
}
.ops-distlegend__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--c-text-2);
  font-size: 12px;
}
.ops-distlegend__item strong { font-variant-numeric: tabular-nums; }
.ops-distlegend__dot { width: 9px; height: 9px; border-radius: 999px; background: var(--c-text-3); }
.ops-distlegend__dot.is-info { background: var(--c-info); }
.ops-distlegend__dot.is-warn { background: var(--c-warning); }
.ops-distlegend__dot.is-danger { background: var(--c-danger); }
.ops-distlegend__dot.is-ok { background: var(--c-success); }
.ops-distlegend__dot.is-muted { background: var(--c-text-3); }

/* 卡片 */
.ops-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: var(--s-5);
  box-shadow: var(--shadow-sm);
}
.ops-card--alert { border-color: rgba(239, 68, 68, .35); }
.ops-card__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s-3);
  margin-bottom: var(--s-4);
}
.ops-card__head h2 { margin: 0; font-size: 15px; font-weight: 700; }
.ops-card__head span { color: var(--c-text-3); font-size: 12px; }
.ops-ok { color: var(--c-success); }
.ops-bad { color: var(--c-danger); }
.ops-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s-4); }

.ops-states { display: flex; flex-wrap: wrap; gap: 16px; }
.ops-state { display: flex; align-items: center; gap: 7px; }
.ops-state__dot { width: 9px; height: 9px; border-radius: 999px; background: var(--c-text-3); }
.ops-state strong { font-size: 20px; font-weight: 800; font-variant-numeric: tabular-nums; }
.ops-state span:last-child { color: var(--c-text-3); font-size: 12px; }
.ops-state.is-info .ops-state__dot { background: var(--c-info); }
.ops-state.is-warn .ops-state__dot { background: var(--c-warning); }
.ops-state.is-danger .ops-state__dot { background: var(--c-danger); }
.ops-state.is-ok .ops-state__dot { background: var(--c-success); }

.ops-queue { display: flex; flex-wrap: wrap; gap: 22px; margin-bottom: 10px; }
.ops-queue__stat { display: flex; flex-direction: column; }
.ops-queue__stat strong { font-size: 22px; font-weight: 800; font-variant-numeric: tabular-nums; }
.ops-queue__stat span { color: var(--c-text-3); font-size: 12px; }
.ops-queue__stat.is-info strong { color: var(--c-info); }
.ops-queue__stat.is-warn strong { color: var(--c-warning); }
.ops-queue__stat.is-danger strong { color: var(--c-danger); }

.ops-subtle { color: var(--c-text-3); font-size: 12px; }
.ops-muted { color: var(--c-text-3); }

.ops-worker-list { display: grid; gap: 6px; margin-top: 8px; }
.ops-worker-row { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--c-text-2); }
.ops-worker-row code { font-family: var(--ff-mono); font-size: 11px; }

.ops-bars { display: grid; gap: 12px; }
.ops-bar__head { display: flex; justify-content: space-between; font-size: 12px; color: var(--c-text-2); margin-bottom: 4px; }
.ops-bar__track { height: 8px; border-radius: 999px; background: var(--c-bg-tint); overflow: hidden; }
.ops-bar__fill { height: 100%; border-radius: 999px; background: var(--c-text-3); transition: width .4s ease; }
.ops-bar__fill.is-info { background: var(--c-info); }
.ops-bar__fill.is-warn { background: var(--c-warning); }
.ops-bar__fill.is-ok { background: var(--c-success); }
.ops-bar__fill.is-danger { background: var(--c-danger); }

/* 列表 */
.ops-list { display: grid; gap: 8px; }
.ops-list__row {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--s-3);
  padding: 11px 13px;
  color: var(--c-text);
  text-decoration: none;
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
}
a.ops-list__row:hover { border-color: var(--c-border-strong); background: #fafbfd; }
.ops-list__row.is-alert { background: #fffbf1; border-color: rgba(239, 68, 68, .25); }
.ops-list__dot { width: 9px; height: 9px; border-radius: 999px; background: var(--c-text-3); flex-shrink: 0; }
.ops-list__dot.is-info { background: var(--c-info); box-shadow: 0 0 0 3px rgba(59,130,246,.16); }
.ops-list__dot.is-warn { background: var(--c-warning); }
.ops-list__dot.is-danger { background: var(--c-danger); }
.ops-list__dot.is-ok { background: var(--c-success); }
.ops-list__body { min-width: 0; }
.ops-list__title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.ops-list__title strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.ops-list__body p { margin: 2px 0 0; overflow: hidden; color: var(--c-text-3); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.ops-list__meta { color: var(--c-text-3); font-family: var(--ff-mono); font-size: 11px; white-space: nowrap; }
.ops-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  color: var(--c-text-3);
  font-size: 11px;
  font-weight: 700;
  background: var(--c-bg-tint);
  border-radius: var(--r-pill);
  white-space: nowrap;
}
.ops-tag.is-danger { color: var(--c-danger); background: var(--c-danger-soft); }

/* 审计 */
.ops-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: var(--s-4); }
.ops-input {
  height: 34px;
  padding: 0 10px;
  font-size: 13px;
  color: var(--c-text);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
}
.ops-table-wrap { overflow-x: auto; }
.ops-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ops-table th {
  text-align: left;
  padding: 8px 10px;
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 600;
  border-bottom: 1px solid var(--c-border);
  white-space: nowrap;
}
.ops-table td { padding: 9px 10px; border-bottom: 1px solid var(--c-border); vertical-align: top; }
.ops-action { font-family: var(--ff-mono); font-size: 12px; color: var(--c-primary); }
.ops-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-3);
  margin-top: var(--s-4);
  color: var(--c-text-3);
  font-size: 12px;
}
.ops-pager__btns { display: flex; gap: 8px; }

@media (max-width: 900px) {
  .ops-grid-2 { grid-template-columns: 1fr; }
}
</style>
