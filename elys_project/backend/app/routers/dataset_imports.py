"""
Purpose: Import implementation library for the datasets area — pure functions only
(no APIRouter, no endpoints). Upload classification, BIDS/FIF path building,
checksum + sidecar writers, DatasetFile/RecordingVersion record builders, the MNE
canonical-FIF generator, and the import "heavy core" (materialize_recording_import)
+ request-stage context builder (_build_import_context).
Related: app/routers/dataset_recordings.py, app/tasks/file_tasks.py,
app/routers/_dataset_shared.py, docs_v2/2-50.

Split out of the former routers/datasets.py (god-router) — see wiki 9-0x.
"""

from datetime import datetime
from pathlib import Path, PurePosixPath
import hashlib
import json
import shutil
import tempfile
import uuid
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    DatasetAsset,
    DatasetFile,
    DatasetFileDerivation,
    DatasetVersion,
    Study,
    Recording,
    RecordingVersion,
    StudyDatasetMount,
    Subject,
    User,
)
from app.services.audit_events import record_audit_event
from app.services.study_access import require_study_write
from app.routers._dataset_shared import (
    STANDARD_SINGLE_EXTENSIONS,
    BRAINVISION_EXTENSIONS,
    REJECTED_EXTENSIONS,
    ADVANCED_EXTENSIONS,
    WORKING_DATASET_VERSION_LABEL,
    DATASET_ORIGINAL_UPLOADS_PREFIX,
    DATASET_CANONICAL_FIF_PREFIX,
    UploadItem,
    require_system_permission,
    normalize_bids_label,
    resolve_upload_dataset_asset,
)

settings = get_settings()


def get_or_create_subject(db: Session, study: Study, bids_subject_id: str) -> Subject:
    """找/建被试，**并发安全**：批量导入时同一被试的多条 recording（如 eo+ec）会被
    不同 Celery worker 同时处理，朴素的 SELECT→INSERT 会双双 SELECT 到空、双双 INSERT，
    第二个撞 (study_id, bids_subject_id) 唯一键炸库并污染整条事务。

    解法：INSERT 包在 SAVEPOINT(begin_nested) 里——撞键时只回滚这个 savepoint，外层事务
    存活；随后重查拿到竞争对手刚提交的那行（READ COMMITTED 下可见）。
    """
    def _query() -> Subject | None:
        return (
            db.query(Subject)
            .filter(Subject.study_id == study.id, Subject.bids_subject_id == bids_subject_id)
            .first()
        )

    subject = _query()
    if subject:
        return subject

    try:
        with db.begin_nested():
            subject = Subject(study_id=study.id, bids_subject_id=bids_subject_id, extra={})
            db.add(subject)
            db.flush()
        return subject
    except IntegrityError:
        # 输给了并发的兄弟任务——它已建好该被试，重查复用即可。
        existing = _query()
        if existing is None:
            raise
        return existing


def safe_upload_relative_path(filename: str | None) -> Path:
    raw = (filename or "upload").replace("\\", "/")
    parts: list[str] = []
    for part in PurePosixPath(raw).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise HTTPException(status_code=422, detail="上传文件名不能包含上级目录 ..")
        cleaned = "".join(ch for ch in part.strip().replace("\x00", "") if ch not in '<>:"|?*')
        if cleaned:
            parts.append(cleaned)
    if not parts:
        raise HTTPException(status_code=422, detail="上传文件名无效")
    return Path(*parts)


def classify_uploads(files: list[UploadFile]) -> tuple[str, dict[str, UploadItem]]:
    if not files:
        raise HTTPException(status_code=422, detail="请选择要上传的数据文件")

    items_by_extension: dict[str, UploadItem] = {}
    stems: set[str] = set()
    parent_paths: set[str] = set()

    for upload in files:
        relative_path = safe_upload_relative_path(upload.filename)
        extension = relative_path.suffix.lower()
        filename = relative_path.name

        if filename.lower().endswith(".nii.gz"):
            raise HTTPException(status_code=422, detail="暂不接受 NIfTI/MRI 数据，本阶段只导入 EEG 原始数据。")
        if extension in REJECTED_EXTENSIONS:
            raise HTTPException(status_code=422, detail=REJECTED_EXTENSIONS[extension])
        if extension in ADVANCED_EXTENSIONS:
            raise HTTPException(status_code=422, detail=ADVANCED_EXTENSIONS[extension])
        if extension not in BRAINVISION_EXTENSIONS and extension not in STANDARD_SINGLE_EXTENSIONS:
            raise HTTPException(status_code=422, detail=f"不支持的文件类型: {filename}")
        if extension in items_by_extension:
            raise HTTPException(status_code=422, detail=f"同一次导入不能包含多个 {extension} 文件")

        items_by_extension[extension] = UploadItem(upload, relative_path, extension)
        stems.add(relative_path.stem.lower())
        parent_paths.add(relative_path.parent.as_posix())

    extensions = set(items_by_extension)
    if extensions == BRAINVISION_EXTENSIONS:
        if len(stems) != 1:
            raise HTTPException(status_code=422, detail="BrainVision 三件套必须同名，例如 sub01.vhdr/sub01.eeg/sub01.vmrk")
        if len(parent_paths) != 1:
            raise HTTPException(status_code=422, detail="BrainVision 三件套必须位于同一文件夹")
        return "brainvision", items_by_extension

    if len(extensions) == 1:
        extension = next(iter(extensions))
        if extension in STANDARD_SINGLE_EXTENSIONS:
            return STANDARD_SINGLE_EXTENSIONS[extension].lower(), items_by_extension
        raise HTTPException(status_code=422, detail="BrainVision 数据必须同时包含同名 .vhdr、.eeg、.vmrk")

    raise HTTPException(status_code=422, detail="一次导入只能包含一个 BrainVision 三件套，或一个 EDF/BDF 文件")


def build_fif_stem(
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
) -> str:
    parts = [bids_subject_id]
    if session:
        parts.append(session)
    if task:
        parts.append(task)
    if run:
        parts.append(run)
    return "_".join(parts)


def canonical_fif_logical_dir(
    bids_subject_id: str,
    session: str | None,
) -> str:
    # 两层重构：canonical FIF 物理目录 = BIDSdata/sub-/[ses-/]eeg（去掉旧 derivatives + task/run/upload 嵌套）。
    # 同被试多 task 共享 eeg 目录，靠文件名 stem（含 task/run）区分；同 sub/ses/task/run 重传则覆盖。
    parts = [DATASET_CANONICAL_FIF_PREFIX, bids_subject_id]
    if session:
        parts.append(session)
    parts.append("eeg")
    return normalize_storage_logical_path("/".join(parts))


def build_canonical_fif_base_path_for_asset(
    dataset_asset_id: uuid.UUID | str,
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
) -> Path:
    root = dataset_asset_root(dataset_asset_id)
    logical_dir = canonical_fif_logical_dir(bids_subject_id, session)
    return root / logical_dir / build_fif_stem(bids_subject_id, session, task, run)


