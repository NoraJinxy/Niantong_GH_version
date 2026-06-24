"""
Purpose: Provide reusable service-layer logic for dataset_qa so routers stay thin.
Related: app/routers/*, app/models/*, docs_v2/7-30.
"""

from __future__ import annotations

from csv import DictReader
from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas.dataset import (
    DATASET_QA_MODE_MOCK,
    DATASET_QA_REPORT_VERSION,
    DatasetQaHumanReview,
    DatasetQaReport,
    DatasetQaStage,
    DatasetQaStageItem,
    DatasetQaSummary,
)

REQUIRED_SIDECARS = ("import", "channels", "events")
SIGNAL_PLACEHOLDER_MESSAGE = "真实 RMS/PSD/坏段指标尚未实现。"


def build_mock_qa_report(study: Any, dataset: Any) -> dict[str, Any]:
    """Build a read-only mock QA report for a dataset.

    The function intentionally does not mutate database models or files. It only
    inspects dataset metadata and lightweight file/header availability.
    """

    blocking_issues: list[str] = []
    warnings: list[str] = []

    stages = [
        _preflight_stage(dataset, blocking_issues, warnings),
        _identity_stage(dataset, warnings),
        _file_integrity_stage(study, dataset, blocking_issues, warnings),
        _metadata_consistency_stage(dataset, blocking_issues, warnings),
        _fif_header_stage(study, dataset, blocking_issues, warnings),
        _channels_sidecar_stage(study, dataset, warnings),
        _events_sidecar_stage(study, dataset, warnings),
        _signal_placeholder_stage(),
    ]

    mock_qc_status = "blocked" if blocking_issues else "passed_with_warnings" if warnings else "passed"
    level = "bad" if blocking_issues else "warning" if warnings else "good"
    report = DatasetQaReport(
        version=DATASET_QA_REPORT_VERSION,
        mode=DATASET_QA_MODE_MOCK,
        generated_at=datetime.utcnow(),
        summary=DatasetQaSummary(
            mock_qc_status=mock_qc_status,
            level=level,
            score=None,
            blocking_issues=blocking_issues,
            warnings=warnings,
        ),
        stages=stages,
        human_review=DatasetQaHumanReview(),
        history=[],
    )
    return report.model_dump(mode="json")


def _preflight_stage(dataset: Any, blocking_issues: list[str], warnings: list[str]) -> DatasetQaStage:
    items: list[DatasetQaStageItem] = []
    dataset_id = _text(_get(dataset, "id"))
    current_upload_id = _text(_get(dataset, "current_version_id"))
    current_upload = _get(dataset, "current_version")
    qa_status = _text(_get(dataset, "qa_status"))

    _add_item(
        items,
        key="dataset_exists",
        label="Dataset 记录存在",
        ok=bool(dataset_id),
        fail_message="Dataset 缺少 id。",
        blocking_issues=blocking_issues,
        block_code="dataset_id_missing",
        value=dataset_id,
    )
    _add_item(
        items,
        key="current_upload",
        label="当前上传版本存在",
        ok=bool(current_upload_id or current_upload),
        fail_message="Dataset 缺少 current_upload_id 或 current_upload。",
        blocking_issues=blocking_issues,
        block_code="current_upload_missing",
        value=current_upload_id or _text(_get(current_upload, "id")),
    )

    if qa_status not in {"converted", "checked"}:
        warnings.append(f"qa_status 当前为 {qa_status or 'unknown'}，不是 converted/checked。")
        items.append(
            DatasetQaStageItem(
                key="qa_status",
                label="当前 qa_status",
                status="warning",
                severity="warning",
                message="模拟质控推荐从 converted 数据开始。",
                value=qa_status or "unknown",
            )
        )
    else:
        items.append(
            DatasetQaStageItem(
                key="qa_status",
                label="当前 qa_status",
                status="pass",
                value=qa_status,
            )
        )

    return _stage("preflight", "前置状态", items)


