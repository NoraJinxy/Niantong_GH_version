export interface User {
  id: string
  username: string
  full_name: string | null
  institution: string | null
  is_active: boolean
  is_verified: boolean
  roles: string[]
  last_login_at: string | null
  created_at: string | null
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface Study {
  id: string
  code: string
  name: string
  description: string | null
  status: string
  owner_id: string
  bids_root: string
  storage_quota_bytes: number
  created_at: string | null
  updated_at: string | null
  archived_at?: string | null
  deleted_at?: string | null
  deleted_by?: string | null
  delete_reason?: string | null
}

export interface CreateStudyRequest {
  code: string
  name: string
  description?: string | null
  storage_quota_gb: number
}

export interface StudyListResponse {
  studies: Study[]
}

export interface StudyActionResponse {
  study: Study
  message: string
}

export type StudyMemberRole = 'editor' | 'viewer'

export interface StudyMember {
  id: string
  study_id: string
  user_id: string
  username: string
  full_name: string | null
  role: 'owner' | StudyMemberRole
  can_read: boolean
  can_write: boolean
  can_run?: boolean
  can_delete: boolean
  can_export: boolean
  added_at: string | null
}

export interface StudyMemberListResponse {
  members: StudyMember[]
}

export interface StudySummaryCounts {
  recordings: number
  pipelines: number
  executions: number
  members: number
  mounts: number
  study_outputs: number
}

export interface StudySummaryPipeline {
  id: string
  name: string
  version: number
  node_count: number
  status: string
}

export interface StudySummaryExecution {
  id: string
  execution_seq: number
  status: string
  started_at: string | null
  finished_at: string | null
}

export interface StudySummaryResponse {
  counts: StudySummaryCounts
  subject_total: number
  running_execution_count: number
  member_role: string | null
  can_run: boolean
  pipelines: StudySummaryPipeline[]
  executions: StudySummaryExecution[]
  mounts: StudyDatasetMount[]
  study_outputs: StudyOutput[]
}

export interface StudyMemberUpsertRequest {
  user_id: string
  role: StudyMemberRole
}

export interface DashboardCounts {
  datasets: number
  studies: number
  pipelines: number
  executions: number
}

export interface DashboardDatasetStates {
  working: number
  active: number
  error: number
}

export interface DashboardStudyStates {
  active: number
  archived: number
}

export interface DashboardPipelineStates {
  active: number
  draft: number
}

export interface DashboardExecutionStates {
  waiting_user_input: number
  failed: number
  running: number
  queued: number
  pending: number
}

export interface DashboardStates {
  datasets: DashboardDatasetStates
  studies: DashboardStudyStates
  pipelines: DashboardPipelineStates
  executions: DashboardExecutionStates
}

export interface DashboardStudyMetrics {
  dataset_count: number
  pipeline_count: number
  execution_count: number
  running_execution_count: number
  attention_execution_count: number
}

export interface DashboardRecentStudy {
  id: string
  name: string
  code?: string | null
  description?: string | null
  status: string
  created_at?: string | null
  updated_at?: string | null
  metrics: DashboardStudyMetrics
}

export interface DashboardActiveExecution {
  id: string
  study_id: string
  pipeline_id: number
  pipeline_name: string
  execution_seq: number
  status: string
  stage_label: string
  started_at?: string | null
  finished_at?: string | null
}

export type DashboardActivityObjectKind = 'dataset' | 'study' | 'pipeline' | 'execution'
export type DashboardActivitySeverity = 'info' | 'success' | 'warn' | 'error'
export type DashboardActivityGroupKind = 'bootstrap' | 'execution_lifecycle'

export interface DashboardRecentActivityItem {
  object_kind: DashboardActivityObjectKind
  object_name: string
  action_label: string
  created_at?: string | null
  target_url?: string | null
  // 上下文字段
  study_id?: string | null
  study_name?: string | null
  pipeline_id?: number | string | null
  pipeline_name?: string | null
  execution_seq?: number | null
  severity?: DashboardActivitySeverity
  // 折叠组
  group_kind?: DashboardActivityGroupKind | null
  group_summary?: string | null
}

export interface DashboardSummaryResponse {
  counts: DashboardCounts
  states: DashboardStates
  recent_studies: DashboardRecentStudy[]
  active_executions: DashboardActiveExecution[]
  recent_activity: DashboardRecentActivityItem[]
}

// ---- 平台运维面板（admin ops console，第一期只读） ----
export type AdminHealthStatus = 'healthy' | 'degraded' | 'down' | 'warning' | 'critical' | 'unknown'
export type AdminAttentionSeverity = 'danger' | 'warn'

export interface AdminHealthLight {
  status: AdminHealthStatus
  [key: string]: unknown
}

export interface AdminAttentionItem {
  kind: string
  severity: AdminAttentionSeverity
  count: number
  label: string
}

export interface AdminOverviewResponse {
  generated_at: string
  counts: {
    users: { total: number; active: number; admins: number }
    studies: { total: number; active: number; archived: number }
    datasets: { total: number; by_status: Record<string, number> }
    dataset_versions: { total: number; published: number; by_state: Record<string, number> }
    recordings: number
    subjects: number
    study_outputs: { total: number; kept: number }
    pipelines: number
    executions: { total: number; by_status: Record<string, number> }
    pending_reviews: { withdrawals: number; publicizations: number }
    async_tasks: { queued: number; running: number }
  }
  execution_states: Record<string, number>
  health: {
    api: AdminHealthLight
    db: AdminHealthLight
    redis: AdminHealthLight
    worker: AdminHealthLight & { online: boolean; worker_count: number; note: string | null }
    disk: AdminHealthLight & { percent: number | null; free: number | null; total: number | null }
  }
  attention: AdminAttentionItem[]
  resources_summary: {
    cpu_percent: number | null
    mem_percent: number | null
    disk_percent: number | null
  }
}

export interface AdminExecutionItem {
  id: string
  study_id: string
  study_name: string | null
  pipeline_id: number
  pipeline_name: string | null
  execution_seq: number
  status: string
  trigger: string
  node_count: number
  started_at: string | null
  age_seconds: number | null
  suspected_stuck: boolean
}

export interface AdminLockItem {
  id: string
  study_id: string | null
  study_name: string | null
  resource_id: string
  locked_at: string | null
  expires_at: string | null
  age_seconds: number | null
  expired: boolean
}

export interface AdminFailureItem {
  id: string
  study_id: string
  study_name: string | null
  pipeline_id: number
  pipeline_name: string | null
  execution_seq: number
  finished_at: string | null
  error_message: string | null
}

export interface AdminRuntimeResponse {
  generated_at: string
  queue: {
    running: number
    queued: number
    waiting_user_input: number
    failed_recent: number
    async_queued: number
    async_running: number
  }
  workers: {
    online: boolean
    worker_count: number
    active: number
    reserved: number
    workers: Array<{ name: string; active: number; reserved: number }>
    error: string | null
  }
  resources: {
    psutil_available: boolean
    cpu_percent: number | null
    cpu_count: number | null
    load_avg: number[] | null
    mem: { total: number; used: number; available: number; percent: number } | null
    disk: { path: string; total: number; used: number; free: number; percent: number | null } | null
    error?: string | null
  }
  executions: AdminExecutionItem[]
  stuck_executions: AdminExecutionItem[]
  locks: AdminLockItem[]
  recent_failures: AdminFailureItem[]
}

export interface AdminAuditEvent {
  id: string
  action: string
  event_scope: string
  actor_id: string | null
  actor_name: string | null
  resource_kind: string | null
  resource_id: string | null
  resource_label: string | null
  study_id: string | null
  occurred_at: string | null
  metadata: Record<string, unknown>
  has_snapshot: boolean
}

export interface AdminAuditEventsResponse {
  events: AdminAuditEvent[]
  total: number
  limit: number
  offset: number
}

export interface AdminAuditFacets {
  actions: string[]
  resource_kinds: string[]
}

export interface StudyActivityItem {
  id: string
  event_type: string
  actor_id?: string | null
  actor_name?: string | null
  resource_kind?: string | null
  resource_id?: string | null
  message?: string | null
  metadata_json: Record<string, unknown>
  created_at?: string | null
}

export type DatasetQaMode = 'mock' | 'real'
export type DatasetQaReviewConclusion = 'accept' | 'reject' | 'hold'
export type DatasetQaStageStatus = 'pass' | 'warning' | 'fail' | 'not_computed' | 'skipped' | 'pending'
export type DatasetQaSeverity = 'info' | 'warning' | 'error'

export interface DatasetQaStageItem {
  key: string
  label: string
  status: DatasetQaStageStatus
  severity: DatasetQaSeverity
  message?: string | null
  value?: unknown
  metadata: Record<string, unknown>
}

export interface DatasetQaStage {
  key: string
  title: string
  status: DatasetQaStageStatus
  severity: DatasetQaSeverity
  message?: string | null
  items: DatasetQaStageItem[]
  metadata: Record<string, unknown>
}

export interface DatasetQaSummary {
  mock_qc_status?: string | null
  level?: string | null
  score: number | null
  blocking_issues: string[]
  warnings: string[]
}

export interface DatasetQaHumanReview {
  conclusion?: DatasetQaReviewConclusion | null
  notes?: string | null
  reviewed_by?: string | null
  reviewed_at?: string | null
}

export interface DatasetQaHistoryItem {
  action: string
  actor_id?: string | null
  at?: string | null
  status?: string | null
  [key: string]: unknown
}

export interface DatasetQaReport {
  version: string
  mode: DatasetQaMode
  generated_at?: string | null
  summary: DatasetQaSummary
  stages: DatasetQaStage[]
  human_review: DatasetQaHumanReview
  history: DatasetQaHistoryItem[]
}

export interface DatasetQaResponse {
  dataset_id: string
  study_id: string
  qa_status?: string | null
  qa_report?: DatasetQaReport | null
  has_report: boolean
  current_upload_id?: string | null
  imported_at?: string | null
}

export interface DatasetQaMockRunResponse {
  dataset_id: string
  study_id: string
  qa_status: string
  qa_report: DatasetQaReport
}

export interface DatasetQaReviewRequest {
  conclusion: DatasetQaReviewConclusion
  notes?: string | null
}

export interface DatasetQaReviewResponse {
  dataset_id: string
  study_id: string
  qa_status: string
  qa_report: DatasetQaReport
}

// 存活态统一 working（去掉 active）；archived/deleted/quarantined 为内部记账态
export type DatasetAssetStatus = 'working' | 'archived' | 'deleted' | 'quarantined'
export type DatasetAssetVisibility = 'private' | 'shared' | 'public'

export interface DatasetAssetCreateRequest {
  name: string
  code: string
  description?: string | null
  visibility?: DatasetAssetVisibility
  metadata_json?: Record<string, unknown>
}

// PATCH 仅保留 name/description（owner+admin 可改）；可见范围改走专用「开放」端点 openVisibility
export interface DatasetAssetUpdateRequest {
  name?: string
  description?: string | null
  metadata_json?: Record<string, unknown>
}

// 可见范围「开放」请求：只升不降（private<shared<public），target 必须 > 当前
export interface DatasetAssetOpenVisibilityRequest {
  target: Extract<DatasetAssetVisibility, 'shared' | 'public'>
}

// 邀请制授权（dataset_members，按用户授权）
export interface DatasetMember {
  id: string
  asset_id: string
  user_id: string
  username?: string | null
  full_name?: string | null
  granted_by: string | null
  granted_at: string | null
}

export interface DatasetMemberListResponse {
  members: DatasetMember[]
}

export interface DatasetMemberAddRequest {
  // #14：接受用户名 / 邮箱 / 用户 UUID，后端统一解析为用户
  user_identifier: string
}

export interface DatasetAsset {
  id: string
  name: string
  code: string
  description?: string | null
  owner_id?: string | null
  status: DatasetAssetStatus | string
  visibility: DatasetAssetVisibility | string
  metadata_json: Record<string, unknown>
  // Phase 3 (docs_v2/3-25): 生命周期相关字段
  primary_study_id?: string | null
  concept_doi?: string | null
  current_version_id?: string | null
  // UI Phase (docs_v2/6-05): 数据概要聚合（后端 compute_asset_stats）
  subject_count?: number
  recording_count?: number
  task_codes?: string[]
  total_duration_seconds?: number
  last_imported_at?: string | null
  created_by?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface DatasetAssetListResponse {
  assets: DatasetAsset[]
}

// Phase 3 (docs_v2/3-25): 数据集版本生命周期状态机
// unpublished=未发布(原 draft) / published=已发布 / withdraw_requested=撤回审核中 / withdrawn=已撤回
export type DatasetVersionState = 'unpublished' | 'published' | 'withdraw_requested' | 'withdrawn'
export type DatasetVersionQaStatus = 'pass' | 'fail' | 'not_run'
export type WithdrawalDecision = 'approved' | 'rejected' | 'emergency'

export interface DatasetVersion {
  id: string
  dataset_asset_id: string
  version_label: string
  // Phase 3 (docs_v2/3-25): 生命周期字段（旧 status 列已删除，发布状态以 state 为准）
  state?: DatasetVersionState
  qa_status?: DatasetVersionQaStatus
  content_hash?: string | null
  version_doi?: string | null
  published_at?: string | null
  published_by?: string | null
  withdraw_requested_at?: string | null
  withdraw_requested_by?: string | null
  withdraw_reason?: string | null
  withdrawn_at?: string | null
  withdrawn_by?: string | null
  withdrawal_admin_notes?: string | null
  storage_uri?: string | null
  metadata_json: Record<string, unknown>
  created_by?: string | null
  created_at?: string | null
}

export interface DatasetVersionPublishRequest {
  version_label: string
  // 发布合规关口（规则 3）：每次发布都需重做脱敏确认 + 伦理/版权声明
  deidentified_confirmed: boolean
  ethics_statement: string
  license_statement: string
}

export interface DatasetVersionPublishResponse {
  dataset_version: DatasetVersion
  previous_version_label: string
  is_first_published_version: boolean
  concept_doi?: string | null
}

export interface DatasetVersionWithdrawRequest {
  reason: string
}

export interface DatasetWithdrawalRequestRecord {
  id: string
  dataset_version_id: string
  requested_by: string
  requested_at: string
  reason: string
  reviewed_by?: string | null
  reviewed_at?: string | null
  decision?: WithdrawalDecision | null
  admin_notes?: string | null
  notification_sent_at?: string | null
}

export interface WithdrawalReviewRequest {
  decision: 'approved' | 'rejected'
  admin_notes?: string | null
}

export interface EmergencyTakedownRequest {
  reason: string
}

// 转公开审核（3-25 §4.2，shared → public 先审后开）。decision='auto' = 调试期自动通过。
export type PublicizationDecision = 'approved' | 'rejected' | 'auto'

export interface DatasetPublicizationRequestRecord {
  id: string
  asset_id: string
  requested_by: string
  requested_at: string
  reason?: string | null
  reviewed_by?: string | null
  reviewed_at?: string | null
  decision?: PublicizationDecision | null
  admin_notes?: string | null
  notified_at?: string | null
}

export interface PublicizationRequestBody {
  reason?: string | null
}

export interface PublicizationReviewRequest {
  decision: 'approved' | 'rejected'
  admin_notes?: string | null
}

export interface DatasetAssetTaskRequest {
  version_label?: string | null
  dry_run?: boolean
  parameters_json?: Record<string, unknown>
}

export interface DatasetBootstrapPairedStudy {
  mode: 'create' | 'existing'
  study_id?: string | null
  code?: string | null
  name?: string | null
  description?: string | null
  storage_quota_gb?: number
}

export interface DatasetBootstrapRequest {
  dataset: DatasetAssetCreateRequest
  paired_study: DatasetBootstrapPairedStudy
  mount_name?: string
  selection_json?: Record<string, unknown>
  is_active?: boolean
}

export interface DatasetBootstrapNextUpload {
  study_id: string
  dataset_asset_id: string
  dataset_version_id: string
  mount_id: string
  mount_name: string
  upload_endpoint: string
  upload_method: 'POST' | string
  form_fields: {
    dataset_asset_id?: string
    mount_name?: string
    [key: string]: string | undefined
  }
}

export interface DatasetUploadContext {
  studyId: string
  datasetAssetId: string
  datasetVersionId?: string | null
  mountId?: string | null
  mountName: string
  uploadEndpoint: string
  uploadMethod: 'POST' | string
  studyName?: string | null
  datasetAssetName?: string | null
}

export interface StudyDatasetMountCreateRequest {
  dataset_asset_id: string
  mount_name: string
  selection_json?: Record<string, unknown>
  is_active?: boolean
}

export interface StudyDatasetMountUpdateRequest {
  mount_name?: string
  selection_json?: Record<string, unknown>
  is_active?: boolean
  // Phase 3 (docs_v2/3-25) C: 升级版本
  dataset_version_id?: string | null
}

export interface StudyDatasetMount {
  id: string
  study_id: string
  dataset_asset_id: string
  // Phase 3 (docs_v2/3-25) C: 挂载锁定到的版本（前端用来判断"是否最新可升级"）
  dataset_version_id?: string | null
  mount_name: string
  selection_json: Record<string, unknown>
  is_active: boolean
  mounted_by?: string | null
  mounted_at?: string | null
  dataset_asset?: DatasetAsset | null
  dataset_version?: DatasetVersion | null
}

export interface StudyDatasetMountListResponse {
  mounts: StudyDatasetMount[]
}

export interface DatasetBootstrapResponse {
  dataset_asset: DatasetAsset
  dataset_version: DatasetVersion
  study: Study
  mount: StudyDatasetMount
  next_upload: DatasetBootstrapNextUpload
}

export interface Recording {
  id: string
  study_id: string
  dataset_asset_id?: string | null
  subject_id: string
  bids_subject_id: string
  session?: string | null
  task: string
  run?: string | null
  source_format: string
  source_path: string
  fif_path?: string | null
  current_version_id?: string | null
  current_version_seq?: number | null
  file_size?: number | null
  checksum?: string | null
  n_channels?: number | null
  sfreq?: number | null
  duration_seconds?: number | null
  n_events?: number | null
  qa_status?: string | null
  qa_report?: DatasetQaReport | Record<string, unknown> | null
  imported_by?: string | null
  imported_at?: string | null
}

export interface RecordingVersion {
  id: string
  recording_id: string
  study_id: string
  version_seq: number
  source_dir: string
  source_main_file: string
  source_files: string[]
  source_format: string
  fif_dir?: string | null
  fif_path?: string | null
  sidecar_paths: Record<string, string>
  file_size?: number | null
  checksum?: string | null
  status: string
  qa_status?: string | null
  note?: string | null
  uploaded_by?: string | null
  uploaded_at?: string | null
}

export interface RecordingListResponse {
  recordings: Recording[]
}

export interface RecordingVersionListResponse {
  versions: RecordingVersion[]
}

export interface RecordingUploadResponse {
  message: string
  recording: Recording
}

export interface RecordingRelabelPayload {
  subject: string
  session?: string | null
  task: string
  run?: string | null
}

export interface DatasetFile {
  id: string
  study_id: string
  dataset_id: string
  dataset_upload_id: string
  file_role: string
  storage_uri: string
  relative_path: string
  logical_path?: string | null
  file_size?: number | null
  sha256?: string | null
  mime_type?: string | null
  metadata_json: Record<string, unknown>
  created_by?: string | null
  created_at?: string | null
}

export interface DatasetFileListResponse {
  files: DatasetFile[]
}

/** 自定义电极位置文件（montage），数据集资产级，供「通道定位」节点选用。 */
export interface DatasetMontage {
  id: string
  dataset_asset_id: string
  name: string
  original_filename?: string | null
  file_format: string
  n_electrodes?: number | null
  file_size?: number | null
  created_at?: string | null
}

export interface DatasetMontageListResponse {
  montages: DatasetMontage[]
}

export interface DatasetFileTreeNode {
  name: string
  path: string
  kind: 'directory' | 'file'
  children: DatasetFileTreeNode[]
  file_id?: string | null
  file_role?: string | null
  storage_uri?: string | null
  relative_path?: string | null
  logical_path?: string | null
  file_size?: number | null
  sha256?: string | null
}

export interface DatasetFileTreeResponse {
  dataset_asset_id: string
  version_label?: string | null
  prefix: string
  tree: DatasetFileTreeNode
}

export type NodePhase = 'phase1' | 'phase2' | 'phase3'

export interface NodePort {
  name: string
  type: string
  label?: string | null
  required?: boolean
  cardinality?: string | null
}

export interface NodePropertyOption {
  label: string
  value: string | number | boolean
}

export interface NodeProperty {
  name: string
  label: string
  type:
    | 'string'
    | 'text'
    | 'number'
    | 'integer'
    | 'boolean'
    | 'select'
    | 'channel_list'
    | 'event_select'
    | 'event_remap_rules'
    | 'tags_input'
    | 'dataset_filter'
    | 'dataset_ids'
    | 'montage_picker'
  default?: unknown
  required?: boolean
  options?: NodePropertyOption[]
  min?: number
  max?: number
  step?: number
  unit?: string | null
  description?: string | null
  help?: string | null
  hash?: boolean
  /** 条件显示：{控制字段: [允许值,...]}，全部命中才渲染该参数。 */
  visible_when?: Record<string, Array<string | number | boolean>>
  /** true=归入折叠的「高级设置」区；默认 false=常显。 */
  advanced?: boolean
}

export interface NodeSpec {
  schema_version: string
  type: string
  title: string
  category: string
  phase: NodePhase
  description?: string | null
  tags?: string[]
  inputs: NodePort[]
  outputs: NodePort[]
  properties: NodeProperty[]
  backend: Record<string, unknown>
  cache?: Record<string, unknown>
  ui?: Record<string, unknown>
}

export interface NodeSpecListResponse {
  nodes: NodeSpec[]
}

export interface PipelineGraphNode {
  id: string
  type: string
  title?: string
  position?: [number, number]
  params: Record<string, unknown>
  ui?: Record<string, unknown>
}

export interface PipelineGraphLinkEndpoint {
  node: string
  port: string
}

export interface PipelineGraphLink {
  id: string
  from: PipelineGraphLinkEndpoint
  to: PipelineGraphLinkEndpoint
}

export interface PipelineDefinitionPayload {
  schema_version: string
  app_version?: string | null
  engine_version?: string | null
  name?: string | null
  description?: string | null
  graph: {
    nodes: PipelineGraphNode[]
    links: PipelineGraphLink[]
  }
  settings: Record<string, unknown>
}

export interface Pipeline {
  id: number
  study_id: string
  name: string
  description: string | null
  version: number
  is_template: boolean
  status: string
  node_count: number
  definition_json: PipelineDefinitionPayload
  created_by?: string | null
  created_at: string | null
  updated_at: string | null
}

export interface PipelineListResponse {
  pipelines: Pipeline[]
}

export interface PipelineCreateRequest {
  name: string
  description?: string | null
  definition_json: PipelineDefinitionPayload
  is_template?: boolean
}

export interface PipelineUpdateRequest {
  name?: string
  description?: string | null
  definition_json?: PipelineDefinitionPayload
  expected_version: number
}

export interface PipelineExecutionSelectionOverride {
  selection_mode?: 'filter' | 'explicit'
  dataset_filter?: Record<string, unknown>
  dataset_ids?: string[]
  dataset_file_ids?: string[]
  selector_json?: Record<string, unknown>
}

export interface PipelineExecutionCreateRequest {
  trigger?: 'manual'
  selection_override?: Record<string, PipelineExecutionSelectionOverride>
}

export interface PipelineExecutionRetryRequest {
  input_policy?: 'reuse_snapshot' | 're_resolve'
}

export interface PipelineEditLock {
  id: string
  study_id: string
  pipeline_id: number
  resource_kind: string
  resource_id: string
  lock_type: string
  locked_by?: string | null
  locked_at: string
  expires_at: string
  released_at?: string | null
  metadata_json: Record<string, unknown>
}

export interface PipelineValidationIssue {
  code: string
  message: string
  node_id?: string | null
  node_type?: string | null
  severity: 'error' | 'warning'
}

export interface PipelineValidationResponse {
  valid: boolean
  errors: PipelineValidationIssue[]
  warnings: PipelineValidationIssue[]
}

export interface PipelineExecution {
  id: string
  study_id: string
  pipeline_id: number
  pipeline_version: number
  execution_seq: number
  trigger: string
  status: 'running' | 'completed' | 'failed' | string
  node_count: number
  dataset_count: number
  definition_snapshot: Record<string, unknown>
  manifest_json: Record<string, unknown>
  result_json: Record<string, unknown>
  error_json: Record<string, unknown>
  started_by?: string | null
  started_at: string | null
  finished_at: string | null
}

export interface PipelineJob {
  id: string
  execution_id: string
  study_id: string
  pipeline_id: number
  node_id: string
  node_type: string
  node_title?: string | null
  status: string
  topo_index: number
  params_json: Record<string, unknown>
  input_json: Record<string, unknown>
  output_json: Record<string, unknown>
  input_hash?: string | null
  params_hash?: string | null
  node_hash?: string | null
  trace_code?: string | null
  error_json: Record<string, unknown>
  log_tail?: string | null
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
}

export interface StudyOutput {
  id: string
  study_id: string

  /** 来源追溯 */
  produced_by_execution_id?: string | null
  produced_by_job_id?: string | null
  produced_by_node_id?: string | null
  produced_by_node_type?: string | null
  produced_by_params: Record<string, unknown>
  upstream_dataset_ids: string[]
  upstream_recording_ids: string[]

  /** 来源工作流（后端 join execution→pipeline 注入；历史行可能为空） */
  pipeline_id?: number | null
  pipeline_name?: string | null
  pipeline_version?: number | null
  execution_seq?: number | null

  /** 数据语义 */
  data_type: string
  subject_id?: string | null
  bids_subject_id?: string | null
  session?: string | null
  task?: string | null
  run_label?: string | null
  condition?: string | null

  /** 用户层 */
  display_name?: string | null
  description?: string | null
  tags: string[]

  /** 物理存储 */
  storage_uri: string
  logical_path?: string | null
  file_role?: string | null
  file_size?: number | null
  sha256?: string | null
  mime_type?: string | null

  /** 保留与缓存（三层解耦：keep=用户是否保留 / cache_eligible=系统是否缓存 / deleted_at=回收站） */
  keep: boolean
  cache_eligible: boolean
  retention_expires_at?: string | null

  /** 预览 */
  preview_json: Record<string, unknown>

  /** 元数据 */
  created_at?: string | null
  created_by?: string | null
  updated_at?: string | null
  deleted_at?: string | null
  /** GC 物理清盘磁盘文件后置位；非空 = 文件已删、不可恢复/预览（DB 行仍留作追溯） */
  purged_at?: string | null
}

export interface StudyOutputListResponse {
  study_outputs: StudyOutput[]
  total: number
}

export interface StudyOutputPreview {
  study_output_id: string
  study_id: string
  produced_by_execution_id?: string | null
  produced_by_job_id?: string | null
  data_type: string
  storage_uri?: string | null
  sha256?: string | null
  keep?: boolean
  preview_json: Record<string, unknown>
  observe_route: string
  observe_query: Record<string, string>
  generated_at: string
}

export interface TimeseriesChannel {
  name: string
  values: number[]
}

export interface StudyOutputTimeseries {
  data_type: string
  unit?: string | null
  sfreq: number
  tmin: number
  tmax: number
  total_duration: number | null
  available_tmin: number
  available_tmax: number
  n_segments: number | null
  segment_index: number | null
  segment_label: string | null
  subject: string | null
  display_name: string | null
  segment_kind: 'epoch' | 'condition' | null
  segment_options: string[] | null
  n_channels_total: number
  ch_names_all: string[]
  /** 通道 2D 头皮投影坐标（单位圆内，+x=右 +y=前）；无 montage 时为 null。供地形图条。 */
  ch_pos?: Record<string, [number, number]> | null
  times: number[]
  channels: TimeseriesChannel[]
}

export interface StudyOutputTimeseriesQuery {
  tmin?: number
  tmax?: number
  index?: number
  maxPoints?: number
  maxChannels?: number
}

export interface TfrBandStat {
  name: string
  fmin: number
  fmax: number
  value: number
  /** 相对功率(占总功率 %)；PSD 视图提供，TFR 不填。 */
  rel?: number
}

export interface StudyOutputTfr {
  data_type: string
  study_output_id: string
  condition: string | null
  subject: string | null
  display_name: string | null
  method: string
  baseline_mode: string
  unit: string
  sfreq: number
  nave: number
  channel: string
  n_channels_total: number
  ch_names_all: string[]
  freqs: number[]
  times: number[]
  fmin: number | null
  fmax: number | null
  tmin: number | null
  tmax: number | null
  zmax: number
  power: number[][]
  bands: TfrBandStat[]
}

export interface StudyOutputTfrQuery {
  channel?: string
  maxFreqs?: number
  maxTimes?: number
}

export interface StudyOutputTfrTopoChannel {
  name: string
  value: number
  x: number | null
  y: number | null
}

export interface StudyOutputTfrTopo {
  data_type: string
  study_output_id: string
  condition: string | null
  unit: string
  tmin: number
  tmax: number
  fmin: number
  fmax: number
  n_channels: number
  n_positioned: number
  vmax: number
  channels: StudyOutputTfrTopoChannel[]
}

export interface StudyOutputTfrTopoQuery {
  tmin?: number
  tmax?: number
  fmin?: number
  fmax?: number
}

export interface StudyOutputTfrCubeChannel {
  name: string
  x: number | null
  y: number | null
  /** 该通道的降采样 freq×time 面（与 cube.freqs / cube.times 对齐），已按展示单位缩放、有符号。 */
  data: number[][]
}

export interface StudyOutputTfrCube {
  data_type: string
  study_output_id: string
  condition: string | null
  unit: string
  freqs: number[]
  times: number[]
  n_channels: number
  n_positioned: number
  channels: StudyOutputTfrCubeChannel[]
}

export interface StudyOutputTfrCubeQuery {
  maxFreqs?: number
  maxTimes?: number
}

export interface StudyOutputPsdChannel {
  name: string
  power: number[]
  bands: TfrBandStat[]
  pmax: number | null
  pmin: number | null
}

export interface StudyOutputPsd {
  data_type: string
  study_output_id: string
  condition: string | null
  subject: string | null
  display_name: string | null
  method: string
  unit: string
  sfreq: number
  n_channels_total: number
  ch_names_all: string[]
  ch_pos: Record<string, number[]> | null
  freqs: number[]
  fmin: number | null
  fmax: number | null
  default_channel: string
  channels: StudyOutputPsdChannel[]
}

export interface StudyOutputStatCluster {
  p: number
  significant: boolean
  n_points: number
  tmin?: number
  tmax?: number
  fmin?: number
  fmax?: number
}

export interface StudyOutputStat {
  data_type: string
  base_type: string
  study_output_id: string
  display_name: string | null
  contrast_label: string
  design: string
  method: string
  tail: string
  correction: string
  alpha: number
  n_a: number
  n_b: number
  n_significant: number
  n_total: number
  ch_names: string[]
  default_channel: string
  channel: string
  tmax_abs: number
  roi_channels: string[]
  clusters: StudyOutputStatCluster[]
  ch_pos: Record<string, number[]> | null
  axis: { kind: string; values?: number[]; freqs?: number[]; times?: number[] }
  // 1D（evoked / psd）
  t?: number[]
  sig?: boolean[]
  mean_a?: number[]
  mean_b?: number[]
  // 2D（tfr）
  t_grid?: number[][]
  sig_grid?: boolean[][]
}

export interface StudyOutputStatQuery {
  channel?: string
  maxPoints?: number
}

export interface StudyOutputPsdQuery {
  channel?: string
  maxFreqs?: number
  maxChannels?: number
}

export interface StudyOutputUpdatePayload {
  display_name?: string | null
  description?: string | null
  tags?: string[]
  keep?: boolean
  deleted?: boolean
  reason?: string | null
}

export interface StudyOutputBatchUpdatePayload {
  ids: string[]
  update: StudyOutputUpdatePayload
}

export interface StudyOutputCleanupRequest {
  dry_run?: boolean
  limit?: number
  reason?: string | null
}

export interface StudyOutputListQuery {
  execution_ids?: string[]
  node_types?: string[]
  data_types?: string[]
  bids_subject_ids?: string[]
  sessions?: string[]
  tasks?: string[]
  conditions?: string[]
  tags?: string[]
  keep?: boolean
  include_deleted?: boolean
  /** 只拉「有意义」的结果（keep/cache/已删除），跳过隐藏的纯临时中间产物——结果页提速用 */
  visible_only?: boolean
  limit?: number
  offset?: number
}

export interface PipelineExecutionDetail extends PipelineExecution {
  inputs: PipelineExecutionInput[]
  dependencies: PipelineExecutionDependency[]
  tasks: AsyncTask[]
  jobs: PipelineJob[]
  study_outputs: StudyOutput[]
}

export interface PipelineExecutionListResponse {
  executions: PipelineExecution[]
}

export interface PipelineJobListResponse {
  jobs: PipelineJob[]
}

export interface PipelineExecutionInput {
  id: string
  execution_id: string
  study_id: string
  pipeline_id: number
  job_id?: string | null
  node_id?: string | null
  node_type?: string | null
  input_slot: string
  input_index: number
  input_kind: string
  dataset_asset_id?: string | null
  dataset_id?: string | null
  dataset_upload_id?: string | null
  dataset_file_id?: string | null
  file_role?: string | null
  storage_uri?: string | null
  logical_path?: string | null
  upstream_execution_id?: string | null
  upstream_dataset_id?: string | null
  selector_json: Record<string, unknown>
  resolved_metadata_json: Record<string, unknown>
  sha256?: string | null
  created_at?: string | null
}

export interface PipelineExecutionDependency {
  id: string
  study_id: string
  execution_id: string
  depends_on_execution_id: string
  upstream_dataset_id?: string | null
  dependency_kind: string
  metadata_json: Record<string, unknown>
  created_at?: string | null
}

export interface TaskEvent {
  id: string
  task_id: string
  event_type: string
  status?: string | null
  progress?: number | null
  message?: string | null
  payload_json: Record<string, unknown>
  created_at?: string | null
}

export interface AsyncTask {
  id: string
  celery_task_id?: string | null
  task_type: string
  queue_name?: string | null
  status: string
  progress: number
  study_id?: string | null
  resource_kind: string
  resource_id?: string | null
  payload_json: Record<string, unknown>
  result_json: Record<string, unknown>
  error_json: Record<string, unknown>
  idempotency_key?: string | null
  created_by?: string | null
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  attempt: number
  max_attempts: number
  events: TaskEvent[]
}

export interface TaskEventListResponse {
  events: TaskEvent[]
}

export interface PipelineExecutionLineageGraphNode {
  id: string
  node_type: string
  label: string
  resource_kind: string
  resource_id: string
  status?: string | null
  metadata_json: Record<string, unknown>
}

export interface PipelineExecutionLineageGraphEdge {
  id: string
  source: string
  target: string
  edge_type: string
  metadata_json: Record<string, unknown>
}

export interface PipelineExecutionLineage {
  execution: PipelineExecution
  inputs: PipelineExecutionInput[]
  study_outputs: StudyOutput[]
  upstream_executions: PipelineExecution[]
  downstream_executions: PipelineExecution[]
  upstream_dependencies: PipelineExecutionDependency[]
  downstream_dependencies: PipelineExecutionDependency[]
  graph_nodes: PipelineExecutionLineageGraphNode[]
  graph_edges: PipelineExecutionLineageGraphEdge[]
}

export interface PipelineIcaComponentPreview {
  index: number
  label?: string | null
  std?: number | null
  max_abs?: number | null
  top_channels?: string[]
  [key: string]: unknown
}

export interface PipelineInteractionDecision {
  excluded_components: number[]
  decision_version: number
  submitted_by?: string | null
  submitted_at?: string | null
  [key: string]: unknown
}

export interface PipelineInteraction {
  execution_id: string
  job_id: string
  node_id: string
  node_type: string
  status: string
  interaction_type: string
  decision_version: number
  components: PipelineIcaComponentPreview[]
  preview_json: Record<string, unknown>
  decision?: PipelineInteractionDecision | null
}

export interface ArtifactBadSegment {
  onset: number
  duration: number
  source?: string
}

export interface PipelineInteractionDecisionRequest {
  // ICA 成分剔除
  excluded_components?: number[]
  // 手动去伪迹去坏段（artifact_marking 交互）
  bad_segments?: ArtifactBadSegment[]
  bad_channels?: string[]
  channel_action?: 'mark' | 'interpolate'
  decision_version: number
}

export interface PipelineResumeResponse {
  execution: PipelineExecution
  job: PipelineJob
}

export interface LoadDataResolveRequest {
  node_id?: string | null
  selection_mode: 'filter' | 'explicit'
  dataset_filter: Record<string, unknown>
  dataset_ids: string[]
}

export interface LoadDataDataInfo {
  dataset_id: string
  dataset_asset_id?: string | null
  dataset_version_id?: string | null
  dataset_file_id?: string | null
  canonical_fif_file_id?: string | null
  source_file_id?: string | null
  file_role?: string | null
  storage_uri?: string | null
  logical_path?: string | null
  sha256?: string | null
  mount_id?: string | null
  mount_name?: string | null
  study_id: string
  subject_id: string
  subject: string
  bids_subject_id: string
  session: string | null
  task: string
  run: string | null
  source_format: string
  source_path: string
  source_abs_path?: string | null
  source_exists: boolean
  fif_path: string | null
  fif_abs_path?: string | null
  fif_exists: boolean
  current_upload_id?: string | null
  current_upload_seq?: number | null
  current_fif_dir?: string | null
  sidecar_paths?: Record<string, string> | null
  file_size: number | null
  checksum: string | null
  n_channels: number | null
  sfreq: number | null
  duration_seconds: number | null
  n_events: number | null
  qa_status: string | null
  imported_at: string | null
  content_hash: string
  data_type: string
  event_labels?: string[]
  event_counts?: Record<string, number>
  /** 自动收成的可勾选 condition 分组（Epoch chips 用）。 */
  condition_groups?: Array<{ name: string; pattern?: string; mode?: string; count?: number; sample?: string }>
  /** 通道名列表（来自 FIF info），供下游节点（如 Re-reference）做通道选择候选。 */
  ch_names?: string[]
}

export interface LoadDataResolveResponse {
  valid: boolean
  study_id: string
  node_id?: string | null
  selection_mode: string
  dataset_count: number
  data_infos: LoadDataDataInfo[]
  errors: PipelineValidationIssue[]
  warnings: PipelineValidationIssue[]
  missing_dataset_ids: string[]
}

/** 沿链路解析「某节点输入端可用 condition」（方案 B：Epoch / ERP / TFR / PSD 选择器用）。 */
export interface ConditionResolveRequest {
  node_id: string
  graph: PipelineDefinitionPayload['graph']
}

export interface ConditionOption {
  name: string
  count: number
  datasets: number
}

export interface ConditionResolveResponse {
  node_id: string
  conditions: ConditionOption[]
  warnings: PipelineValidationIssue[]
}