def build_canonical_fif_base_path(
    dataset_version: DatasetVersion,
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
) -> Path:
    return build_canonical_fif_base_path_for_asset(
        dataset_version.dataset_asset_id, bids_subject_id, session, task, run
    )


def make_import_job_id() -> str:
    return f"import-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def dataset_asset_root(dataset_asset_id: uuid.UUID | str) -> Path:
    # 两层重构：asset 根，下含 sourcedata/（asset 级共享）、BIDSdata/（working FIF）、ver{label}/（发布快照）。
    return Path(settings.DATASETS_STORAGE_ROOT) / str(dataset_asset_id)


def dataset_fif_root_uri(dataset_asset_id: uuid.UUID | str, version_label: str = WORKING_DATASET_VERSION_LABEL) -> str:
    # 版本 FIF 根 URI（存 dataset_versions.storage_uri）。working→BIDSdata，发布→ver{label}。
    prefix = DATASET_CANONICAL_FIF_PREFIX if version_label == WORKING_DATASET_VERSION_LABEL else f"ver{version_label}"
    return f"elys://datasets/{dataset_asset_id}/{prefix}"


def dataset_upload_logical_dir(upload_seq: int) -> str:
    return normalize_storage_logical_path(f"{DATASET_ORIGINAL_UPLOADS_PREFIX}/upload-{upload_seq:03d}")


def dataset_storage_uri(dataset_asset_id: uuid.UUID | str, logical_path: str) -> str:
    normalized = normalize_storage_logical_path(logical_path)
    base = f"elys://datasets/{dataset_asset_id}"
    return f"{base}/{normalized}" if normalized else base


def get_or_create_working_dataset_version(
    db: Session,
    *,
    dataset_asset: DatasetAsset,
    current_user: User,
) -> DatasetVersion:
    version = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.dataset_asset_id == dataset_asset.id,
            DatasetVersion.version_label == WORKING_DATASET_VERSION_LABEL,
        )
        .first()
    )
    if version is not None:
        if not version.storage_uri:
            version.storage_uri = dataset_fif_root_uri(dataset_asset.id)
            db.flush()
        return version

    version = DatasetVersion(
        dataset_asset_id=dataset_asset.id,
        version_label=WORKING_DATASET_VERSION_LABEL,
        storage_uri=dataset_fif_root_uri(dataset_asset.id),
        metadata_json={"auto_created": True, "source": "upload"},
        created_by=current_user.id,
    )
    db.add(version)
    db.flush()
    return version


def make_import_job_dir(
    study: Study,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
    upload_seq: int,
    dataset_asset: DatasetAsset | None = None,
) -> Path:
    if dataset_asset is not None:
        return dataset_asset_root(dataset_asset.id) / dataset_upload_logical_dir(upload_seq)

    root = Path(study.data_root) / "source_uploads" / bids_subject_id
    if session:
        root = root / session
    root = root / task / (run or "run-none")
    return root / f"upload-{upload_seq:03d}"


def get_next_upload_seq(
    db: Session,
    *,
    dataset: Recording | None,
    study: Study,
    dataset_asset: DatasetAsset | None,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
) -> int:
    if dataset:
        max_seq = (
            db.query(func.max(RecordingVersion.version_seq))
            .filter(RecordingVersion.recording_id == dataset.id)
            .scalar()
        )
        seq = (max_seq + 1) if max_seq else (2 if dataset.source_path else 1)
    else:
        seq = 1

    # 两层重构：canonical FIF 不再按 upload_seq 隔离（同 recording 重传覆盖 BIDSdata 内同名），
    # upload_seq 只决定 sourcedata 批次目录，故只需看 sourcedata upload dir 是否已占用。
    while make_import_job_dir(study, bids_subject_id, session, task, run, seq, dataset_asset=dataset_asset).exists():
        seq += 1
    return seq


def is_storage_uri(value: str) -> bool:
    return "://" in str(value)


def normalize_storage_logical_path(path_value: str) -> str:
    text = str(path_value or "").replace("\\", "/").strip("/")
    if not text:
        return ""
    return PurePosixPath(text).as_posix()


def dataset_storage_reference_for_path(path: Path) -> tuple[str, str] | None:
    try:
        relative_to_datasets_root = path.resolve().relative_to(Path(settings.DATASETS_STORAGE_ROOT).resolve()).as_posix()
    except ValueError:
        return None

    parts = PurePosixPath(relative_to_datasets_root).parts
    if len(parts) < 2:
        return None

    dataset_asset_id = parts[0]
    logical_path = normalize_storage_logical_path("/".join(parts[1:]))
    return dataset_storage_uri(dataset_asset_id, logical_path), logical_path


def dataset_logical_path_from_storage_uri(storage_uri: str | None) -> str | None:
    text = str(storage_uri or "")
    if not text.startswith("elys://datasets/"):
        return None
    without_scheme = text.removeprefix("elys://datasets/")
    parts = PurePosixPath(without_scheme).parts
    if len(parts) < 2:
        return None
    return normalize_storage_logical_path("/".join(parts[1:]))


def dataset_logical_path_for_version(dataset_version: DatasetVersion | None, path: Path) -> str | None:
    if dataset_version is None:
        return None
    root = dataset_asset_root(dataset_version.dataset_asset_id)
    try:
        return normalize_storage_logical_path(path.resolve().relative_to(root.resolve()).as_posix())
    except ValueError:
        return None


def relative_to_study(study: Study, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path(study.data_root).resolve()).as_posix()
    except ValueError:
        dataset_reference = dataset_storage_reference_for_path(resolved)
        if dataset_reference is not None:
            storage_uri, _logical_path = dataset_reference
            return storage_uri
        return resolved.as_posix()


