"""
Purpose: FastAPI sub-router for recording (采集记录) endpoints under
/api/v1/studies/{study_id}/recordings — list / versions / files / QA (get,
mock-run, review) / import-task / import-async / import. Import endpoints delegate
the heavy lifting to app.routers.dataset_imports.
Related: app/routers/_dataset_shared.py, app/routers/dataset_imports.py,
app/schemas/*, docs_v2/2-50.

Split out of the former routers/datasets.py (god-router) — see wiki 9-0x.
"""

from datetime import datetime
from pathlib import Path
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    AuditEvent,
    DatasetFile,
    Recording,
    Study,
    User,
)
from app.routers.auth import get_current_user
from app.schemas.dataset import (
    DATASET_QA_MODE_MOCK,
    DatasetImportTaskRequest,
    DatasetQaHumanReview,
    DatasetQaMockRunResponse,
    DatasetQaReport,
    DatasetQaResponse,
    DatasetQaReviewRequest,
    DatasetQaReviewResponse,
    DatasetQaSummary,
    DatasetFileListResponse,
    RecordingListResponse,
    RecordingRelabelRequest,
    RecordingResponse,
    RecordingUploadResponse,
    RecordingVersionListResponse,
)
from app.schemas.pipeline import AsyncTaskResponse
from app.services.dataset_qa import build_mock_qa_report
from app.services.dataset_assets import can_write_dataset_asset, get_dataset_asset_for_user
from app.services.study_access import require_study_read, require_study_write
from app.services.recordings import (
    get_recording_for_study,
    list_recording_versions_for_study,
    list_recordings_for_study,
)
from app.routers._dataset_shared import (
    require_system_permission,
    recording_to_response,
    recording_version_to_response,
    dataset_file_to_response,
    create_and_dispatch_file_task,
    resolve_dataset_asset_filter,
    active_study_dataset_asset_ids,
)
from app.routers.dataset_imports import (
    archive_uploads,
    materialize_recording_import,
    parse_bids_entities_from_filename,
    relabel_recording,
    write_manifest,
    _build_import_context,
)

recording_router = APIRouter(prefix="/api/v1/studies/{study_id}/recordings", tags=["recordings"])


def dataset_qa_to_response(dataset: Recording) -> DatasetQaResponse:
    raw_report = dataset.qa_report
    has_report = bool(raw_report)
    qa_report = None

    if isinstance(raw_report, dict) and raw_report:
        try:
            qa_report = DatasetQaReport.model_validate(raw_report)
        except ValidationError:
            qa_report = DatasetQaReport(
                summary=DatasetQaSummary(
                    mock_qc_status="unparsed",
                    level="warning",
                    score=None,
                    warnings=["Stored qa_report does not match the current v1 schema."],
                )
            )

    return DatasetQaResponse(
        dataset_id=str(dataset.id),
        study_id=dataset.study_id,
        qa_status=dataset.qa_status,
        qa_report=qa_report,
        has_report=has_report,
        current_upload_id=str(dataset.current_version_id) if dataset.current_version_id else None,
        imported_at=dataset.imported_at,
    )


def validate_mock_qa_report_payload(report: dict[str, Any]) -> DatasetQaReport:
    try:
        qa_report = DatasetQaReport.model_validate(report)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"模拟质控报告结构无效: {exc}",
        ) from exc

    signal_placeholder = next(
        (stage for stage in qa_report.stages if stage.key == "signal_placeholder"),
        None,
    )
    if (
        qa_report.mode != DATASET_QA_MODE_MOCK
        or qa_report.summary.score is not None
        or signal_placeholder is None
        or signal_placeholder.status != "not_computed"
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="模拟质控报告未满足 mock 模式约定",
        )
    return qa_report


def apply_mock_qa_status(dataset: Recording, qa_report: DatasetQaReport) -> None:
    if qa_report.summary.blocking_issues:
        dataset.qa_status = "failed"


def actor_id_text(user: User) -> str | None:
    actor_id = getattr(user, "id", None)
    return str(actor_id) if actor_id else None


