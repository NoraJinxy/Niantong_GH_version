$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutDir = Join-Path $ScriptDir "server_outputs"
$MetaDir = Join-Path $ScriptDir "metadata"
$Key = Join-Path $HOME ".ssh\elys_deploy_ed25519"
$HostName = "120.76.251.79"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path $MetaDir | Out-Null

$sql = @'
WITH target AS (
  SELECT 'a60fc287-feb6-4b91-9296-675f2640f64f'::uuid AS execution_id
), exec_row AS (
  SELECT e.* FROM pipeline_executions e JOIN target t ON e.id=t.execution_id
), pipeline_row AS (
  SELECT p.* FROM pipeline_definitions p JOIN exec_row e ON p.id=e.pipeline_id
), jobs AS (
  SELECT jsonb_agg(jsonb_build_object(
    'job_id', id,
    'topo_index', topo_index,
    'node_id', node_id,
    'node_type', node_type,
    'node_title', node_title,
    'status', status,
    'params', params_json
  ) ORDER BY topo_index) AS items
  FROM pipeline_jobs j JOIN target t ON j.execution_id=t.execution_id
), load_raw AS (
  SELECT output_json->'data_infos'->0 AS info
  FROM pipeline_jobs j JOIN target t ON j.execution_id=t.execution_id
  WHERE j.node_type='eeg/data/load'
  ORDER BY topo_index
  LIMIT 1
), outputs AS (
  SELECT jsonb_agg(jsonb_build_object(
    'relation', eo.relation,
    'job_id', eo.job_id,
    'study_output_id', o.id,
    'node_id', eo.node_id,
    'node_type', eo.node_type,
    'data_type', o.data_type,
    'condition', o.condition,
    'display_name', o.display_name,
    'storage_uri', o.storage_uri,
    'logical_path', o.logical_path,
    'file_size', o.file_size,
    'sha256', o.sha256
  ) ORDER BY o.created_at, o.produced_by_node_id, o.condition NULLS FIRST) AS items
  FROM execution_outputs eo
  JOIN study_outputs o ON o.id=eo.study_output_id
  JOIN target t ON eo.execution_id=t.execution_id
)
SELECT jsonb_pretty(jsonb_build_object(
  'pipeline', jsonb_build_object('id', p.id, 'study_id', p.study_id, 'name', p.name, 'version', p.version),
  'execution', jsonb_build_object('id', e.id, 'pipeline_version', e.pipeline_version, 'execution_seq', e.execution_seq, 'status', e.status, 'started_at', e.started_at, 'finished_at', e.finished_at),
  'source_raw', load_raw.info,
  'jobs', jobs.items,
  'outputs', outputs.items,
  'notes', jsonb_build_array('Execution #2 is used because it is completed and contains only sub-007; execution #3/version 4 later completed but also selected sub-008, so it has a different scope.')
))
FROM pipeline_row p, exec_row e, jobs, outputs, load_raw;
'@

$sql | ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no -i $Key "root@$HostName" "sudo -u postgres psql -d elys -At" |
    Set-Content -Encoding UTF8 (Join-Path $MetaDir "test1_manifest.json")

$files = @(
    @("/mnt/elys_data/storage/datasets/d38826f7-25d9-411a-b68c-128f81d7c077/BIDSdata/sub-007/ses-a/eeg/sub-007_ses-a_task-sensory_run-04_eeg.fif", "00_load_raw.fif"),
    @("/mnt/elys_data/storage/studies/202606000001/outputs/e8/e82a0425df725a2525dcad0cbf934aa05255f146f11888024ac0fc92cabc81f8/sub-007_ses-a_task-sensory_run-04_eeg_notch-raw.fif", "01_notch_raw.fif"),
    @("/mnt/elys_data/storage/studies/202606000001/outputs/5c/5ca6aaf1d753630ff7b3fff0f70776b6ddae84b6b8a789427a13f84faf42f86f/sub-007_ses-a_task-sensory_run-04_eeg_notch_firfilt-raw.fif", "02_bandpass_raw.fif"),
    @("/mnt/elys_data/storage/studies/202606000001/outputs/d6/d63c1ca610a4017dbed6ed45f062fda47bfc71b45298f5a2fdc64906728be165/sub-007_ses-a_task-sensory_run-04_eeg_notch_firfilt_epo-epo.fif", "03_epoch_epo.fif"),
    @("/mnt/elys_data/storage/studies/202606000001/outputs/5d/5d979aeece1a2449b2e5777cef211f6466001243ce8fa5f9cd90851cac633d6b/sub-007_ses-a_task-sensory_run-04_eeg_notch_firfilt_epo_bl-epo.fif", "04_baseline_epo.fif"),
    @("/mnt/elys_data/storage/studies/202606000001/outputs/6d/6d5a0095e1e7ffc216da90e2c188e2c1bb3d7927a4abbf3b029284d8a7fc1d4f/sub-007_ses-a_task-sensory_run-04_eeg_notch_firfilt_epo_bl_Stimulus_S__3_erp-ave.fif", "05_erp_S3-ave.fif"),
    @("/mnt/elys_data/storage/studies/202606000001/outputs/48/48bc7f6149db92d972d7c8bbd776b8aa573a34ddcee51ec957d8b369578918db/sub-007_ses-a_task-sensory_run-04_eeg_notch_firfilt_epo_bl_Stimulus_S__4_erp-ave.fif", "06_erp_S4-ave.fif"),
    @("/mnt/elys_data/storage/studies/202606000001/outputs/bf/bf917e61f17e5d211107148f17aac09e2dab67d4482c4b70e6222dd9815d846d/sub-007_ses-a_task-sensory_run-04_eeg_notch_firfilt_epo_bl_Stimulus_S__5_erp-ave.fif", "07_erp_S5-ave.fif")
)

foreach ($item in $files) {
    $remote = $item[0]
    $local = Join-Path $OutDir $item[1]
    scp -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no -i $Key "root@${HostName}:$remote" $local
}

Write-Host "Downloaded test1 outputs to $OutDir"