def write_manifest(job_dir: Path, payload: dict[str, Any]) -> None:
    manifest_path = job_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def write_upload_file(upload: UploadFile, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with destination.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                handle.write(chunk)
    finally:
        await upload.close()

    if total == 0:
        raise HTTPException(status_code=422, detail=f"{upload.filename} 是空文件")
    return total


async def archive_uploads(
    items_by_extension: dict[str, UploadItem],
    job_dir: Path,
    *,
    files_subdir: str | None = "files",
) -> dict[str, Path]:
    files_dir = job_dir / files_subdir if files_subdir else job_dir
    archived: dict[str, Path] = {}
    targets: set[Path] = set()
    for extension, item in items_by_extension.items():
        target = files_dir / item.relative_path
        resolved = target.resolve()
        if resolved in targets:
            raise HTTPException(status_code=422, detail=f"上传文件路径重复: {item.relative_path.as_posix()}")
        targets.add(resolved)
        await write_upload_file(item.upload, target)
        archived[extension] = target
    return archived


def compute_files_checksum(paths: list[Path]) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                total += len(chunk)
                digest.update(chunk)
    return digest.hexdigest(), total


def compute_file_sha256(path: Path) -> tuple[str | None, int | None]:
    if not path.exists() or not path.is_file():
        return None, None
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def normalize_study_relative_path(relative_path: str) -> str:
    text = str(relative_path).replace("\\", "/")
    if is_storage_uri(text):
        return text
    return PurePosixPath(text).as_posix()


def resolve_study_relative_path(study: Study, relative_path: str) -> Path:
    normalized_text = normalize_study_relative_path(relative_path)
    if normalized_text.startswith("elys://datasets/"):
        without_scheme = normalized_text.removeprefix("elys://datasets/")
        parts = PurePosixPath(without_scheme).parts
        if len(parts) >= 1:
            return dataset_asset_root(parts[0]).joinpath(*parts[1:])
    if normalized_text.startswith("study://"):
        without_scheme = normalized_text.removeprefix("study://")
        parts = PurePosixPath(without_scheme).parts
        if len(parts) >= 2 and parts[0] == study.id:
            return Path(study.data_root).joinpath(*parts[1:])
    normalized = PurePosixPath(normalize_study_relative_path(relative_path))
    return Path(study.data_root).joinpath(*normalized.parts)


def study_storage_uri(study: Study, relative_path: str) -> str:
    normalized = normalize_study_relative_path(relative_path)
    if is_storage_uri(normalized):
        return normalized
    return f"study://{study.id}/{normalized}"


def guess_dataset_file_mime_type(relative_path: str) -> str | None:
    suffix = PurePosixPath(relative_path).suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".tsv":
        return "text/tab-separated-values"
    if suffix in {".txt", ".vhdr", ".vmrk"}:
        return "text/plain"
    if suffix in {".fif", ".edf", ".bdf", ".eeg"}:
        return "application/octet-stream"
    return None


def add_dataset_file_record(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    upload_record: RecordingVersion,
    dataset_version: DatasetVersion | None = None,
    file_role: str,
    relative_path: str,
    current_user: User,
    metadata: dict[str, Any] | None = None,
    absolute_path: Path | None = None,
    storage_uri: str | None = None,
    logical_path: str | None = None,
) -> DatasetFile:
    normalized_path = normalize_study_relative_path(relative_path)
    target_path = absolute_path or resolve_study_relative_path(study, normalized_path)
    sha256, file_size = compute_file_sha256(target_path)
    normalized_logical_path = normalize_storage_logical_path(logical_path) if logical_path else None
    resolved_storage_uri = storage_uri or study_storage_uri(study, normalized_path)
    mime_reference = normalized_logical_path or normalized_path
    record = DatasetFile(
        study_id=study.id,
        recording_id=dataset.id,
        recording_version_id=upload_record.id,
        dataset_version_id=dataset_version.id if dataset_version else None,
        file_role=file_role,
        storage_uri=resolved_storage_uri,
        relative_path=normalized_path,
        logical_path=normalized_logical_path,
        file_size=file_size,
        sha256=sha256,
        mime_type=guess_dataset_file_mime_type(mime_reference),
        metadata_json=metadata or {},
        created_by=current_user.id,
    )
    db.add(record)
    return record


def add_dataset_file_derivation_record(
    db: Session,
    *,
    study: Study,
    source_file: DatasetFile,
    derived_file: DatasetFile,
    derivation_kind: str,
    metadata: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> DatasetFileDerivation:
    record = DatasetFileDerivation(
        study_id=study.id,
        source_file=source_file,
        derived_file=derived_file,
        derivation_kind=derivation_kind,
        transform_name="import.generate_canonical_fif",
        transform_version="mvp",
        parameters_json=parameters or {},
        metadata_json=metadata or {},
    )
    db.add(record)
    return record


def create_dataset_file_records(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    upload_record: RecordingVersion,
    dataset_version: DatasetVersion | None,
    primary_source: Path,
    source_format: str,
    archived_paths: list[Path],
    conversion: dict[str, Any],
    current_user: User,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
) -> list[DatasetFile]:
    records: list[DatasetFile] = []
    primary_original_record: DatasetFile | None = None
    canonical_fif_record: DatasetFile | None = None
    canonical_provenance_record: DatasetFile | None = None
    primary_resolved = primary_source.resolve()
    for path in sorted(archived_paths, key=lambda item: item.as_posix()):
        relative_path = relative_to_study(study, path)
        dataset_reference = dataset_storage_reference_for_path(path)
        storage_uri = dataset_reference[0] if dataset_reference else study_storage_uri(study, relative_path)
        logical_path = (
            dataset_reference[1]
            if dataset_reference
            else dataset_logical_path_for_version(dataset_version, path)
        )
        is_primary = path.resolve() == primary_resolved
        original_metadata = {
            "source_format": source_format,
            "is_primary": is_primary,
            "extension": path.suffix.lower(),
            "upload_seq": upload_record.version_seq,
        }
        # 两层重构：raw_bids 降为纯逻辑索引——不再登记 raw_source / raw_bids_data 冗余行。
        # 原始文件只留 original_upload；BIDS 实体映射（sub/ses/task/run）查 recordings 表。
        original_record = add_dataset_file_record(
            db,
            study=study,
            dataset=dataset,
            upload_record=upload_record,
            dataset_version=dataset_version,
            file_role="original_upload",
            relative_path=relative_path,
            storage_uri=storage_uri,
            logical_path=logical_path,
            absolute_path=path,
            current_user=current_user,
            metadata=original_metadata,
        )
        records.append(original_record)
        if is_primary:
            primary_original_record = original_record

    provenance = conversion.get("provenance") if isinstance(conversion.get("provenance"), dict) else {}
    conversion_params = provenance.get("ConversionParams") if isinstance(provenance.get("ConversionParams"), dict) else {}
    canonical_fif_path = conversion.get("canonical_fif_path")
    if canonical_fif_path:
        canonical_fif_text = str(canonical_fif_path)
        canonical_fif_storage_uri = canonical_fif_text if is_storage_uri(canonical_fif_text) else None
        canonical_fif_record = add_dataset_file_record(
            db,
            study=study,
            dataset=dataset,
            upload_record=upload_record,
            dataset_version=dataset_version,
            file_role="fif",
            relative_path=canonical_fif_text,
            storage_uri=canonical_fif_storage_uri,
            logical_path=(
                dataset_logical_path_from_storage_uri(canonical_fif_storage_uri)
                or normalize_study_relative_path(canonical_fif_text)
            ),
            current_user=current_user,
            metadata={
                "canonical_fif_dir": conversion.get("canonical_fif_dir"),
                "generated_by": "import.generate_canonical_fif",
                "upload_seq": upload_record.version_seq,
                "provenance": provenance,
            },
        )
        records.append(canonical_fif_record)

    canonical_provenance_path = conversion.get("canonical_provenance_path")
    if canonical_provenance_path:
        canonical_provenance_text = str(canonical_provenance_path)
        canonical_provenance_storage_uri = (
            canonical_provenance_text if is_storage_uri(canonical_provenance_text) else None
        )
        canonical_provenance_record = add_dataset_file_record(
            db,
            study=study,
            dataset=dataset,
            upload_record=upload_record,
            dataset_version=dataset_version,
            file_role="fif_provenance",
            relative_path=canonical_provenance_text,
            storage_uri=canonical_provenance_storage_uri,
            logical_path=(
                dataset_logical_path_from_storage_uri(canonical_provenance_storage_uri)
                or normalize_study_relative_path(canonical_provenance_text)
            ),
            current_user=current_user,
            metadata={
                "canonical_fif_path": conversion.get("canonical_fif_path"),
                "generated_by": "import.generate_canonical_fif",
                "upload_seq": upload_record.version_seq,
            },
        )
        records.append(canonical_provenance_record)

    # 两层重构（§2.3）：BIDSdata FIF 同目录 sidecar 按类型登记独立 file_role（fif_eeg_json/fif_channels/fif_events），
    # 取代旧泛化 "sidecar"。provenance 已单独登记为 fif_provenance，故在此跳过，避免重复行。
    canonical_sidecar_paths = (
        conversion.get("canonical_sidecar_paths") if isinstance(conversion.get("canonical_sidecar_paths"), dict) else {}
    )
    FIF_SIDECAR_ROLES = {"eeg": "fif_eeg_json", "channels": "fif_channels", "events": "fif_events"}
    for sidecar_key, sidecar_path in sorted(canonical_sidecar_paths.items()):
        sidecar_role = FIF_SIDECAR_ROLES.get(sidecar_key)
        if sidecar_role is None:
            continue
        records.append(
            add_dataset_file_record(
                db,
                study=study,
                dataset=dataset,
                upload_record=upload_record,
                dataset_version=dataset_version,
                file_role=sidecar_role,
                relative_path=str(sidecar_path),
                logical_path=normalize_study_relative_path(str(sidecar_path)),
                current_user=current_user,
                metadata={
                    "sidecar_key": sidecar_key,
                    "generated_by": "import",
                    "upload_seq": upload_record.version_seq,
                },
            )
        )

    derivation_metadata = {
        # 两层重构：原 SourceRawBIDS（合成 raw_bids 路径）退役，溯源改记真实 BIDS 实体 + 原始上传位置。
        "SourceBIDSEntities": provenance.get("SourceBIDSEntities"),
        "SourceOriginalUpload": provenance.get("SourceOriginalUpload"),
        "SourceSHA256": provenance.get("SourceSHA256"),
        "GeneratedBy": provenance.get("GeneratedBy"),
        "canonical_fif_path": conversion.get("canonical_fif_path"),
        "canonical_provenance_path": conversion.get("canonical_provenance_path"),
        "upload_seq": upload_record.version_seq,
    }
    if canonical_fif_record is not None and primary_original_record is not None:
        add_dataset_file_derivation_record(
            db,
            study=study,
            source_file=primary_original_record,
            derived_file=canonical_fif_record,
            derivation_kind="canonical_fif",
            metadata=derivation_metadata,
            parameters=conversion_params,
        )
    if canonical_provenance_record is not None and primary_original_record is not None:
        add_dataset_file_derivation_record(
            db,
            study=study,
            source_file=primary_original_record,
            derived_file=canonical_provenance_record,
            derivation_kind="canonical_fif_provenance",
            metadata=derivation_metadata,
            parameters=conversion_params,
        )

    return records


# 「调整归类」relabel：派生层（canonical FIF + sidecar）按 BIDS 实体命名，改标签 = 把它们物理重排到
# 新 BIDS 路径。下表把 dataset_files.file_role 映射到 canonical 文件名后缀，用来重算路径。
# 原始上传（original_upload / sourcedata）是不可改存档，relabel 一律不碰。
RELABEL_DERIVED_FILE_ROLE_SUFFIXES = {
    "fif": "_eeg.fif",
    "fif_provenance": "_provenance.json",
    "fif_eeg_json": "_eeg.json",
    "fif_channels": "_channels.tsv",
    "fif_events": "_events.tsv",
}


def relabel_recording(
    db: Session,
    *,
    study: Study,
    recording: Recording,
    subject: str,
    session: str | None,
    task: str,
    run: str | None,
    current_user: User,
) -> Recording:
    """重新归类一条采集记录：改 BIDS 实体（被试/会话/任务/轮次），并把派生层（canonical FIF + sidecar）
    物理重排到新 BIDS 路径、同步 recordings / recording_versions / dataset_files 三处路径字段。
    原始上传（sourcedata）不可改、不碰。同一研究项内四元组冲突（schema uq_recordings_bids_entities）则 409。"""
    new_subject = normalize_bids_label(subject, prefix="sub-", required=True)
    new_task = normalize_bids_label(task, prefix="task-", required=True)
    new_session = normalize_bids_label(session or "", prefix="ses-")
    new_run = normalize_bids_label(run or "", prefix="run-")

    old_subject = recording.subject.bids_subject_id if recording.subject else None
    old_session = recording.session
    old_task = recording.task
    old_run = recording.run

    if (new_subject, new_session, new_task, new_run) == (old_subject, old_session, old_task, old_run):
        return recording  # 实体无变化，直接返回

    # 同一研究项内 (subject, session, task, run) 唯一，排除自己；与导入期的存在性判定同口径
    collision = (
        db.query(Recording)
        .join(Subject, Recording.subject_id == Subject.id)
        .filter(
            Recording.study_id == study.id,
            Recording.id != recording.id,
            Subject.bids_subject_id == new_subject,
            Recording.session == new_session,
            Recording.task == new_task,
            Recording.run == new_run,
        )
        .first()
    )
    if collision:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RECORDING_LABEL_CONFLICT",
                "message": (
                    f"本研究项里已经有 {new_subject} / {new_session or '无会话'} / {new_task} / "
                    f"{new_run or '无轮次'} 这条记录了，换一个标签再试。"
                ),
            },
        )

    asset_id = recording.dataset_asset_id
    # 仅当记录已关联数据集（能定位 BIDS 物理路径）时，物理重排派生层；原始上传不碰。
    if asset_id is not None:
        old_base = build_canonical_fif_base_path_for_asset(asset_id, old_subject, old_session, old_task, old_run)
        new_base = build_canonical_fif_base_path_for_asset(asset_id, new_subject, new_session, new_task, new_run)
        if old_base != new_base:
            new_base.parent.mkdir(parents=True, exist_ok=True)
            for suffix in RELABEL_DERIVED_FILE_ROLE_SUFFIXES.values():
                old_path = old_base.with_name(old_base.name + suffix)
                new_path = new_base.with_name(new_base.name + suffix)
                if old_path == new_path or not old_path.exists():
                    continue
                if new_path.exists():
                    new_path.unlink()
                shutil.move(str(old_path), str(new_path))

        # recordings / recording_versions / dataset_files 路径字段按新 BIDS 实体重算
        new_fif_path = relative_to_study(study, new_base.with_name(new_base.name + "_eeg.fif"))
        new_fif_dir = relative_to_study(study, new_base.parent)
        new_sidecar_paths = {
            "eeg": relative_to_study(study, new_base.with_name(new_base.name + "_eeg.json")),
            "channels": relative_to_study(study, new_base.with_name(new_base.name + "_channels.tsv")),
            "events": relative_to_study(study, new_base.with_name(new_base.name + "_events.tsv")),
            "provenance": relative_to_study(study, new_base.with_name(new_base.name + "_provenance.json")),
        }
        # 仅重排"本就有派生数据"的记录；没生成过 canonical 的（fif_path 为空）不无中生有
        if recording.fif_path:
            recording.fif_path = new_fif_path
        for version in recording.versions:
            if version.fif_dir:
                version.fif_dir = new_fif_dir
            if version.fif_path:
                version.fif_path = new_fif_path
            if version.sidecar_paths:
                version.sidecar_paths = dict(new_sidecar_paths)
        for dataset_file in recording.files:
            suffix = RELABEL_DERIVED_FILE_ROLE_SUFFIXES.get(dataset_file.file_role)
            if suffix is None:
                continue  # original_upload 等原始档案不动
            new_rel = relative_to_study(study, new_base.with_name(new_base.name + suffix))
            dataset_file.relative_path = new_rel
            dataset_file.storage_uri = new_rel if is_storage_uri(new_rel) else study_storage_uri(study, new_rel)
            dataset_file.logical_path = (
                dataset_logical_path_from_storage_uri(dataset_file.storage_uri)
                or normalize_study_relative_path(new_rel)
            )

    # 实体本身：找/建目标 Subject（被试变了就重指），再写 session/task/run。
    # 直接赋关系对象（一并同步 subject_id），让响应里 recording.subject 立即是新值。
    subject_record = get_or_create_subject(db, study, new_subject)
    recording.subject = subject_record
    recording.session = new_session
    recording.task = new_task
    recording.run = new_run

    record_audit_event(
        db,
        study_id=study.id,
        action="recording.relabeled",
        actor_id=current_user.id,
        resource_kind="recording",
        resource_id=recording.id,
        resource_label=f"{new_subject}/{new_session or 'no-session'}/{new_task}/{new_run or 'no-run'}",
        metadata={
            "from": {"subject": old_subject, "session": old_session, "task": old_task, "run": old_run},
            "to": {"subject": new_subject, "session": new_session, "task": new_task, "run": new_run},
        },
    )
    db.flush()
    return recording


