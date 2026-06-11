"""
Purpose: Implement workflow/Pipeline runtime support for load_data, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

from collections import Counter
from csv import DictReader
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID
import hashlib
import json

try:
    from sqlalchemy import or_
except ImportError:  # pragma: no cover - lightweight test stubs may not expose sqlalchemy.or_
    def or_(*predicates):
        return lambda item: any(predicate(item) for predicate in predicates)
from sqlalchemy.orm import Session, joinedload

from app.models import DatasetFile, Recording, Study, StudyDatasetMount, StudySettings
from app.schemas.pipeline import LoadDataDataInfo, LoadDataResolveResponse, PipelineValidationIssue
from app.services.storage import StorageService, StorageUriError


BLOCKED_QA_STATUS = {"failed", "deleted", "rejected"}
DEFAULT_QA_STATUS = "all"
CANONICAL_LOAD_FILE_ROLE = "fif"
# 两层重构：raw_bids_data / raw_source 不再登记（raw_bids 降纯逻辑），源文件兜底只剩 original_upload（首选 fif）。
SOURCE_LOAD_FILE_ROLES = ("original_upload",)
EVENT_LABEL_COLUMNS = ("trial_type", "value", "type", "marker", "label")
EVENT_LABEL_MAX_PER_DATASET = 64
EVENT_LABEL_MAX_LENGTH = 80


def _read_dataset_ch_names(fif_abs_path: Path | None) -> list[str]:
    """Read MNE FIF header to extract ch_names. Lightweight — header only, no raw data.

    失败（fif 不存在 / mne 不可用 / 读取异常）返回空列表，不阻塞 LoadData resolve。

    策略：直接从 `info["chs"]` 列表抠 ch_name —— 这是 MNE 最底层数据，每个 ch 是 dict 含
    'ch_name' 字段。不依赖 MNE Info 的 ch_names property / dict-key 行为差异（不同版本
    可能有微妙不同，曾出现"全空字符串"症状）。三层 fallback 兜底。
    """
    import logging  # noqa: PLC0415
    logger = logging.getLogger(__name__)

    if fif_abs_path is None or not fif_abs_path.exists():
        return []
    try:
        import mne  # noqa: PLC0415
    except ImportError:
        logger.warning("_read_dataset_ch_names: mne import failed")
        return []
    try:
        info = mne.io.read_info(str(fif_abs_path), verbose="ERROR")
    except Exception as exc:
        logger.warning("_read_dataset_ch_names: read_info failed for %s: %s", fif_abs_path, exc)
        return []

    def _clean(raw: Any) -> list[str]:
        if not raw:
            return []
        out: list[str] = []
        for item in raw:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                out.append(text)
        return out

    # 1) 主路径：从 info["chs"] 抠 ch_name。chs 是 list[dict]，每个含 'ch_name'。
    chs = None
    try:
        chs = info["chs"]  # MNE Info.__getitem__ 支持
    except (KeyError, TypeError, Exception):
        chs = getattr(info, "chs", None)
    if chs and isinstance(chs, (list, tuple)):
        names: list[str] = []
        for ch in chs:
            if isinstance(ch, dict):
                names.append(str(ch.get("ch_name") or "").strip())
            else:
                names.append(str(getattr(ch, "ch_name", "") or "").strip())
        cleaned = [n for n in names if n]
        if cleaned:
            return cleaned
        logger.warning("_read_dataset_ch_names: chs has %d entries but all ch_name empty for %s",
                       len(chs), fif_abs_path)

    # 2) fallback：直接走 ch_names property
    cleaned = _clean(getattr(info, "ch_names", None))
    if cleaned:
        return cleaned

    # 3) fallback：__getitem__("ch_names")
    try:
        cleaned = _clean(info["ch_names"])  # type: ignore[index]
        if cleaned:
            return cleaned
    except (KeyError, TypeError, Exception):
        pass

    logger.warning("_read_dataset_ch_names: all three paths returned empty for %s", fif_abs_path)
    return []


def _read_dataset_event_labels(
    study: Study,
    dataset: Recording,
) -> tuple[list[str], dict[str, int]]:
    """Read events.tsv (if present) and return unique label list + per-label counts."""
    sidecar_paths: Any = None
    current_version = getattr(dataset, "current_version", None)
    if current_version is not None:
        sidecar_paths = getattr(current_version, "sidecar_paths", None)
    if not sidecar_paths:
        sidecar_paths = getattr(dataset, "current_sidecar_paths", None)
    if not isinstance(sidecar_paths, dict):
        return [], {}
    events_path = sidecar_paths.get("events")
    if not events_path:
        return [], {}
    abs_path = _resolve_storage_path(study, events_path)
    if abs_path is None or not abs_path.exists():
        return [], {}
    try:
        with abs_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(DictReader(handle, delimiter="\t"))
    except OSError:
        return [], {}
    counts: Counter[str] = Counter()
    for row in rows:
        label: str | None = None
        for column in EVENT_LABEL_COLUMNS:
            raw = row.get(column)
            if raw is None:
                continue
            text = str(raw).strip()
            if not text or text in {"n/a", "N/A"}:
                continue
            label = text[:EVENT_LABEL_MAX_LENGTH]
            break
        if label is None:
            continue
        counts[label] += 1
        if len(counts) >= EVENT_LABEL_MAX_PER_DATASET:
            break
    labels = sorted(counts.keys(), key=lambda item: (item.isdigit() is False, item))
    return labels, dict(counts)


def resolve_load_data_selection(
    *,
    db: Session,
    study: Study,
    params: dict[str, Any],
    node_id: str | None = None,
    node_type: str = "eeg/data/load",
) -> LoadDataResolveResponse:
    """Resolve a LoadData node into the dataset metadata consumed by downstream nodes."""

    selection_mode = str(params.get("selection_mode") or "filter")
    dataset_filter = params.get("dataset_filter") if isinstance(params.get("dataset_filter"), dict) else {}
    dataset_ids = params.get("dataset_ids") if isinstance(params.get("dataset_ids"), list) else []
    if selection_mode == "filter":
        dataset_filter = _apply_study_default_dataset_filter(db=db, study=study, dataset_filter=dataset_filter)

    errors: list[PipelineValidationIssue] = []
    warnings: list[PipelineValidationIssue] = []
    missing_dataset_ids: list[str] = []

    if selection_mode not in {"filter", "explicit"}:
        errors.append(
            PipelineValidationIssue(
                code="LOAD_DATA_SELECTION_MODE_INVALID",
                message="LoadData.selection_mode must be filter or explicit.",
                node_id=node_id,
                node_type=node_type,
            )
        )
        selection_mode = "filter"

    if selection_mode == "filter":
        dataset_filter, mount_issue = _resolve_mount_dataset_filter(
            db=db,
            study=study,
            dataset_filter=dataset_filter,
            node_id=node_id,
            node_type=node_type,
        )
        if mount_issue is not None:
            errors.append(mount_issue)

    mount_context_by_asset = _active_mount_context_by_asset(db, study)
    mounted_dataset_asset_ids = [mount.dataset_asset_id for mount in mount_context_by_asset.values()]

    if selection_mode == "explicit":
        datasets, missing_dataset_ids = _load_explicit_datasets(
            db,
            study,
            dataset_ids,
            mounted_dataset_asset_ids=mounted_dataset_asset_ids,
        )
        if not dataset_ids:
            errors.append(
                PipelineValidationIssue(
                    code="LOAD_DATA_DATASET_IDS_REQUIRED",
                    message="LoadData fixed dataset mode requires at least one dataset_id.",
                    node_id=node_id,
                    node_type=node_type,
                )
            )
        for dataset_id in missing_dataset_ids:
            errors.append(
                PipelineValidationIssue(
                    code="LOAD_DATA_DATASET_NOT_FOUND",
                    message=f"LoadData dataset_id does not exist in this study: {dataset_id}",
                    node_id=node_id,
                    node_type=node_type,
                )
            )
    else:
        datasets = _load_filter_datasets(
            db,
            study,
            dataset_filter,
            mounted_dataset_asset_ids=mounted_dataset_asset_ids,
        )

    normalized_filter = _normalize_dataset_filter(dataset_filter)
    require_fif = normalized_filter["require_fif"]
    data_infos: list[LoadDataDataInfo] = []
    for dataset in datasets:
        issue_target = errors if selection_mode == "explicit" else warnings
        if _blocked_by_status(dataset):
            issue_target.append(
                PipelineValidationIssue(
                    code="LOAD_DATA_DATASET_STATUS_BLOCKED",
                    message=f"Recording {dataset.id} has blocked qa_status: {dataset.qa_status}",
                    node_id=node_id,
                    node_type=node_type,
                    severity="error" if selection_mode == "explicit" else "warning",
                )
            )
            continue

        mount_id, mount_name = _mount_context_for_dataset(
            dataset,
            dataset_filter=dataset_filter,
            mount_context_by_asset=mount_context_by_asset,
        )
        data_info, dataset_errors, dataset_warnings = dataset_to_data_info(
            db,
            study,
            dataset,
            require_fif=require_fif,
            mount_id=mount_id,
            mount_name=mount_name,
        )
        errors.extend(
            issue.model_copy(update={"node_id": node_id, "node_type": node_type})
            for issue in dataset_errors
            if selection_mode == "explicit"
        )
        warnings.extend(
            issue.model_copy(update={"node_id": node_id, "node_type": node_type})
            for issue in dataset_warnings
        )

        if selection_mode != "explicit" and dataset_errors:
            warnings.extend(
                issue.model_copy(update={"node_id": node_id, "node_type": node_type, "severity": "warning"})
                for issue in dataset_errors
            )
            continue
        if dataset_errors:
            continue
        data_infos.append(data_info)

    if not data_infos:
        errors.append(
            PipelineValidationIssue(
                code="LOAD_DATA_NO_DATASET_MATCHED",
                message="LoadData did not resolve any runnable dataset.",
                node_id=node_id,
                node_type=node_type,
            )
        )

    return LoadDataResolveResponse(
        valid=not errors,
        study_id=study.id,
        node_id=node_id,
        selection_mode=selection_mode,
        dataset_count=len(data_infos),
        resolved_filter={
            "raw": dataset_filter,
            "normalized": normalized_filter,
        },
        data_infos=data_infos,
        errors=errors,
        warnings=warnings,
        missing_dataset_ids=missing_dataset_ids,
    )


def dataset_to_data_info(
    db: Session,
    study: Study,
    dataset: Recording,
    *,
    require_fif: bool = True,
    mount_id: Any | None = None,
    mount_name: Any | None = None,
) -> tuple[LoadDataDataInfo, list[PipelineValidationIssue], list[PipelineValidationIssue]]:
    errors: list[PipelineValidationIssue] = []
    warnings: list[PipelineValidationIssue] = []

    dataset_file = _select_dataset_file(db, study=study, dataset=dataset, require_fif=require_fif)
    source_abs_path = _resolve_storage_path(study, dataset.source_path)
    fif_abs_path = _resolve_dataset_file_path(study, dataset_file) if dataset_file else _resolve_storage_path(study, dataset.fif_path)
    source_exists = bool(source_abs_path and source_abs_path.exists())
    fif_exists = bool(fif_abs_path and fif_abs_path.exists())

    if require_fif and dataset_file is None and not dataset.fif_path:
        errors.append(
            PipelineValidationIssue(
                code="LOAD_DATA_FIF_MISSING",
                message=f"Recording {dataset.id} has no fif dataset_file or legacy fif_path. Import/convert it before using LoadData.",
            )
        )
    elif require_fif and dataset_file is None and dataset.fif_path:
        warnings.append(
            PipelineValidationIssue(
                code="LOAD_DATA_DATASET_FILE_INDEX_MISSING",
                message=f"Recording {dataset.id} falls back to legacy fif_path because fif dataset_file is missing.",
                severity="warning",
            )
        )
    if dataset_file and not fif_exists:
        errors.append(
            PipelineValidationIssue(
                code="LOAD_DATA_DATASET_FILE_MISSING",
                message=f"Recording {dataset.id} dataset_file {dataset_file.id} is recorded but missing on disk: {dataset_file.storage_uri}",
            )
        )
    elif dataset.fif_path and not fif_exists and dataset_file is None:
        errors.append(
            PipelineValidationIssue(
                code="LOAD_DATA_FIF_FILE_MISSING",
                message=f"Recording {dataset.id} fif_path is recorded but the file is missing: {dataset.fif_path}",
            )
        )
    elif not dataset_file and not dataset.fif_path and not source_exists:
        errors.append(
            PipelineValidationIssue(
                code="LOAD_DATA_SOURCE_FILE_MISSING",
                message=f"Recording {dataset.id} has no usable FIF and source_path is missing: {dataset.source_path}",
            )
        )

    if dataset.source_path and not source_exists:
        warnings.append(
            PipelineValidationIssue(
                code="LOAD_DATA_SOURCE_FILE_MISSING",
                message=f"Recording {dataset.id} source_path is missing on disk: {dataset.source_path}",
                severity="warning",
            )
        )

    subject = dataset.subject.bids_subject_id if dataset.subject else ""
    event_labels, event_counts = _read_dataset_event_labels(study, dataset)
    ch_names = _read_dataset_ch_names(fif_abs_path) if fif_exists else []
    content_hash = _content_hash(
        {
            "dataset_id": str(dataset.id),
            "dataset_asset_id": str(dataset.dataset_asset_id) if dataset.dataset_asset_id else None,
            "dataset_version_id": str(dataset_file.dataset_version_id) if dataset_file and dataset_file.dataset_version_id else None,
            "dataset_file_id": str(dataset_file.id) if dataset_file else None,
            "file_role": dataset_file.file_role if dataset_file else None,
            "storage_uri": dataset_file.storage_uri if dataset_file else None,
            "logical_path": dataset_file.logical_path if dataset_file else None,
            "sha256": dataset_file.sha256 if dataset_file else None,
            "mount_id": str(mount_id) if mount_id else None,
            "mount_name": str(mount_name) if mount_name else None,
            "checksum": dataset.checksum,
            "fif_path": dataset.fif_path,
            "file_size": dataset.file_size,
            "n_channels": dataset.n_channels,
            "sfreq": dataset.sfreq,
            "duration_seconds": dataset.duration_seconds,
            "qa_status": dataset.qa_status,
        }
    )
    data_info = LoadDataDataInfo(
        dataset_id=str(dataset.id),
        study_id=dataset.study_id,
        dataset_asset_id=str(dataset.dataset_asset_id) if dataset.dataset_asset_id else None,
        dataset_version_id=str(dataset_file.dataset_version_id) if dataset_file and dataset_file.dataset_version_id else None,
        dataset_file_id=str(dataset_file.id) if dataset_file else None,
        file_role=dataset_file.file_role if dataset_file else None,
        storage_uri=dataset_file.storage_uri if dataset_file else None,
        logical_path=dataset_file.logical_path if dataset_file else None,
        sha256=dataset_file.sha256 if dataset_file else None,
        mount_id=str(mount_id) if mount_id else None,
        mount_name=str(mount_name) if mount_name else None,
        subject_id=str(dataset.subject_id),
        subject=subject,
        bids_subject_id=subject,
        session=dataset.session,
        task=dataset.task,
        run=dataset.run,
        source_format=dataset.source_format,
        source_path=dataset.source_path,
        source_abs_path=str(source_abs_path) if source_abs_path else None,
        source_exists=source_exists,
        fif_path=dataset.fif_path,
        fif_abs_path=str(fif_abs_path) if fif_abs_path else None,
        fif_exists=fif_exists,
        current_upload_id=str(dataset.current_version_id) if dataset.current_version_id else None,
        current_upload_seq=dataset.current_version.version_seq if dataset.current_version else None,
        current_fif_dir=dataset.current_version.fif_dir if dataset.current_version else None,
        sidecar_paths=dataset.current_version.sidecar_paths if dataset.current_version else None,
        file_size=dataset.file_size,
        checksum=dataset.checksum,
        n_channels=dataset.n_channels,
        sfreq=dataset.sfreq,
        duration_seconds=dataset.duration_seconds,
        n_events=dataset.n_events,
        qa_status=dataset.qa_status,
        imported_at=dataset.imported_at,
        content_hash=content_hash,
        data_type="raw",
        event_labels=event_labels,
        event_counts=event_counts,
        ch_names=ch_names,
    )
    return data_info, errors, warnings


def _load_explicit_datasets(
    db: Session,
    study: Study,
    dataset_ids: list[Any],
    *,
    mounted_dataset_asset_ids: list[UUID] | None = None,
) -> tuple[list[Recording], list[str]]:
    requested: list[str] = []
    valid_uuids: list[UUID] = []
    for raw_id in dataset_ids:
        text = str(raw_id)
        requested.append(text)
        try:
            valid_uuids.append(UUID(text))
        except ValueError:
            continue

    if not valid_uuids:
        return [], requested

    query = (
        db.query(Recording)
        .options(joinedload(Recording.subject), joinedload(Recording.current_version))
        .filter(Recording.id.in_(valid_uuids))
    )
    if mounted_dataset_asset_ids:
        query = query.filter(
            or_(
                Recording.dataset_asset_id.in_(mounted_dataset_asset_ids),
                Recording.study_id == study.id,
            )
        )
    else:
        query = query.filter(Recording.study_id == study.id)
    datasets = query.all()
    by_id = {str(dataset.id): dataset for dataset in datasets}
    ordered = [by_id[dataset_id] for dataset_id in requested if dataset_id in by_id]
    missing = [dataset_id for dataset_id in requested if dataset_id not in by_id]
    return ordered, missing


def _load_filter_datasets(
    db: Session,
    study: Study,
    dataset_filter: dict[str, Any],
    *,
    mounted_dataset_asset_ids: list[UUID] | None = None,
) -> list[Recording]:
    filters = _normalize_dataset_filter(dataset_filter)
    explicit_asset_ids = _uuid_filter_values(filters["dataset_asset_ids"])
    query = (
        db.query(Recording)
        .options(joinedload(Recording.subject), joinedload(Recording.current_version))
    )
    if explicit_asset_ids:
        query = query.filter(Recording.dataset_asset_id.in_(explicit_asset_ids))
    elif mounted_dataset_asset_ids:
        query = query.filter(
            or_(
                Recording.dataset_asset_id.in_(mounted_dataset_asset_ids),
                Recording.study_id == study.id,
            )
        )
    else:
        query = query.filter(Recording.study_id == study.id)
    datasets = query.order_by(Recording.imported_at.desc(), Recording.id.desc()).all()
    matched = [
        dataset
        for dataset in datasets
        if _matches(filters["subjects"], dataset.subject.bids_subject_id if dataset.subject else None)
        and _matches(filters["sessions"], dataset.session)
        and _matches(filters["tasks"], dataset.task)
        and _matches(filters["runs"], dataset.run)
        and _matches(filters["qa_status"], dataset.qa_status)
        and _matches(filters["dataset_asset_ids"], str(dataset.dataset_asset_id) if dataset.dataset_asset_id else None)
    ]
    return sorted(
        matched,
        key=lambda item: (
            item.subject.bids_subject_id if item.subject else "",
            item.session or "",
            item.task or "",
            item.run or "",
            item.imported_at or datetime.min,
        ),
    )


def _apply_study_default_dataset_filter(
    *,
    db: Session,
    study: Study,
    dataset_filter: dict[str, Any],
) -> dict[str, Any]:
    if dataset_filter:
        # Explicit LoadData params win over Study defaults.
        explicit_filter = dataset_filter
    else:
        explicit_filter = {}
    settings = getattr(study, "study_settings", None)
    if settings is None:
        settings = db.query(StudySettings).filter(StudySettings.study_id == study.id).first()
    default_filter = settings.default_dataset_filter if settings and isinstance(settings.default_dataset_filter, dict) else {}
    return {**default_filter, **explicit_filter}


def _resolve_mount_dataset_filter(
    *,
    db: Session,
    study: Study,
    dataset_filter: dict[str, Any],
    node_id: str | None,
    node_type: str,
) -> tuple[dict[str, Any], PipelineValidationIssue | None]:
    mount_id = dataset_filter.get("mount_id")
    mount_name = dataset_filter.get("mount_name")
    requested_asset_ids, asset_issue = _dataset_asset_ids_from_filter(
        dataset_filter,
        node_id=node_id,
        node_type=node_type,
    )
    if asset_issue is not None:
        return dataset_filter, asset_issue
    if not mount_id and not mount_name and not requested_asset_ids:
        return dataset_filter, None

    if mount_id or mount_name:
        query = db.query(StudyDatasetMount).filter(
            StudyDatasetMount.study_id == study.id,
            StudyDatasetMount.is_active.is_(True),
        )
        if mount_id:
            try:
                query = query.filter(StudyDatasetMount.id == UUID(str(mount_id)))
            except ValueError:
                return dataset_filter, PipelineValidationIssue(
                    code="LOAD_DATA_MOUNT_ID_INVALID",
                    message=f"LoadData mount_id is not a valid UUID: {mount_id}",
                    node_id=node_id,
                    node_type=node_type,
                )
        elif mount_name:
            query = query.filter(StudyDatasetMount.mount_name == str(mount_name))

        mount = query.first()
        if mount is None:
            return dataset_filter, PipelineValidationIssue(
                code="LOAD_DATA_MOUNT_NOT_FOUND",
                message="LoadData referenced an inactive or missing Study Dataset Mount.",
                node_id=node_id,
                node_type=node_type,
            )
        if requested_asset_ids and mount.dataset_asset_id not in requested_asset_ids:
            return dataset_filter, PipelineValidationIssue(
                code="LOAD_DATA_MOUNT_DATASET_ASSET_MISMATCH",
                message="LoadData mount and dataset_asset_id point to different Dataset Assets.",
                node_id=node_id,
                node_type=node_type,
            )

        mount_selection = mount.selection_json or {}
        if isinstance(mount_selection.get("dataset_filter"), dict):
            mount_filter = mount_selection["dataset_filter"]
        else:
            mount_filter = mount_selection

        merged = {
            **mount_filter,
            **{key: value for key, value in dataset_filter.items() if key not in {"mount_id", "mount_name"}},
            "dataset_asset_id": str(mount.dataset_asset_id),
            "mount_id": str(mount.id),
            "mount_name": mount.mount_name,
        }
        return merged, None

    mount_context_by_asset = _active_mount_context_by_asset(db, study)
    missing = [str(asset_id) for asset_id in requested_asset_ids if str(asset_id) not in mount_context_by_asset]
    if missing:
        return dataset_filter, PipelineValidationIssue(
            code="LOAD_DATA_DATASET_ASSET_NOT_MOUNTED",
            message=f"LoadData dataset_asset_id is not active-mounted in this Study: {', '.join(missing)}",
            node_id=node_id,
            node_type=node_type,
        )

    merged = dict(dataset_filter)
    if len(requested_asset_ids) == 1:
        asset_id = requested_asset_ids[0]
        mount = mount_context_by_asset[str(asset_id)]
        merged["dataset_asset_id"] = str(asset_id)
        merged["mount_id"] = str(mount.id)
        merged["mount_name"] = mount.mount_name
    else:
        merged["dataset_asset_ids"] = [str(asset_id) for asset_id in requested_asset_ids]
    return merged, None


def _normalize_dataset_filter(dataset_filter: dict[str, Any]) -> dict[str, Any]:
    dataset_asset_ids = dataset_filter.get("dataset_asset_ids")
    if dataset_asset_ids is None:
        dataset_asset_ids = dataset_filter.get("dataset_asset_id", "all")
    return {
        "subjects": _normalize_filter_value(dataset_filter.get("subjects", "all")),
        "sessions": _normalize_filter_value(dataset_filter.get("sessions", "all")),
        "tasks": _normalize_filter_value(dataset_filter.get("tasks", "all")),
        "runs": _normalize_filter_value(dataset_filter.get("runs", "all")),
        "qa_status": _normalize_filter_value(dataset_filter.get("qa_status", DEFAULT_QA_STATUS)),
        "dataset_asset_ids": _normalize_filter_value(dataset_asset_ids),
        "require_fif": dataset_filter.get("require_fif") is not False,
    }


def _normalize_filter_value(value: Any) -> list[Any] | str:
    if value in (None, "", "all"):
        return "all"
    if isinstance(value, list):
        return value or "all"
    return [value]


def _uuid_filter_values(filter_value: list[Any] | str) -> list[UUID]:
    if filter_value == "all":
        return []
    values: list[UUID] = []
    for item in filter_value:
        try:
            values.append(UUID(str(item)))
        except (TypeError, ValueError):
            continue
    return values


def _dataset_asset_ids_from_filter(
    dataset_filter: dict[str, Any],
    *,
    node_id: str | None,
    node_type: str,
) -> tuple[list[UUID], PipelineValidationIssue | None]:
    raw_asset_ids = dataset_filter.get("dataset_asset_ids")
    if raw_asset_ids is None:
        raw_asset_ids = dataset_filter.get("dataset_asset_id")
    normalized = _normalize_filter_value(raw_asset_ids)
    if normalized == "all":
        return [], None
    asset_ids: list[UUID] = []
    for item in normalized:
        try:
            asset_ids.append(UUID(str(item)))
        except (TypeError, ValueError):
            return [], PipelineValidationIssue(
                code="LOAD_DATA_DATASET_ASSET_ID_INVALID",
                message=f"LoadData dataset_asset_id is not a valid UUID: {item}",
                node_id=node_id,
                node_type=node_type,
            )
    return asset_ids, None


def _active_mount_context_by_asset(db: Session, study: Study) -> dict[str, StudyDatasetMount]:
    mounts = (
        db.query(StudyDatasetMount)
        .filter(
            StudyDatasetMount.study_id == study.id,
            StudyDatasetMount.is_active.is_(True),
        )
        .order_by(StudyDatasetMount.mounted_at.desc(), StudyDatasetMount.id.desc())
        .all()
    )
    context: dict[str, StudyDatasetMount] = {}
    for mount in mounts:
        dataset_asset_id = getattr(mount, "dataset_asset_id", None)
        if dataset_asset_id:
            context.setdefault(str(dataset_asset_id), mount)
    return context


def _mount_context_for_dataset(
    dataset: Recording,
    *,
    dataset_filter: dict[str, Any],
    mount_context_by_asset: dict[str, StudyDatasetMount],
) -> tuple[Any | None, Any | None]:
    if dataset_filter.get("mount_id") or dataset_filter.get("mount_name"):
        return dataset_filter.get("mount_id"), dataset_filter.get("mount_name")
    dataset_asset_id = getattr(dataset, "dataset_asset_id", None)
    mount = mount_context_by_asset.get(str(dataset_asset_id)) if dataset_asset_id else None
    if mount is None:
        return None, None
    return mount.id, mount.mount_name


def _matches(filter_value: list[Any] | str, actual: Any) -> bool:
    if filter_value == "all":
        return True
    normalized_actual = str(actual) if actual not in ("", None) else None
    return any((str(item) if item not in ("", None) else None) == normalized_actual for item in filter_value)


def _blocked_by_status(dataset: Recording) -> bool:
    return str(dataset.qa_status or "").lower() in BLOCKED_QA_STATUS


def _select_dataset_file(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    require_fif: bool,
) -> DatasetFile | None:
    roles = (CANONICAL_LOAD_FILE_ROLE,) if require_fif else (CANONICAL_LOAD_FILE_ROLE, *SOURCE_LOAD_FILE_ROLES)
    for role in roles:
        found = _latest_dataset_file(db, study=study, dataset=dataset, file_role=role, current_upload_only=True)
        if found is not None:
            return found
    for role in roles:
        found = _latest_dataset_file(db, study=study, dataset=dataset, file_role=role, current_upload_only=False)
        if found is not None:
            return found
    return None


def _latest_dataset_file(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    file_role: str,
    current_upload_only: bool,
) -> DatasetFile | None:
    query = db.query(DatasetFile).filter(
        DatasetFile.recording_id == dataset.id,
        DatasetFile.file_role == file_role,
    )
    current_version_id = getattr(dataset, "current_version_id", None)
    if current_upload_only:
        if not current_version_id:
            return None
        query = query.filter(DatasetFile.recording_version_id == current_version_id)
    return query.order_by(DatasetFile.created_at.desc(), DatasetFile.id.desc()).first()


def _resolve_dataset_file_path(study: Study, dataset_file: DatasetFile | None) -> Path | None:
    if dataset_file is None:
        return None
    return _resolve_storage_path(study, dataset_file.storage_uri or dataset_file.relative_path)


def _resolve_storage_path(study: Study, path_value: str | None) -> Path | None:
    if not path_value:
        return None
    try:
        return StorageService().resolve_path(
            path_value,
            study_id=study.id,
            study_root=study.data_root,
        )
    except (StorageUriError, ValueError):
        raw = Path(path_value)
        if raw.is_absolute():
            return raw
        return (Path(study.data_root) / path_value).resolve()


def _content_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