def study_snapshot(study: Study) -> dict[str, Any]:
    to_dict = getattr(study, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return {"id": getattr(study, "id", None)}


def add_qa_report_history(
    qa_report: DatasetQaReport,
    *,
    action: str,
    actor: User,
    occurred_at: datetime,
    status_value: str | None,
) -> None:
    qa_report.history.append(
        {
            "action": action,
            "actor_id": actor_id_text(actor),
            "at": f"{occurred_at.isoformat()}Z",
            "status": status_value,
        }
    )


def add_dataset_qa_audit_event(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    action: str,
    actor: User,
    occurred_at: datetime,
    old_qa_status: str | None,
    new_qa_status: str | None,
    qa_report: DatasetQaReport,
    conclusion: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            study_id=study.id,
            event_scope="study",
            action=action,
            actor_id=getattr(actor, "id", None),
            resource_kind="dataset",
            resource_id=str(dataset.id),
            resource_label=getattr(dataset, "name", None) or str(dataset.id),
            occurred_at=occurred_at,
            snapshot=study_snapshot(study),
            metadata_json={
                "dataset_id": str(dataset.id),
                "current_upload_id": str(dataset.current_version_id) if dataset.current_version_id else None,
                "old_qa_status": old_qa_status,
                "new_qa_status": new_qa_status,
                "conclusion": conclusion,
                "has_blocking_issues": bool(qa_report.summary.blocking_issues),
            },
        )
    )


def record_dataset_qa_action(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    qa_report: DatasetQaReport,
    action: str,
    actor: User,
    occurred_at: datetime,
    old_qa_status: str | None,
    conclusion: str | None = None,
) -> None:
    new_qa_status = dataset.qa_status
    add_qa_report_history(
        qa_report,
        action=action,
        actor=actor,
        occurred_at=occurred_at,
        status_value=new_qa_status,
    )
    dataset.qa_report = qa_report.model_dump(mode="json")
    add_dataset_qa_audit_event(
        db,
        study=study,
        dataset=dataset,
        action=action,
        actor=actor,
        occurred_at=occurred_at,
        old_qa_status=old_qa_status,
        new_qa_status=new_qa_status,
        qa_report=qa_report,
        conclusion=conclusion,
    )


def require_existing_qa_report(dataset: Recording) -> DatasetQaReport:
    raw_report = dataset.qa_report
    if not isinstance(raw_report, dict) or not raw_report:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先生成模拟质控报告")
    try:
        return DatasetQaReport.model_validate(raw_report)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"已有质控报告结构无效: {exc}") from exc


def apply_dataset_qa_review(
    dataset: Recording,
    qa_report: DatasetQaReport,
    review: DatasetQaReviewRequest,
    current_user: User,
) -> DatasetQaReport:
    if review.conclusion == "accept":
        if qa_report.summary.blocking_issues:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="存在阻塞问题，不能人工确认通过")
        dataset.qa_status = "checked"
    elif review.conclusion == "reject":
        dataset.qa_status = "rejected"
    elif review.conclusion == "hold" and dataset.qa_status not in {"failed", "rejected"}:
        dataset.qa_status = "converted"

    qa_report.human_review = DatasetQaHumanReview(
        conclusion=review.conclusion,
        notes=review.notes,
        reviewed_by=str(current_user.id) if getattr(current_user, "id", None) else None,
        reviewed_at=datetime.utcnow(),
    )
    dataset.qa_report = qa_report.model_dump(mode="json")
    return qa_report