def create_dataset_upload_record(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    dataset_version: DatasetVersion | None,
    upload_seq: int,
    job_dir: Path,
    primary_source: Path,
    source_format: str,
    archived_paths: list[Path],
    conversion: dict[str, Any],
    total_size: int,
    checksum: str,
    current_user: User,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
    note: str | None = None,
) -> RecordingVersion:
    (
        db.query(RecordingVersion)
        .filter(RecordingVersion.recording_id == dataset.id, RecordingVersion.status == "current")
        .update({"status": "replaced"}, synchronize_session=False)
    )
    upload_record = RecordingVersion(
        recording_id=dataset.id,
        version_seq=upload_seq,
        source_dir=relative_to_study(study, job_dir),
        source_main_file=relative_to_study(study, primary_source),
        source_files=[relative_to_study(study, path) for path in archived_paths],
        source_format=source_format,
        fif_dir=conversion["canonical_fif_dir"],
        fif_path=conversion["canonical_fif_path"],
        sidecar_paths=conversion["canonical_sidecar_paths"],
        file_size=total_size,
        checksum=checksum,
        status="current",
        qa_status="converted",
        uploaded_by=current_user.id,
        note=note,
    )
    db.add(upload_record)
    db.flush()
    dataset.current_version_id = upload_record.id
    create_dataset_file_records(
        db,
        study=study,
        dataset=dataset,
        upload_record=upload_record,
        dataset_version=dataset_version,
        primary_source=primary_source,
        source_format=source_format,
        archived_paths=archived_paths,
        conversion=conversion,
        current_user=current_user,
        bids_subject_id=bids_subject_id,
        session=session,
        task=task,
        run=run,
    )
    return upload_record