def _identity_stage(dataset: Any, warnings: list[str]) -> DatasetQaStage:
    items = [
        _identity_item("subject", "被试", _get_nested(dataset, "subject", "bids_subject_id") or _get(dataset, "bids_subject_id"), required=True, warnings=warnings),
        _identity_item("task", "Task", _get(dataset, "task"), required=True, warnings=warnings),
        _identity_item("session", "Session", _get(dataset, "session"), required=False, warnings=warnings),
        _identity_item("run", "Run", _get(dataset, "run"), required=False, warnings=warnings),
    ]
    return _stage("identity", "数据身份检查", items)


def _file_integrity_stage(study: Any, dataset: Any, blocking_issues: list[str], warnings: list[str]) -> DatasetQaStage:
    items: list[DatasetQaStageItem] = []

    source_path = _get(dataset, "source_path")
    source_abs = _resolve_study_path(study, source_path)
    _add_file_item(
        items,
        key="source_exists",
        label="原始归档存在",
        path_value=source_path,
        abs_path=source_abs,
        block=False,
        blocking_issues=blocking_issues,
        warnings=warnings,
    )

    fif_path = _get(dataset, "fif_path")
    fif_abs = _resolve_study_path(study, fif_path)
    _add_file_item(
        items,
        key="fif_exists",
        label="FIF 文件存在",
        path_value=fif_path,
        abs_path=fif_abs,
        block=True,
        blocking_issues=blocking_issues,
        warnings=warnings,
    )

    sidecar_paths = _sidecar_paths(dataset)
    for key in REQUIRED_SIDECARS:
        sidecar_value = sidecar_paths.get(key)
        sidecar_abs = _resolve_study_path(study, sidecar_value)
        _add_file_item(
            items,
            key=f"sidecar_{key}_exists",
            label=f"{key} sidecar 存在",
            path_value=sidecar_value,
            abs_path=sidecar_abs,
            block=False,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )

    return _stage("file_integrity", "文件完整性检查", items)


def _metadata_consistency_stage(dataset: Any, blocking_issues: list[str], warnings: list[str]) -> DatasetQaStage:
    items: list[DatasetQaStageItem] = []
    _add_numeric_item(items, "n_channels", "通道数", _get(dataset, "n_channels"), minimum=1, blocking=True, blocking_issues=blocking_issues, warnings=warnings)
    _add_numeric_item(items, "sfreq", "采样率", _get(dataset, "sfreq"), minimum=1, blocking=True, blocking_issues=blocking_issues, warnings=warnings)
    _add_numeric_item(
        items,
        "duration_seconds",
        "数据时长",
        _get(dataset, "duration_seconds"),
        minimum=0.001,
        blocking=True,
        blocking_issues=blocking_issues,
        warnings=warnings,
    )
    _add_numeric_item(items, "n_events", "事件数", _get(dataset, "n_events"), minimum=0, blocking=False, blocking_issues=blocking_issues, warnings=warnings)

    checksum = _text(_get(dataset, "checksum"))
    if checksum:
        items.append(DatasetQaStageItem(key="checksum", label="checksum", status="pass", value=checksum))
    else:
        warnings.append("Dataset 缺少 checksum。")
        items.append(
            DatasetQaStageItem(
                key="checksum",
                label="checksum",
                status="warning",
                severity="warning",
                message="Dataset 缺少 checksum。",
            )
        )
    return _stage("metadata_consistency", "元数据一致性检查", items)


