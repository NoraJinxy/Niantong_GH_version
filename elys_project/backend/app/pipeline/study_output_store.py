"""
Purpose: StudyOutputStore — Pipeline 节点产出的派生数据集统一登记与物理存储。
负责把节点写出的文件 / 目录 / JSON content-addressed 落到 `derived/{sha256[0:2]}/{sha256}/`，
同时在 `study_outputs` 表登记一行（产出来源、上游、BIDS 维度、retention 等）。

Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, wiki/docs/5-00 and wiki/docs/7-40.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

from app.config import get_settings

from .contracts import StudyOutputSummary


class StudyOutputStore:
    def __init__(
        self,
        db: Any,
        study: Any,
        execution: Any,
        job: Any | None = None,
        *,
        base_dir: str | Path | None = None,
        study_output_model: type[Any] | None = None,
    ):
        self.db = db
        self.study = study
        self.execution = execution
        self.job = job
        self._study_output_model = study_output_model
        self.study_root = self._resolve_legacy_study_root(study, base_dir)
        self.execution_id = getattr(execution, "id", execution)
        self.study_id = getattr(study, "id", None)
        if self.study_id is None:
            raise ValueError("study.id is required")
        if self.execution_id is None:
            raise ValueError("execution.id is required")
        self.study_root = self._resolve_study_root(str(self.study_id))

    @staticmethod
    def _resolve_legacy_study_root(study: Any, base_dir: str | Path | None) -> Path:
        """旧版:从 study 对象的 data_root/study_root/root_dir/storage_path 属性取 root。"""
        root = base_dir
        if root is None:
            for attr in ("data_root", "study_root", "root_dir", "storage_path"):
                value = getattr(study, attr, None)
                if value:
                    root = value
                    break
        if root is None:
            raise ValueError("study.data_root or base_dir is required")
        path = Path(root).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _resolve_study_root(study_id: str) -> Path:
        """新版:从 STUDIES_STORAGE_ROOT 拼 study_id 目录。"""
        path = Path(get_settings().STUDIES_STORAGE_ROOT) / str(study_id)
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def node_dir(self, node_id: str | None = None) -> Path:
        return self.temp_node_dir(node_id)

    def temp_node_dir(self, node_id: str | None = None) -> Path:
        resolved_node_id = self._node_id(node_id)
        path = self.study_root / "temp" / str(self.execution_id) / resolved_node_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    @contextmanager
    def temporary_directory(self, node_id: str | None = None) -> Iterator[Path]:
        temp_dir = Path(tempfile.mkdtemp(prefix=".tmp-", dir=self.node_dir(node_id)))
        try:
            yield temp_dir
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def save_json(
        self,
        filename: str,
        payload: Any,
        *,
        kind: str = "metadata",
        data_type: str = "json",
        metadata: dict[str, Any] | None = None,
        preview: dict[str, Any] | None = None,
        source_dataset_id: Any | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        def writer(path: Path) -> None:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)

        return self.save_file_from_writer(
            filename,
            writer,
            kind=kind,
            data_type=data_type,
            metadata=metadata,
            preview=preview,
            source_dataset_id=source_dataset_id,
            node_id=node_id,
        )

    def publish_file(
        self,
        source_path: str | Path,
        *,
        filename: str | None = None,
        kind: str = "file",
        data_type: str = "file",
        metadata: dict[str, Any] | None = None,
        preview: dict[str, Any] | None = None,
        source_dataset_id: Any | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(f"Derived dataset source file does not exist: {source}")

        def writer(path: Path) -> None:
            shutil.copy2(source, path)

        return self.save_file_from_writer(
            filename or source.name,
            writer,
            kind=kind,
            data_type=data_type,
            metadata=metadata,
            preview=preview,
            source_dataset_id=source_dataset_id,
            node_id=node_id,
        )

    def publish_directory(
        self,
        source_dir: str | Path,
        *,
        dirname: str | None = None,
        kind: str = "directory",
        data_type: str = "directory",
        metadata: dict[str, Any] | None = None,
        preview: dict[str, Any] | None = None,
        source_dataset_id: Any | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        source = Path(source_dir)
        if not source.is_dir():
            raise FileNotFoundError(f"Derived dataset source directory does not exist: {source}")

        safe_dirname = self._safe_name(dirname or source.name)
        temp_root = Path(tempfile.mkdtemp(prefix=f".tmp-{safe_dirname}-", dir=self.temp_node_dir(node_id)))
        staged = temp_root / safe_dirname
        final_path: Path | None = None
        published_new = False
        try:
            shutil.copytree(source, staged)
            file_size = self._directory_size(staged)
            checksum = self.sha256_directory(staged)
            final_path = self._content_addressed_path(checksum, safe_dirname)
            if final_path.exists():
                if not final_path.is_dir() or self.sha256_directory(final_path) != checksum:
                    raise FileExistsError(f"Content-addressed derived path is occupied by different content: {final_path}")
                shutil.rmtree(staged, ignore_errors=True)
            else:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(staged), str(final_path))
                published_new = True
            try:
                summary = self._register_study_output(
                    storage_path=self._storage_path(final_path),
                    file_size=file_size,
                    checksum=checksum,
                    kind=kind,
                    data_type=data_type,
                    metadata=metadata or {},
                    preview=preview or {},
                    source_dataset_id=source_dataset_id,
                )
            except Exception:
                if published_new and final_path.exists():
                    shutil.rmtree(final_path, ignore_errors=True)
                raise
            return summary.to_dict()
        except Exception:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)
            raise
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

    def save_file_from_writer(
        self,
        filename: str,
        writer: Callable[[Path], None],
        *,
        kind: str,
        data_type: str,
        metadata: dict[str, Any] | None = None,
        preview: dict[str, Any] | None = None,
        source_dataset_id: Any | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        safe_filename = self._safe_name(filename)
        temp_root = Path(tempfile.mkdtemp(prefix=f".tmp-{safe_filename}-", dir=self.temp_node_dir(node_id)))
        temp_path = temp_root / safe_filename
        final_path: Path | None = None
        published_new = False
        try:
            writer(temp_path)
            if not temp_path.is_file():
                raise FileNotFoundError(f"Derived dataset writer did not create a file: {temp_path}")
            file_size = temp_path.stat().st_size
            checksum = self.sha256_file(temp_path)
            final_path = self._content_addressed_path(checksum, safe_filename)
            if final_path.exists():
                if not final_path.is_file() or self.sha256_file(final_path) != checksum:
                    raise FileExistsError(f"Content-addressed derived path is occupied by different content: {final_path}")
                temp_path.unlink()
            else:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp_path), str(final_path))
                published_new = True
            try:
                summary = self._register_study_output(
                    storage_path=self._storage_path(final_path),
                    file_size=file_size,
                    checksum=checksum,
                    kind=kind,
                    data_type=data_type,
                    metadata=metadata or {},
                    preview=preview or {},
                    source_dataset_id=source_dataset_id,
                )
            except Exception:
                if published_new and final_path.exists():
                    final_path.unlink()
                raise
            return summary.to_dict()
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)
            raise
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

    @staticmethod
    def sha256_file(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def sha256_directory(cls, path: str | Path) -> str:
        root = Path(path)
        digest = hashlib.sha256()
        for file_path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = file_path.relative_to(root).as_posix().encode("utf-8")
            digest.update(relative)
            digest.update(b"\0")
            digest.update(cls.sha256_file(file_path).encode("ascii"))
            digest.update(b"\0")
        return digest.hexdigest()

    @staticmethod
    def _directory_size(path: Path) -> int:
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())

    def _register_study_output(
        self,
        *,
        storage_path: str,
        file_size: int,
        checksum: str,
        kind: str,
        data_type: str,
        metadata: dict[str, Any],
        preview: dict[str, Any],
        source_dataset_id: Any | None,
    ) -> StudyOutputSummary:
        """Write a study_outputs row, or return existing row if same sha256 already exists.

        content-addressed dedup：物理文件已经按 sha256 去重，DB 也保持每个 sha256 一行。
        - 已存在 (study_id, sha256) 行 → 直接返回它的 summary，不 INSERT
          兜底场景：cache miss 导致重跑了节点，但产物字节相同；避免撞 idx_study_output_sha256 unique。
        - 不存在 → 正常 INSERT 新行。
        """
        derived_model = self._get_study_output_model()
        storage_uri = self._storage_uri(storage_path)

        # === content-addressed dedup ===
        # 写文件已经完成，sha256 已知；查 DB 是否已有同 (study, sha256) 的行
        if checksum:
            existing = (
                self.db.query(derived_model)
                .filter(
                    derived_model.study_id == self.study_id,
                    derived_model.sha256 == checksum,
                    derived_model.deleted_at.is_(None),
                )
                .order_by(derived_model.created_at.asc())
                .first()
            )
            if existing is not None:
                # 复用旧行（produced_by_* 保留旧 execution；新 execution 的消费记录走 job.output_json）
                return self._derived_summary_from_row(existing)

        node_id = self._safe_str(getattr(self.job, "node_id", None))
        node_type = self._safe_str(getattr(self.job, "node_type", None))
        produced_by_params = self._safe_dict(metadata.get("params") if isinstance(metadata, dict) else None)
        upstream_recording_ids = self._normalise_id_list(
            metadata.get("upstream_recording_ids") if isinstance(metadata, dict) else None
        ) or ([self._stringify(source_dataset_id)] if source_dataset_id is not None else [])
        upstream_dataset_ids = self._normalise_id_list(
            metadata.get("upstream_dataset_ids") if isinstance(metadata, dict) else None
        )
        bids_entities = self._safe_dict(
            metadata.get("input_data_info") if isinstance(metadata, dict) else None
        )
        keep = bool(metadata.get("keep")) if isinstance(metadata, dict) else False
        cache_eligible = bool(metadata.get("cache_eligible")) if isinstance(metadata, dict) else False
        retention_expires_at = (
            metadata.get("retention_expires_at") if isinstance(metadata, dict) else None
        )
        if keep:
            retention_expires_at = None

        derived = derived_model(
            study_id=self.study_id,
            produced_by_execution_id=self.execution_id,
            produced_by_job_id=getattr(self.job, "id", None),
            produced_by_node_id=node_id,
            produced_by_node_type=node_type,
            produced_by_params=produced_by_params,
            upstream_dataset_ids=upstream_dataset_ids,
            upstream_recording_ids=[i for i in upstream_recording_ids if i],
            data_type=data_type,
            subject_id=self._safe_uuid(bids_entities.get("subject_id")),
            bids_subject_id=self._safe_str(bids_entities.get("bids_subject_id") or bids_entities.get("subject")),
            session=self._safe_str(bids_entities.get("session")),
            task=self._safe_str(bids_entities.get("task")),
            run_label=self._safe_str(bids_entities.get("run") or bids_entities.get("run_label")),
            # condition 优先取 metadata 顶层显式传入（Epoch split_by 时 dispatcher 设置），
            # 否则回落到上游 BIDS 实体的 condition 字段。
            condition=self._safe_str(
                (metadata.get("condition") if isinstance(metadata, dict) else None)
                or bids_entities.get("condition")
            ),
            display_name=self._safe_str(
                (metadata.get("display_name") if isinstance(metadata, dict) else None)
                or self._default_display_name(data_type, bids_entities)
            ),
            tags=list(metadata.get("tags") or []) if isinstance(metadata, dict) else [],
            storage_uri=storage_uri,
            logical_path=storage_path,
            file_role=self._default_file_role(data_type, kind),
            file_size=file_size,
            sha256=checksum,
            mime_type=self._safe_str(metadata.get("mime_type") if isinstance(metadata, dict) else None),
            keep=keep,
            cache_eligible=cache_eligible,
            retention_expires_at=retention_expires_at,
            preview_json=preview,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(derived)
        self.db.flush()

        return StudyOutputSummary(
            study_output_id=self._stringify(getattr(derived, "id", None)),
            study_id=str(self.study_id),
            produced_by_execution_id=self._stringify(self.execution_id),
            produced_by_job_id=self._stringify(getattr(self.job, "id", None)),
            produced_by_node_id=node_id,
            produced_by_node_type=node_type,
            upstream_dataset_ids=upstream_dataset_ids,
            upstream_recording_ids=[i for i in upstream_recording_ids if i],
            data_type=data_type,
            subject_id=self._stringify(derived.subject_id),
            bids_subject_id=derived.bids_subject_id,
            session=derived.session,
            task=derived.task,
            run_label=derived.run_label,
            condition=derived.condition,
            display_name=derived.display_name,
            tags=list(derived.tags or []),
            storage_uri=storage_uri,
            logical_path=storage_path,
            file_role=derived.file_role,
            file_size=file_size,
            sha256=checksum,
            mime_type=derived.mime_type,
            keep=keep,
            cache_eligible=cache_eligible,
            retention_expires_at=retention_expires_at.isoformat() if isinstance(retention_expires_at, datetime) else None,
            preview_json=preview,
            produced_by_params=produced_by_params,
        )

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _derived_summary_from_row(self, row: Any) -> StudyOutputSummary:
        """把已存在的 StudyOutput ORM 行包装成 StudyOutputSummary，
        用于 content-addressed dedup 命中时复用旧行。"""
        retention_expires_at = getattr(row, "retention_expires_at", None)
        return StudyOutputSummary(
            study_output_id=self._stringify(getattr(row, "id", None)),
            study_id=str(getattr(row, "study_id", "") or ""),
            produced_by_execution_id=self._stringify(getattr(row, "produced_by_execution_id", None)),
            produced_by_job_id=self._stringify(getattr(row, "produced_by_job_id", None)),
            produced_by_node_id=getattr(row, "produced_by_node_id", None),
            produced_by_node_type=getattr(row, "produced_by_node_type", None),
            upstream_dataset_ids=list(getattr(row, "upstream_dataset_ids", None) or []),
            upstream_recording_ids=list(getattr(row, "upstream_recording_ids", None) or []),
            data_type=getattr(row, "data_type", "") or "",
            subject_id=self._stringify(getattr(row, "subject_id", None)),
            bids_subject_id=getattr(row, "bids_subject_id", None),
            session=getattr(row, "session", None),
            task=getattr(row, "task", None),
            run_label=getattr(row, "run_label", None),
            condition=getattr(row, "condition", None),
            display_name=getattr(row, "display_name", None),
            tags=list(getattr(row, "tags", None) or []),
            storage_uri=getattr(row, "storage_uri", None),
            logical_path=getattr(row, "logical_path", None),
            file_role=getattr(row, "file_role", None),
            file_size=getattr(row, "file_size", None),
            sha256=getattr(row, "sha256", None),
            mime_type=getattr(row, "mime_type", None),
            keep=bool(getattr(row, "keep", False)),
            cache_eligible=bool(getattr(row, "cache_eligible", False)),
            retention_expires_at=retention_expires_at.isoformat() if isinstance(retention_expires_at, datetime) else None,
            preview_json=dict(getattr(row, "preview_json", None) or {}),
            produced_by_params=dict(getattr(row, "produced_by_params", None) or {}),
        )

    def _get_study_output_model(self) -> type[Any]:
        if self._study_output_model is None:
            from app.models import StudyOutput

            self._study_output_model = StudyOutput
        return self._study_output_model

    @staticmethod
    def _normalise_id_list(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple, set)):
            return []
        return [str(item) for item in value if item]

    @staticmethod
    def _safe_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _safe_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _safe_uuid(value: Any) -> Any:
        if value is None or value == "":
            return None
        return value

    @staticmethod
    def _default_display_name(data_type: str, bids: dict[str, Any]) -> str:
        subject = bids.get("bids_subject_id") or bids.get("subject") or bids.get("subject_id")
        task = bids.get("task")
        pieces = [data_type]
        if subject:
            pieces.append(str(subject))
        if task:
            pieces.append(f"task-{task}" if not str(task).startswith("task-") else str(task))
        return " ".join(pieces)

    @staticmethod
    def _default_file_role(data_type: str, kind: str) -> str:
        mapping = {
            "raw": "canonical_fif",
            "filtered_raw": "canonical_fif",
            "ica_cleaned": "canonical_fif",
            "epochs": "canonical_fif",
            "evoked": "canonical_fif",
            "psd": "canonical_fif",
            "tfr": "canonical_fif",
            "json": "metadata_json",
            "metadata": "metadata_json",
            "directory": "directory",
        }
        return mapping.get(data_type, kind or "derivative")

    def _node_id(self, node_id: str | None) -> str:
        resolved = node_id or getattr(self.job, "node_id", None)
        if not resolved:
            raise ValueError("node_id or job.node_id is required")
        return self._safe_name(str(resolved))

    def _final_path(self, filename: str, node_id: str | None) -> Path:
        target_dir = self.node_dir(node_id)
        base_name = self._safe_name(filename)
        candidate = target_dir / base_name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        for index in range(1, 1000):
            next_candidate = target_dir / f"{stem}-{index}{suffix}"
            if not next_candidate.exists():
                return next_candidate
        raise FileExistsError(f"Could not allocate derived dataset filename for {filename}")

    def _content_addressed_path(self, checksum: str, filename: str) -> Path:
        digest = str(checksum or "").strip().lower()
        if len(digest) < 8:
            raise ValueError("Derived dataset checksum is required for content-addressed storage.")
        return self.study_root / "derived" / digest[:2] / digest / self._safe_name(filename)

    def _storage_path(self, path: Path) -> str:
        return path.relative_to(self.study_root).as_posix()

    def _storage_uri(self, storage_path: str) -> str:
        return f"elys://studies/{self.study_id}/{storage_path}"

    @staticmethod
    def _safe_name(value: str) -> str:
        name = Path(value).name
        if not name or name in {".", ".."}:
            raise ValueError(f"Invalid derived dataset name: {value}")
        return name

    @staticmethod
    def _stringify(value: Any | None) -> str | None:
        if value is None:
            return None
        return str(value)