def ensure_canonical_fif_targets_are_free(canonical_fif_base: Path) -> None:
    targets = [
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_eeg.fif"),
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_eeg.json"),
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_channels.tsv"),
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_events.tsv"),
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_provenance.json"),
    ]
    for path in targets:
        if path.exists():
            raise HTTPException(
                status_code=409,
                detail=f"canonical FIF 中已存在同名记录，请更换 run 或 subject: {path.name}",
            )


def write_channels_tsv(raw: Any, target: Path) -> None:
    ch_types = raw.get_channel_types() if hasattr(raw, "get_channel_types") else ["EEG"] * len(raw.ch_names)
    bads = set(raw.info.get("bads", []))
    low_cutoff = raw.info.get("highpass", "n/a")
    high_cutoff = raw.info.get("lowpass", "n/a")

    lines = ["name\ttype\tunits\tlow_cutoff\thigh_cutoff\tstatus\tstatus_description"]
    for name, ch_type in zip(raw.ch_names, ch_types):
        units = "uV" if ch_type == "eeg" else "n/a"
        status_value = "bad" if name in bads else "good"
        lines.append(f"{name}\t{ch_type.upper()}\t{units}\t{low_cutoff}\t{high_cutoff}\t{status_value}\t")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_events_tsv(raw: Any, target: Path) -> int:
    annotations = getattr(raw, "annotations", None)
    lines = ["onset\tduration\ttrial_type"]
    count = 0
    if annotations:
        for onset, duration, description in zip(annotations.onset, annotations.duration, annotations.description):
            lines.append(f"{float(onset):.6f}\t{float(duration):.6f}\t{description}")
            count += 1
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def write_eeg_json(
    raw: Any,
    target: Path,
    *,
    task_label: str,
    source_format: str,
    import_job_id: str,
    duration_seconds: float | None,
) -> None:
    payload = {
        "TaskName": task_label.replace("task-", "", 1),
        "SamplingFrequency": float(raw.info["sfreq"]) if raw.info.get("sfreq") else None,
        "EEGChannelCount": len(raw.ch_names),
        "RecordingDuration": duration_seconds,
        "PowerLineFrequency": "n/a",
        "SourceFormat": source_format,
        "ImportJobId": import_job_id,
        "GeneratedBy": "ELYS import pipeline",
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_mne_module():
    try:
        from scipy.special import sph_harm as _sph_harm  # noqa: F401
        import mne
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="服务器 EEG 转换环境异常：MNE/SciPy 依赖不兼容，请重新部署后重试",
        ) from exc
    return mne


def load_raw_for_conversion(upload_kind: str, source_path: Path):
    mne = get_mne_module()

    if upload_kind == "brainvision":
        reader = mne.io.read_raw_brainvision
    elif upload_kind == "edf":
        reader = mne.io.read_raw_edf
    elif upload_kind == "bdf":
        reader = mne.io.read_raw_bdf
    else:
        raise HTTPException(status_code=422, detail=f"{upload_kind} 暂不支持自动转换为 FIF")

    try:
        return reader(str(source_path), preload=True, verbose="ERROR")
    except TypeError:
        try:
            return reader(str(source_path), preload=True)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"FIF 转换失败: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"FIF 转换失败: {exc}") from exc