def _fif_header_stage(study: Any, dataset: Any, blocking_issues: list[str], warnings: list[str]) -> DatasetQaStage:
    fif_path = _get(dataset, "fif_path")
    fif_abs = _resolve_study_path(study, fif_path)
    if not fif_path or not fif_abs or not fif_abs.exists():
        return DatasetQaStage(
            key="fif_header",
            title="FIF 头部快速读取",
            status="fail",
            severity="error",
            message="FIF 文件缺失，无法读取头部。",
            items=[
                DatasetQaStageItem(
                    key="fif_header_readable",
                    label="FIF 头部可读取",
                    status="fail",
                    severity="error",
                    message="FIF 文件缺失。",
                    value=str(fif_path or ""),
                )
            ],
        )

    try:
        import mne  # type: ignore
    except Exception:
        warnings.append("当前环境缺少 MNE，跳过 FIF 头部读取。")
        return DatasetQaStage(
            key="fif_header",
            title="FIF 头部快速读取",
            status="not_computed",
            severity="warning",
            message="当前环境缺少 MNE，未读取 FIF 头部。",
            items=[
                DatasetQaStageItem(
                    key="mne_available",
                    label="MNE 可用",
                    status="not_computed",
                    severity="warning",
                    message="当前环境缺少 MNE。",
                )
            ],
        )

    try:
        raw = mne.io.read_raw_fif(str(fif_abs), preload=False, verbose="ERROR")
        try:
            sfreq = float(raw.info["sfreq"]) if raw.info.get("sfreq") else None
            n_channels = int(raw.info.get("nchan") or len(raw.ch_names))
            n_times = getattr(raw, "n_times", None)
            duration = float(n_times / sfreq) if sfreq and n_times is not None else None
        finally:
            close = getattr(raw, "close", None)
            if callable(close):
                close()
    except Exception as exc:
        blocking_issues.append("fif_header_unreadable")
        return DatasetQaStage(
            key="fif_header",
            title="FIF 头部快速读取",
            status="fail",
            severity="error",
            message=f"FIF 头部读取失败: {exc}",
            items=[
                DatasetQaStageItem(
                    key="fif_header_readable",
                    label="FIF 头部可读取",
                    status="fail",
                    severity="error",
                    message=str(exc),
                    value=str(fif_abs),
                )
            ],
        )

    items = [
        _compare_numeric_item("fif_n_channels", "FIF 通道数与数据库一致", n_channels, _get(dataset, "n_channels"), warnings),
        _compare_numeric_item("fif_sfreq", "FIF 采样率与数据库一致", sfreq, _get(dataset, "sfreq"), warnings),
        _compare_numeric_item("fif_duration", "FIF 时长与数据库一致", duration, _get(dataset, "duration_seconds"), warnings, tolerance=0.05),
    ]
    return _stage("fif_header", "FIF 头部快速读取", items)


def _channels_sidecar_stage(study: Any, dataset: Any, warnings: list[str]) -> DatasetQaStage:
    sidecar_path = _sidecar_paths(dataset).get("channels")
    abs_path = _resolve_study_path(study, sidecar_path)
    if not sidecar_path or not abs_path or not abs_path.exists():
        warnings.append("缺少 channels sidecar，无法复核通道清单。")
        return DatasetQaStage(
            key="channels_sidecar",
            title="通道清单检查",
            status="warning",
            severity="warning",
            message="缺少 channels sidecar。",
            items=[
                DatasetQaStageItem(
                    key="channels_sidecar_exists",
                    label="channels sidecar 存在",
                    status="warning",
                    severity="warning",
                    value=str(sidecar_path or ""),
                )
            ],
        )

    rows = _read_tsv_rows(abs_path)
    row_count = len(rows)
    expected = _as_number(_get(dataset, "n_channels"))
    items = [
        DatasetQaStageItem(key="channels_rows", label="channels.tsv 行数", status="pass" if row_count else "warning", severity="info" if row_count else "warning", value=row_count),
    ]
    if expected is not None and row_count and int(expected) != row_count:
        warnings.append("channels.tsv 行数与数据库 n_channels 不一致。")
        items.append(
            DatasetQaStageItem(
                key="channels_row_count_matches",
                label="通道行数与数据库一致",
                status="warning",
                severity="warning",
                message="channels.tsv 行数与数据库 n_channels 不一致。",
                value={"expected": int(expected), "actual": row_count},
            )
        )
    else:
        items.append(
            DatasetQaStageItem(
                key="channels_row_count_matches",
                label="通道行数与数据库一致",
                status="pass" if row_count else "warning",
                severity="info" if row_count else "warning",
                value={"expected": int(expected) if expected is not None else None, "actual": row_count},
            )
        )
    return _stage("channels_sidecar", "通道清单检查", items)