@recording_router.get("", response_model=RecordingListResponse)
def list_recordings(
    study_id: str,
    dataset_asset_id: uuid.UUID | None = None,
    mount_id: uuid.UUID | None = None,
    mount_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看采集记录权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    has_asset_filter = dataset_asset_id is not None or mount_id is not None or mount_name is not None
    resolved_asset_id = resolve_dataset_asset_filter(
        db,
        study=study,
        dataset_asset_id=dataset_asset_id,
        mount_id=mount_id,
        mount_name=mount_name,
    )
    recordings = list_recordings_for_study(
        db,
        study=study,
        dataset_asset_id=resolved_asset_id,
        mounted_dataset_asset_ids=None if has_asset_filter else active_study_dataset_asset_ids(db, study=study),
    )
    return RecordingListResponse(recordings=[recording_to_response(recording) for recording in recordings])


@recording_router.get("/{recording_id}/versions", response_model=RecordingVersionListResponse)
def list_recording_versions(
    study_id: str,
    recording_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看采集版本权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    recording = get_recording_for_study(db, study=study, recording_id=recording_id)
    if recording is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")
    versions = list_recording_versions_for_study(db, study=study, recording_id=recording_id)
    return RecordingVersionListResponse(
        versions=[recording_version_to_response(version, study_id=study.id) for version in versions],
    )


@recording_router.get("/{recording_id}/files", response_model=DatasetFileListResponse)
def list_recording_files(
    study_id: str,
    recording_id: uuid.UUID,
    file_role: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看采集文件权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    recording = get_recording_for_study(db, study=study, recording_id=recording_id)
    if recording is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")
    query = db.query(DatasetFile).filter(DatasetFile.study_id == study.id, DatasetFile.recording_id == recording_id)
    if file_role:
        query = query.filter(DatasetFile.file_role == file_role)
    files = query.order_by(DatasetFile.created_at.desc(), DatasetFile.id.desc()).all()
    return DatasetFileListResponse(files=[dataset_file_to_response(item) for item in files])


@recording_router.patch("/{recording_id}", response_model=RecordingResponse)
def relabel_recording_endpoint(
    study_id: str,
    recording_id: uuid.UUID,
    payload: RecordingRelabelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 「调整归类」：改一条采集记录的 BIDS 实体并物理重排派生层（原始上传不碰）。
    require_system_permission(current_user, "data:write", "当前用户没有修改采集记录权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    recording = get_recording_for_study(db, study=study, recording_id=recording_id)
    if recording is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")
    try:
        relabel_recording(
            db,
            study=study,
            recording=recording,
            subject=payload.subject,
            session=payload.session,
            task=payload.task,
            run=payload.run,
            current_user=current_user,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(recording)
    return recording_to_response(recording)


@recording_router.post("/import-task", response_model=AsyncTaskResponse, status_code=status.HTTP_201_CREATED)
def create_recording_import_task(
    study_id: str,
    payload: DatasetImportTaskRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有创建导入任务权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    payload = payload or DatasetImportTaskRequest()
    asset = None
    if payload.dataset_asset_id:
        asset = get_dataset_asset_for_user(db, asset_id=payload.dataset_asset_id, user=current_user)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
        if not can_write_dataset_asset(current_user, asset):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权写入该 Dataset 资产")
    payload_json = {
        "study_id": study.id,
        "dataset_asset_id": str(payload.dataset_asset_id) if payload.dataset_asset_id else None,
        "staged_upload_uri": payload.staged_upload_uri,
        "metadata_json": payload.metadata_json,
        "mode": "async_dataset_import",
        "sync_upload_endpoint": f"/api/v1/studies/{study.id}/recordings/import",
    }
    return create_and_dispatch_file_task(
        db,
        task_type="dataset_import",
        study_id=study.id,
        resource_kind="dataset_asset" if asset else "study",
        resource_id=asset.id if asset else None,
        payload_json=payload_json,
        current_user=current_user,
    )


@recording_router.get("/{recording_id}/qa", response_model=DatasetQaResponse)
def get_recording_qa_report(
    study_id: str,
    recording_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看数据权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    dataset = (
        db.query(Recording)
        .options(joinedload(Recording.subject), joinedload(Recording.current_version))
        .filter(Recording.study_id == study.id, Recording.id == recording_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")

    return dataset_qa_to_response(dataset)


@recording_router.post("/{recording_id}/qa/mock-run", response_model=DatasetQaMockRunResponse)
def run_recording_mock_qa_report(
    study_id: str,
    recording_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有写入数据权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    dataset = (
        db.query(Recording)
        .options(joinedload(Recording.subject), joinedload(Recording.current_version))
        .filter(Recording.study_id == study.id, Recording.id == recording_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")

    old_qa_status = dataset.qa_status
    qa_report = validate_mock_qa_report_payload(build_mock_qa_report(study, dataset))
    apply_mock_qa_status(dataset, qa_report)
    record_dataset_qa_action(
        db,
        study=study,
        dataset=dataset,
        qa_report=qa_report,
        action="dataset.qa.mock_run",
        actor=current_user,
        occurred_at=datetime.utcnow(),
        old_qa_status=old_qa_status,
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(dataset)

    return DatasetQaMockRunResponse(
        dataset_id=str(dataset.id),
        study_id=dataset.study_id,
        qa_status=dataset.qa_status,
        qa_report=qa_report,
    )


@recording_router.post("/{recording_id}/qa/review", response_model=DatasetQaReviewResponse)
def review_recording_qa_report(
    study_id: str,
    recording_id: uuid.UUID,
    review: DatasetQaReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有写入数据权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    dataset = (
        db.query(Recording)
        .options(joinedload(Recording.subject), joinedload(Recording.current_version))
        .filter(Recording.study_id == study.id, Recording.id == recording_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")

    old_qa_status = dataset.qa_status
    qa_report = require_existing_qa_report(dataset)
    qa_report = apply_dataset_qa_review(
        dataset=dataset,
        qa_report=qa_report,
        review=review,
        current_user=current_user,
    )
    record_dataset_qa_action(
        db,
        study=study,
        dataset=dataset,
        qa_report=qa_report,
        action="dataset.qa.review",
        actor=current_user,
        occurred_at=datetime.utcnow(),
        old_qa_status=old_qa_status,
        conclusion=review.conclusion,
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(dataset)

    return DatasetQaReviewResponse(
        dataset_id=str(dataset.id),
        study_id=dataset.study_id,
        qa_status=dataset.qa_status,
        qa_report=qa_report,
    )


@recording_router.post("/import-async", response_model=AsyncTaskResponse, status_code=status.HTTP_201_CREATED)
async def import_recording_async(
    study_id: str,
    subject: str = Form(...),
    task: str = Form(...),
    session: str | None = Form(None),
    run: str | None = Form(None),
    replace_existing: bool = Form(False),
    dataset_asset_id: uuid.UUID | None = Form(None),
    mount_name: str | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """异步导入：请求内只把文件落盘后**立即返回 task_id**，转 FIF 的重活交给 Celery worker。
    客户端拿 task_id 轮询 GET /studies/{study_id}/tasks/{task_id} 看进度/状态。
    权限、重复 409 等能快速判定的校验仍在请求内同步做掉，让客户端立刻拿到 409。"""
    ctx = _build_import_context(
        db,
        study_id=study_id,
        current_user=current_user,
        subject=subject,
        task=task,
        session=session,
        run=run,
        replace_existing=replace_existing,
        dataset_asset_id=dataset_asset_id,
        mount_name=mount_name,
        files=files,
    )
    study = ctx["study"]
    job_dir = ctx["job_dir"]
    archived = await archive_uploads(ctx["items_by_extension"], job_dir, files_subdir=None)

    payload_json = {
        "mode": "async_dataset_import",
        "study_id": study.id,
        "importer_user_id": str(current_user.id),
        "dataset_asset_id": str(ctx["target_asset"].id),
        "dataset_version_id": str(ctx["target_version"].id),
        "duplicate_recording_id": str(ctx["duplicate"].id) if ctx["duplicate"] else None,
        "subject_record_id": str(ctx["subject_record"].id) if ctx["subject_record"] else None,
        "bids_subject_id": ctx["bids_subject_id"],
        "session_label": ctx["session_label"],
        "task_label": ctx["task_label"],
        "run_label": ctx["run_label"],
        "upload_kind": ctx["upload_kind"],
        "upload_seq": ctx["upload_seq"],
        "job_id": ctx["job_id"],
        "job_dir": str(job_dir),
        "archived": {ext: str(path) for ext, path in archived.items()},
        "replace_existing": replace_existing,
    }
    return create_and_dispatch_file_task(
        db,
        task_type="dataset_import",
        study_id=study.id,
        resource_kind="dataset_asset",
        resource_id=ctx["target_asset"].id,
        payload_json=payload_json,
        current_user=current_user,
    )


class _BatchImportItem(BaseModel):
    filename: str
    task_id: str | None = None
    status: str      # "submitted" | "skipped" | "error"
    message: str = ""


class _BatchImportResponse(BaseModel):
    results: list[_BatchImportItem]
    n_submitted: int
    n_skipped: int
    n_error: int


@recording_router.post("/import-batch-async", response_model=_BatchImportResponse, status_code=status.HTTP_201_CREATED)
async def import_recordings_batch_async(
    study_id: str,
    files: list[UploadFile] = File(...),
    dataset_asset_id: uuid.UUID | None = Form(None),
    mount_name: str | None = Form(None),
    session: str | None = Form(None),
    run: str | None = Form(None),
    replace_existing: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量异步导入：多个文件一次请求，从文件名自动解析 BIDS 元信息（sub-/task-）。

    文件名须符合 BIDS 命名：sub-{subject}_task-{task}_eeg.edf
    每个文件独立创建一个 Celery 任务；已存在文件（409）标记为 skipped 而不报错。
    返回 {results, n_submitted, n_skipped, n_error}，客户端按 task_id 轮询各自进度。
    """
    results: list[_BatchImportItem] = []

    for file in files:
        fname = file.filename or ""
        entities = parse_bids_entities_from_filename(fname)
        subject = entities.get("sub", "")
        task_label = entities.get("task", "")

        if not subject or not task_label:
            results.append(_BatchImportItem(
                filename=fname,
                status="error",
                message=f"无法从文件名解析 sub/task 实体，跳过（期望格式：sub-XXX_task-YYY_eeg.edf）",
            ))
            continue

        try:
            ctx = _build_import_context(
                db,
                study_id=study_id,
                current_user=current_user,
                subject=subject,
                task=task_label,
                session=session,
                run=run,
                replace_existing=replace_existing,
                dataset_asset_id=dataset_asset_id,
                mount_name=mount_name,
                files=[file],
            )
        except HTTPException as exc:
            if exc.status_code == 409:
                results.append(_BatchImportItem(filename=fname, status="skipped", message="已存在（幂等跳过）"))
                continue
            results.append(_BatchImportItem(filename=fname, status="error", message=str(exc.detail)))
            continue

        job_dir = ctx["job_dir"]
        archived = await archive_uploads(ctx["items_by_extension"], job_dir, files_subdir=None)

        payload_json = {
            "mode": "async_dataset_import",
            "study_id": ctx["study"].id,
            "importer_user_id": str(current_user.id),
            "dataset_asset_id": str(ctx["target_asset"].id),
            "dataset_version_id": str(ctx["target_version"].id),
            "duplicate_recording_id": str(ctx["duplicate"].id) if ctx["duplicate"] else None,
            "subject_record_id": str(ctx["subject_record"].id) if ctx["subject_record"] else None,
            "bids_subject_id": ctx["bids_subject_id"],
            "session_label": ctx["session_label"],
            "task_label": ctx["task_label"],
            "run_label": ctx["run_label"],
            "upload_kind": ctx["upload_kind"],
            "upload_seq": ctx["upload_seq"],
            "job_id": ctx["job_id"],
            "job_dir": str(job_dir),
            "archived": {ext: str(path) for ext, path in archived.items()},
            "replace_existing": replace_existing,
        }
        task_resp = create_and_dispatch_file_task(
            db,
            task_type="dataset_import",
            study_id=ctx["study"].id,
            resource_kind="dataset_asset",
            resource_id=ctx["target_asset"].id,
            payload_json=payload_json,
            current_user=current_user,
        )
        results.append(_BatchImportItem(filename=fname, task_id=task_resp.id, status="submitted"))

    n_submitted = sum(1 for r in results if r.status == "submitted")
    n_skipped   = sum(1 for r in results if r.status == "skipped")
    n_error     = sum(1 for r in results if r.status == "error")
    return _BatchImportResponse(results=results, n_submitted=n_submitted, n_skipped=n_skipped, n_error=n_error)


@recording_router.post("/import", response_model=RecordingUploadResponse, status_code=status.HTTP_201_CREATED)
async def import_recording(
    study_id: str,
    subject: str = Form(...),
    task: str = Form(...),
    session: str | None = Form(None),
    run: str | None = Form(None),
    replace_existing: bool = Form(False),
    dataset_asset_id: uuid.UUID | None = Form(None),
    mount_name: str | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = _build_import_context(
        db,
        study_id=study_id,
        current_user=current_user,
        subject=subject,
        task=task,
        session=session,
        run=run,
        replace_existing=replace_existing,
        dataset_asset_id=dataset_asset_id,
        mount_name=mount_name,
        files=files,
    )
    study = ctx["study"]
    duplicate = ctx["duplicate"]
    upload_seq = ctx["upload_seq"]
    job_dir = ctx["job_dir"]
    manifest = ctx["manifest"]

    archived: dict[str, Path] = {}
    try:
        archived = await archive_uploads(ctx["items_by_extension"], job_dir, files_subdir=None)
        dataset = materialize_recording_import(
            db,
            study=study,
            current_user=current_user,
            target_asset=ctx["target_asset"],
            target_version=ctx["target_version"],
            target_mount=ctx["target_mount"],
            duplicate=duplicate,
            subject_record=ctx["subject_record"],
            bids_subject_id=ctx["bids_subject_id"],
            session_label=ctx["session_label"],
            task_label=ctx["task_label"],
            run_label=ctx["run_label"],
            upload_kind=ctx["upload_kind"],
            upload_seq=upload_seq,
            job_id=ctx["job_id"],
            job_dir=job_dir,
            archived=archived,
            manifest=manifest,
            temp_root=ctx["temp_root"],
        )
        return RecordingUploadResponse(
            message=(
                f"已新增 upload-{upload_seq:03d}，并切换为当前工作版本"
                if duplicate
                else "原始文件已归档到 Dataset 存储，canonical FIF 已生成并写入 derivatives"
            ),
            recording=recording_to_response(dataset),
        )
    except HTTPException as exc:
        db.rollback()
        next_status = "duplicate" if manifest.get("status") == "duplicate" else "failed"
        manifest.update(
            {
                "status": next_status,
                "error": exc.detail,
                "updatedAt": datetime.utcnow().isoformat() + "Z",
            }
        )
        write_manifest(job_dir, manifest)
        raise
    except Exception as exc:
        db.rollback()
        manifest.update({"status": "failed", "error": str(exc), "updatedAt": datetime.utcnow().isoformat() + "Z"})
        write_manifest(job_dir, manifest)
        raise HTTPException(status_code=500, detail=f"数据导入失败: {exc}") from exc