def anonymize_raw_for_import(raw) -> None:
    """导入转 FIF 时强制 PII 脱敏（2026-06-10 Q3）。

    canonical FIF 是整个工作期分析都在读的工作副本，必须「出生即干净」：擦文件头 subject_info
    （设备塞进去的真名/生日）+ 采集日期归零（MNE 默认保留相对时序）。sourcedata 原件不动
    （事实源，限 owner）；sub-001 假名 + owner 侧登记表负责身份映射，不在 FIF 里。
    """
    try:
        # MNE 默认：清 subject_info、把 meas_date 归到固定基准日（保留 date 间相对时序）。
        raw.anonymize()
    except Exception:
        # 个别格式 / 老版本 anonymize 可能抛错；不阻断，下面兜底强制清空。
        pass
    # 兜底 + 校验：无论 anonymize 是否完全生效，强制清空 subject_info，确保 FIF 头无残留 PII。
    info = raw.info
    try:
        with info._unlock():
            info["subject_info"] = None
    except Exception:
        try:
            info["subject_info"] = None
        except Exception:
            pass


def generate_canonical_fif(
    *,
    study: Study,
    dataset_version: DatasetVersion,
    upload_kind: str,
    source_path: Path,
    source_format: str,
    canonical_fif_base: Path,
    bids_subject_id: str,
    session: str | None,
    task_label: str,
    run: str | None,
    upload_seq: int,
    import_job_id: str,
    archived_files: list[Path],
    checksum: str,
    temp_root: Path,
) -> dict[str, Any]:
    mne = get_mne_module()

    raw = load_raw_for_conversion(upload_kind, source_path)
    # P2 (2026-06-10 Q3): 强制 PII 脱敏，必须在 raw.save() 之前 —— canonical FIF 出生即干净。
    anonymize_raw_for_import(raw)
    temp_dir = Path(tempfile.mkdtemp(prefix="fif-", dir=temp_root))
    # Q6 (2026-06-10): canonical FIF 后缀统一 _eeg.fif（BIDS EEG modality 命名）。
    canonical_fif_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_eeg.fif")
    canonical_eeg_json_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_eeg.json")
    canonical_channels_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_channels.tsv")
    canonical_events_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_events.tsv")
    canonical_provenance_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_provenance.json")
    canonical_version_dir = canonical_fif_base.parent
    temp_targets = [
        temp_dir / canonical_fif_path.name,
        temp_dir / canonical_eeg_json_path.name,
        temp_dir / canonical_channels_path.name,
        temp_dir / canonical_events_path.name,
        temp_dir / canonical_provenance_path.name,
    ]
    temp_fif, temp_eeg_json, temp_channels, temp_events, temp_provenance_json = temp_targets
    committed = False

    try:
        # 两层重构：BIDSdata/sub-/ses-/eeg 为同被试多 task 共享目录，存在是常态，不再 409；
        # 同名文件（同 sub/ses/task/run 重传）在 commit 阶段逐个覆盖。
        sfreq = float(raw.info["sfreq"]) if raw.info.get("sfreq") else None
        n_times = int(raw.n_times) if getattr(raw, "n_times", None) is not None else None
        duration = float(n_times / sfreq) if sfreq and n_times is not None else None

        raw.save(str(temp_fif), overwrite=True, verbose="ERROR")

        # Re-open the written file so import validation catches write/read incompatibilities.
        check_raw = mne.io.read_raw_fif(str(temp_fif), preload=False, verbose="ERROR")
        check_raw.close()

        n_events = write_events_tsv(raw, temp_events)
        write_channels_tsv(raw, temp_channels)
        write_eeg_json(
            raw,
            temp_eeg_json,
            task_label=task_label,
            source_format=source_format,
            import_job_id=import_job_id,
            duration_seconds=duration,
        )

        source_reference = dataset_storage_reference_for_path(source_path)
        source_storage_uri = source_reference[0] if source_reference else study_storage_uri(study, relative_to_study(study, source_path))
        source_original_logical_path = source_reference[1] if source_reference else None
        source_sha256, source_size = compute_file_sha256(source_path)
        # 两层重构（§2.2）：raw_bids 降为纯逻辑索引，溯源不再合成 raw_bids/ 路径——
        # BIDS 身份直接记四元组实体，原始文件位置记 original_upload（sourcedata）。
        provenance = {
            "importJobId": import_job_id,
            "sourceFormat": source_format,
            "SourceBIDSEntities": {
                "subject": bids_subject_id,
                "session": session,
                "task": task_label,
                "run": run,
            },
            "SourceOriginalUpload": {
                "logical_path": source_original_logical_path,
                "storage_uri": source_storage_uri,
                "file_size": source_size,
            },
            "SourceSHA256": source_sha256,
            "checksum": checksum,
            "sourceFiles": [relative_to_study(study, path) for path in archived_files],
            "canonicalFifDir": relative_to_study(study, canonical_version_dir),
            "canonicalFifPath": relative_to_study(study, canonical_fif_path),
            "sidecars": {
                "eeg": relative_to_study(study, canonical_eeg_json_path),
                "channels": relative_to_study(study, canonical_channels_path),
                "events": relative_to_study(study, canonical_events_path),
                "provenance": relative_to_study(study, canonical_provenance_path),
            },
            "validation": {
                "fifReadable": True,
                "nChannels": len(raw.ch_names),
                "sfreq": sfreq,
                "durationSeconds": duration,
                "nEvents": n_events,
            },
            "GeneratedBy": {
                "Name": "ELYS import pipeline",
                "Step": "generate_canonical_fif",
                "Version": "mvp",
            },
            "GeneratedAt": datetime.utcnow().isoformat() + "Z",
            "ConversionParams": {
                "upload_kind": upload_kind,
                "preload": True,
                "output_format": "FIF",
            },
            "createdAt": datetime.utcnow().isoformat() + "Z",
        }
        temp_provenance_json.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

        # 逐文件落入共享 eeg 目录（不整目录 move，避免撞同被试其他 task 的文件）；同名则覆盖（重传）。
        canonical_version_dir.mkdir(parents=True, exist_ok=True)
        for _tmp in temp_targets:
            _dest = canonical_version_dir / _tmp.name
            if _dest.exists():
                _dest.unlink()
            shutil.move(str(_tmp), str(_dest))
        committed = True

        return {
            "canonical_fif_dir": relative_to_study(study, canonical_version_dir),
            "canonical_fif_path": relative_to_study(study, canonical_fif_path),
            "canonical_sidecar_paths": {
                "eeg": relative_to_study(study, canonical_eeg_json_path),
                "channels": relative_to_study(study, canonical_channels_path),
                "events": relative_to_study(study, canonical_events_path),
                "provenance": relative_to_study(study, canonical_provenance_path),
            },
            "canonical_provenance_path": relative_to_study(study, canonical_provenance_path),
            "n_channels": len(raw.ch_names),
            "sfreq": sfreq,
            "duration_seconds": duration,
            "n_events": n_events,
            "provenance": provenance,
            "source_sha256": source_sha256,
            "qa_report": {
                "import": provenance,
                "fif_conversion": {
                    "status": "success",
                    "source_format": source_format,
                    "canonical_fif_path": relative_to_study(study, canonical_fif_path),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                },
            },
        }
    except Exception:
        if not committed:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    finally:
        close = getattr(raw, "close", None)
        if callable(close):
            close()
        # 文件已逐个 move 出 temp_dir（committed 时 temp_dir 已空；未 committed 时清半成品）——总是清理。
        shutil.rmtree(temp_dir, ignore_errors=True)