def _events_sidecar_stage(study: Any, dataset: Any, warnings: list[str]) -> DatasetQaStage:
    sidecar_path = _sidecar_paths(dataset).get("events")
    abs_path = _resolve_study_path(study, sidecar_path)
    if not sidecar_path or not abs_path or not abs_path.exists():
        warnings.append("缺少 events sidecar，无法复核事件清单。")
        return DatasetQaStage(
            key="events_sidecar",
            title="事件清单检查",
            status="warning",
            severity="warning",
            message="缺少 events sidecar。",
            items=[
                DatasetQaStageItem(
                    key="events_sidecar_exists",
                    label="events sidecar 存在",
                    status="warning",
                    severity="warning",
                    value=str(sidecar_path or ""),
                )
            ],
        )

    rows = _read_tsv_rows(abs_path)
    row_count = len(rows)
    duration = _as_number(_get(dataset, "duration_seconds"))
    out_of_range = 0
    if duration is not None:
        for row in rows:
            onset = _as_number(row.get("onset"))
            if onset is not None and (onset < 0 or onset > duration):
                out_of_range += 1

    items = [
        DatasetQaStageItem(key="events_rows", label="events.tsv 行数", status="pass", value=row_count),
        DatasetQaStageItem(
            key="events_onset_range",
            label="事件时间不越界",
            status="warning" if out_of_range else "pass",
            severity="warning" if out_of_range else "info",
            message="存在超出数据时长的事件。" if out_of_range else None,
            value={"out_of_range": out_of_range},
        ),
    ]
    if out_of_range:
        warnings.append("events.tsv 中存在超出数据时长的事件。")
    return _stage("events_sidecar", "事件清单检查", items)


def _signal_placeholder_stage() -> DatasetQaStage:
    return DatasetQaStage(
        key="signal_placeholder",
        title="信号质量占位",
        status="not_computed",
        severity="info",
        message=SIGNAL_PLACEHOLDER_MESSAGE,
        items=[
            DatasetQaStageItem(
                key="rms_psd_bad_segments",
                label="RMS/PSD/坏段指标",
                status="not_computed",
                severity="info",
                message=SIGNAL_PLACEHOLDER_MESSAGE,
            )
        ],
    )


def _stage(key: str, title: str, items: list[DatasetQaStageItem]) -> DatasetQaStage:
    if any(item.status == "fail" for item in items):
        status = "fail"
        severity = "error"
    elif any(item.status == "warning" for item in items):
        status = "warning"
        severity = "warning"
    elif any(item.status == "not_computed" for item in items):
        status = "not_computed"
        severity = "info"
    else:
        status = "pass"
        severity = "info"
    return DatasetQaStage(key=key, title=title, status=status, severity=severity, items=items)


def _add_item(
    items: list[DatasetQaStageItem],
    *,
    key: str,
    label: str,
    ok: bool,
    fail_message: str,
    blocking_issues: list[str],
    block_code: str,
    value: Any = None,
) -> None:
    if ok:
        items.append(DatasetQaStageItem(key=key, label=label, status="pass", value=value))
    else:
        blocking_issues.append(block_code)
        items.append(
            DatasetQaStageItem(
                key=key,
                label=label,
                status="fail",
                severity="error",
                message=fail_message,
                value=value,
            )
        )