def materialize_recording_import(
    db: Session,
    *,
    study: Study,
    current_user: User,
    target_asset: DatasetAsset,
    target_version: DatasetVersion,
    target_mount: StudyDatasetMount | None,
    duplicate: Recording | None,
    subject_record: Subject | None,
    bids_subject_id: str,
    session_label: str | None,
    task_label: str,
    run_label: str | None,
    upload_kind: str,
    upload_seq: int,
    job_id: str,
    job_dir: Path,
    archived: dict[str, Path],
    manifest: dict[str, Any],
    temp_root: Path,
    on_progress=None,
) -> Recording:
    """导入的「重活核心」：对**已落盘**的 archived 文件做 校验 → 转 canonical FIF → 写库 → audit → commit，
    返回已回填 subject/current_version 的 Recording。

    同步端点 import_recording 和 Celery worker run_dataset_import 都调它（单一事实源）。
    on_progress(pct:int, msg:str) 可选：worker 传它来上报进度，同步端点不传。
    注意 archived 的 key 是小写扩展名（.vhdr/.eeg/.vmrk/.edf/...），文件必须已经存进 job_dir。
    """
    def _emit(pct, msg):
        if on_progress is not None:
            on_progress(pct, msg)

    archived_paths = list(archived.values())
    checksum, total_size = compute_files_checksum(archived_paths)
    _emit(30, "文件校验完成，准备转换")

    existing_checksum_query = db.query(Recording).filter(
        Recording.study_id == study.id,
        Recording.dataset_asset_id == target_asset.id,
        Recording.checksum == checksum,
    )
    if duplicate:
        existing_checksum_query = existing_checksum_query.filter(Recording.id != duplicate.id)
    existing_checksum = existing_checksum_query.first()
    if existing_checksum:
        manifest.update(
            {
                "status": "duplicate",
                "checksum": checksum,
                "duplicateDatasetId": str(existing_checksum.id),
                "updatedAt": datetime.utcnow().isoformat() + "Z",
            }
        )
        write_manifest(job_dir, manifest)
        raise HTTPException(status_code=409, detail="检测到完全相同的数据已经导入过，已阻止重复入库")
    if duplicate and duplicate.checksum == checksum:
        manifest.update(
            {
                "status": "duplicate",
                "checksum": checksum,
                "duplicateDatasetId": str(duplicate.id),
                "updatedAt": datetime.utcnow().isoformat() + "Z",
            }
        )
        write_manifest(job_dir, manifest)
        raise HTTPException(status_code=409, detail="本次上传与当前数据完全相同，无需替换")

    if upload_kind == "brainvision":
        primary_source = archived[".vhdr"]
        source_format = "BRAINVISION"
    else:
        extension = next(iter(archived))
        primary_source = archived[extension]
        source_format = STANDARD_SINGLE_EXTENSIONS[extension]

    canonical_fif_base = build_canonical_fif_base_path(
        target_version,
        bids_subject_id,
        session_label,
        task_label,
        run_label,
    )
    ensure_canonical_fif_targets_are_free(canonical_fif_base)

    _emit(45, "转换中（原始格式 → canonical FIF）")
    conversion = generate_canonical_fif(
        study=study,
        dataset_version=target_version,
        upload_kind=upload_kind,
        source_path=primary_source,
        source_format=source_format,
        canonical_fif_base=canonical_fif_base,
        bids_subject_id=bids_subject_id,
        session=session_label,
        task_label=task_label,
        run=run_label,
        upload_seq=upload_seq,
        import_job_id=job_id,
        archived_files=archived_paths,
        checksum=checksum,
        temp_root=temp_root,
    )

    subject_record = subject_record or get_or_create_subject(db, study, bids_subject_id)
    source_path = relative_to_study(study, primary_source)
    now = datetime.utcnow()
    if duplicate:
        dataset = duplicate
        if dataset.dataset_asset_id is None:
            dataset.dataset_asset_id = target_asset.id
        elif dataset.dataset_asset_id != target_asset.id:
            raise HTTPException(
                status_code=409,
                detail="该 subject/session/task/run 已存在于另一个 Dataset Asset 中，请调整上传目标或使用新的 run 标签",
            )
        previous_source_path = dataset.source_path
        previous_fif_path = dataset.fif_path
        dataset.source_format = source_format
        dataset.source_path = source_path
        dataset.fif_path = conversion["canonical_fif_path"]
        dataset.file_size = total_size
        dataset.checksum = checksum
        dataset.n_channels = conversion["n_channels"]
        dataset.sfreq = conversion["sfreq"]
        dataset.duration_seconds = conversion["duration_seconds"]
        dataset.n_events = conversion["n_events"]
        dataset.qa_status = "converted"
        dataset.qa_report = {
            **conversion["qa_report"],
            "replacement": {
                "status": "current_version_switched",
                "upload_seq": upload_seq,
                "previous_source_path": previous_source_path,
                "previous_fif_path": previous_fif_path,
                "replaced_at": now.isoformat() + "Z",
            },
        }
        dataset.imported_by = current_user.id
        dataset.imported_at = now
    else:
        dataset = Recording(
            study_id=study.id,
            dataset_asset_id=target_asset.id,
            subject_id=subject_record.id,
            session=session_label,
            task=task_label,
            run=run_label,
            source_format=source_format,
            source_path=source_path,
            fif_path=conversion["canonical_fif_path"],
            file_size=total_size,
            checksum=checksum,
            n_channels=conversion["n_channels"],
            sfreq=conversion["sfreq"],
            duration_seconds=conversion["duration_seconds"],
            n_events=conversion["n_events"],
            qa_status="converted",
            qa_report=conversion["qa_report"],
            imported_by=current_user.id,
        )
        db.add(dataset)
        db.flush()

    upload_record = create_dataset_upload_record(
        db,
        study=study,
        dataset=dataset,
        dataset_version=target_version,
        upload_seq=upload_seq,
        job_dir=job_dir,
        primary_source=primary_source,
        source_format=source_format,
        archived_paths=archived_paths,
        conversion=conversion,
        total_size=total_size,
        checksum=checksum,
        current_user=current_user,
        bids_subject_id=bids_subject_id,
        session=session_label,
        task=task_label,
        run=run_label,
        note="replace_existing" if duplicate else "initial_import",
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="dataset.reuploaded" if duplicate else "dataset.uploaded",
        actor_id=current_user.id,
        resource_kind="dataset",
        resource_id=dataset.id,
        resource_label=f"{bids_subject_id}/{session_label or 'no-session'}/{task_label}/{run_label or 'no-run'}",
        metadata={
            "dataset_upload_id": str(upload_record.id),
            "upload_seq": upload_seq,
            "upload_kind": upload_kind,
            "source_format": source_format,
            "checksum": checksum,
            "file_size": total_size,
            "replace_existing": bool(duplicate),
            "fif_path": dataset.fif_path,
            "canonical_fif_path": conversion.get("canonical_fif_path"),
            "canonical_provenance_path": conversion.get("canonical_provenance_path"),
            "dataset_asset_id": str(dataset.dataset_asset_id) if dataset.dataset_asset_id else None,
            "mount_name": target_mount.mount_name if target_mount else None,
        },
    )
    db.commit()
    db.refresh(dataset)
    dataset.subject = subject_record
    dataset.current_version = upload_record

    manifest.update(
        {
            "status": "done",
            "checksum": checksum,
            "fileSize": total_size,
            "datasetId": str(dataset.id),
            "datasetUploadId": str(upload_record.id),
            "uploadSeq": upload_seq,
            "mode": "replacement" if duplicate else "new",
            "sourcePath": dataset.source_path,
            "fifPath": dataset.fif_path,
            "fifDir": conversion["canonical_fif_dir"],
            "sidecars": conversion["canonical_sidecar_paths"],
            "canonicalFifPath": conversion.get("canonical_fif_path"),
            "canonicalFifDir": conversion.get("canonical_fif_dir"),
            "canonicalProvenancePath": conversion.get("canonical_provenance_path"),
            "canonicalSidecars": conversion.get("canonical_sidecar_paths"),
            "updatedAt": datetime.utcnow().isoformat() + "Z",
        }
    )
    write_manifest(job_dir, manifest)
    return dataset


def parse_bids_entities_from_filename(filename: str) -> dict[str, str]:
    """从 BIDS 文件名提取实体标签：sub-、task-、ses-、run-。
    例：sub-ADMU001_task-eo_eeg.edf → {"sub": "ADMU001", "task": "eo"}
    未找到的实体不在返回 dict 里，调用方自行判断必填项。
    """
    import re
    entities: dict[str, str] = {}
    for entity in ("sub", "task", "ses", "run"):
        m = re.search(rf"(?:^|_){entity}-([^_\.]+)", filename)
        if m:
            entities[entity] = m.group(1)
    return entities


def _build_import_context(
    db: Session,
    *,
    study_id: str,
    current_user: User,
    subject: str,
    task: str,
    session: str | None,
    run: str | None,
    replace_existing: bool,
    dataset_asset_id: "uuid.UUID | None",
    mount_name: str | None,
    files: list[UploadFile],
) -> dict[str, Any]:
    """同步 / 异步两个上传端点共用的「请求阶段前置逻辑」：鉴权、解析 asset/version、分类文件、
    规范 BIDS 标签、重复 409 校验、算 job_id / upload_seq / job_dir、初始化并写 archiving manifest。

    返回一个 dict，把后续 archive_uploads + materialize / 派发任务所需的全部上下文打包带走。
    """
    require_system_permission(current_user, "data:write", "当前用户没有上传数据权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    target_asset, target_mount = resolve_upload_dataset_asset(
        db,
        study=study,
        current_user=current_user,
        dataset_asset_id=dataset_asset_id,
        mount_name=mount_name,
    )
    target_version = get_or_create_working_dataset_version(db, dataset_asset=target_asset, current_user=current_user)
    upload_kind, items_by_extension = classify_uploads(files)

    bids_subject_id = normalize_bids_label(subject, prefix="sub-", required=True)
    task_label = normalize_bids_label(task, prefix="task-", required=True)
    session_label = normalize_bids_label(session or "", prefix="ses-")
    run_label = normalize_bids_label(run or "", prefix="run-")

    subject_record = (
        db.query(Subject)
        .filter(Subject.study_id == study.id, Subject.bids_subject_id == bids_subject_id)
        .first()
    )
    duplicate = None
    if subject_record:
        duplicate = (
            db.query(Recording)
            .options(joinedload(Recording.current_version))
            .filter(
                Recording.study_id == study.id,
                Recording.subject_id == subject_record.id,
                Recording.session == session_label,
                Recording.task == task_label,
                Recording.run == run_label,
            )
            .first()
        )
    if duplicate and not replace_existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DATASET_EXISTS",
                "message": "该数据位已经存在，可以作为新上传版本导入，并在成功后切换为当前版本。",
                "dataset_id": str(duplicate.id),
                "subject": bids_subject_id,
                "session": session_label,
                "task": task_label,
                "run": run_label,
                "current_upload_seq": duplicate.current_version.version_seq if duplicate.current_version else None,
                "fif_path": duplicate.fif_path,
            },
        )

    job_id = make_import_job_id()
    upload_seq = get_next_upload_seq(
        db,
        dataset=duplicate,
        study=study,
        dataset_asset=target_asset,
        bids_subject_id=bids_subject_id,
        session=session_label,
        task=task_label,
        run=run_label,
    )
    job_dir = make_import_job_dir(
        study,
        bids_subject_id,
        session_label,
        task_label,
        run_label,
        upload_seq,
        dataset_asset=target_asset,
    )
    temp_root = Path(study.data_root) / "upload_staging"
    temp_root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "jobId": job_id,
        "uploadSeq": upload_seq,
        "status": "archiving",
        "studyId": study.id,
        "replaceExisting": replace_existing,
        "existingDatasetId": str(duplicate.id) if duplicate else None,
        "datasetAssetId": str(target_asset.id),
        "datasetVersionId": str(target_version.id),
        "datasetVersionLabel": target_version.version_label,
        "mountName": target_mount.mount_name if target_mount else None,
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "entities": {
            "subject": bids_subject_id,
            "session": session_label,
            "task": task_label,
            "run": run_label,
        },
        "uploadKind": upload_kind,
        "files": [item.relative_path.as_posix() for item in items_by_extension.values()],
    }
    write_manifest(job_dir, manifest)

    return {
        "study": study,
        "target_asset": target_asset,
        "target_mount": target_mount,
        "target_version": target_version,
        "upload_kind": upload_kind,
        "items_by_extension": items_by_extension,
        "bids_subject_id": bids_subject_id,
        "session_label": session_label,
        "task_label": task_label,
        "run_label": run_label,
        "subject_record": subject_record,
        "duplicate": duplicate,
        "job_id": job_id,
        "upload_seq": upload_seq,
        "job_dir": job_dir,
        "temp_root": temp_root,
        "manifest": manifest,
    }