def _identity_item(key: str, label: str, value: Any, *, required: bool, warnings: list[str]) -> DatasetQaStageItem:
    text = _text(value)
    if text:
        return DatasetQaStageItem(key=key, label=label, status="pass", value=text)
    if required:
        warnings.append(f"数据身份缺少必填字段: {label}。")
        return DatasetQaStageItem(key=key, label=label, status="warning", severity="warning", message=f"缺少 {label}。")
    return DatasetQaStageItem(key=key, label=label, status="pass", message="可为空。", value=None)


def _add_file_item(
    items: list[DatasetQaStageItem],
    *,
    key: str,
    label: str,
    path_value: Any,
    abs_path: Path | None,
    block: bool,
    blocking_issues: list[str],
    warnings: list[str],
) -> None:
    path_text = _text(path_value)
    exists = bool(abs_path and abs_path.exists())
    if exists:
        items.append(DatasetQaStageItem(key=key, label=label, status="pass", value=path_text))
        return

    message = f"{label}缺失: {path_text or '未记录路径'}。"
    if block:
        blocking_issues.append(key)
        status = "fail"
        severity = "error"
    else:
        warnings.append(message)
        status = "warning"
        severity = "warning"
    items.append(
        DatasetQaStageItem(
            key=key,
            label=label,
            status=status,
            severity=severity,
            message=message,
            value=path_text,
        )
    )


def _add_numeric_item(
    items: list[DatasetQaStageItem],
    key: str,
    label: str,
    value: Any,
    *,
    minimum: float,
    blocking: bool,
    blocking_issues: list[str],
    warnings: list[str],
) -> None:
    number = _as_number(value)
    ok = number is not None and number >= minimum
    if ok:
        items.append(DatasetQaStageItem(key=key, label=label, status="pass", value=number))
        return
    message = f"{label} 缺失或不合理。"
    if blocking:
        blocking_issues.append(f"{key}_invalid")
        status = "fail"
        severity = "error"
    else:
        warnings.append(message)
        status = "warning"
        severity = "warning"
    items.append(DatasetQaStageItem(key=key, label=label, status=status, severity=severity, message=message, value=value))


def _compare_numeric_item(
    key: str,
    label: str,
    actual: Any,
    expected: Any,
    warnings: list[str],
    *,
    tolerance: float = 0.001,
) -> DatasetQaStageItem:
    actual_num = _as_number(actual)
    expected_num = _as_number(expected)
    if actual_num is None or expected_num is None:
        warnings.append(f"{label} 无法比较，缺少实际值或数据库值。")
        return DatasetQaStageItem(
            key=key,
            label=label,
            status="warning",
            severity="warning",
            message="缺少实际值或数据库值。",
            value={"actual": actual, "expected": expected},
        )
    if abs(actual_num - expected_num) <= tolerance:
        return DatasetQaStageItem(key=key, label=label, status="pass", value={"actual": actual_num, "expected": expected_num})
    warnings.append(f"{label} 不一致。")
    return DatasetQaStageItem(
        key=key,
        label=label,
        status="warning",
        severity="warning",
        message="FIF 头部值与数据库记录不一致。",
        value={"actual": actual_num, "expected": expected_num},
    )


def _sidecar_paths(dataset: Any) -> dict[str, Any]:
    current_upload = _get(dataset, "current_version")
    paths = _get(current_upload, "sidecar_paths") or _get(dataset, "current_sidecar_paths") or {}
    return paths if isinstance(paths, dict) else {}


def _resolve_study_path(study: Any, path_value: Any) -> Path | None:
    text = _text(path_value)
    if not text:
        return None
    raw = Path(text)
    if raw.is_absolute():
        return raw
    root = _get(study, "data_root")
    if not root:
        return raw
    return (Path(str(root)) / raw).resolve()


def _read_tsv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(DictReader(handle, delimiter="\t"))
    except Exception:
        return []


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _get_nested(obj: Any, *names: str) -> Any:
    value = obj
    for name in names:
        value = _get(value, name)
        if value is None:
            return None
    return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
