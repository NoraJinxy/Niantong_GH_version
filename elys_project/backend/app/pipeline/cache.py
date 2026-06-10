"""
Purpose: Implement workflow/Pipeline runtime support for cache, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.pipeline.study_output_store import StudyOutputStore
from app.pipeline.contracts import NodeOutput
from app.services.storage import StorageService, StorageUriError


CACHEABLE_NODE_STATUSES = ("success", "cached")


@dataclass
class CacheLookupResult:
    output: NodeOutput
    output_ports: list[str]
    dataset_count: int
    source_job_id: str | None


class PipelineCache:
    def __init__(
        self,
        db: Any,
        study: Any,
        execution: Any,
        job: Any,
        *,
        artifact_model: type[Any] | None = None,
        job_model: type[Any] | None = None,
        base_dir: str | Path | None = None,
        topology: dict[str, str] | None = None,
    ):
        self.db = db
        self.study = study
        self.execution = execution
        self.job = job
        self._artifact_model = artifact_model
        self._job_model = job_model
        self.study_root = self._resolve_study_root(study, base_dir)
        # 拓扑角色字典 {node_id: "leaf" | "intermediate" | "source"}（保留备用；
        # 命中复用直接沿用源行 keep/cache_eligible，不再按角色重算）
        self.topology: dict[str, str] = topology or {}

    def restore_node_output(self, *, node_hash: str, node: dict[str, Any]) -> CacheLookupResult | None:
        if not node_hash:
            return None
        for candidate in self._candidate_jobs(node_hash):
            source_artifacts = self._artifacts_for_job(candidate)
            if not source_artifacts:
                continue
            if not self._artifacts_are_valid(source_artifacts):
                continue
            copied_artifacts = self._register_artifact_references(source_artifacts)
            output_json = getattr(candidate, "output_json", None) or {}
            output = self._restore_output(
                output_json=output_json,
                copied_artifacts=copied_artifacts,
                node=node,
                source_job=candidate,
            )
            return CacheLookupResult(
                output=output,
                output_ports=list(output.outputs.keys()),
                dataset_count=len(output.data_infos),
                source_job_id=self._stringify(getattr(candidate, "id", None)),
            )
        return None

    def _candidate_jobs(self, node_hash: str) -> list[Any]:
        model = self._get_job_model()
        query = self.db.query(model).filter(
            model.study_id == getattr(self.study, "id", None),
            model.node_hash == node_hash,
            model.status.in_(CACHEABLE_NODE_STATUSES),
        )
        current_id = getattr(self.job, "id", None)
        if current_id is not None:
            query = query.filter(model.id != current_id)
        return query.order_by(model.finished_at.desc(), model.id.desc()).all()

    def _artifacts_for_job(self, job: Any) -> list[Any]:
        model = self._get_artifact_model()
        # 必须排除已被 cleanup/用户删除的输出：删除只置 deleted_at、物理文件可能仍在，
        # 所以"文件在 + sha256 对"仍成立，但这些行用户视角是已删除的，不能当作缓存命中
        # 复用（否则下游会引用一条已删除行）。与 study_output_store 的 content-addressed
        # dedup 过滤口径保持一致。
        return (
            self.db.query(model)
            .filter(
                model.produced_by_job_id == getattr(job, "id", None),
                model.deleted_at.is_(None),
            )
            .order_by(model.created_at.asc(), model.id.asc())
            .all()
        )

    def _artifacts_are_valid(self, artifacts: list[Any]) -> bool:
        for artifact in artifacts:
            path = self._artifact_path(artifact)
            if not path.exists():
                return False
            expected_checksum = getattr(artifact, "sha256", None) or getattr(artifact, "checksum", None) or getattr(artifact, "content_hash", None)
            if not expected_checksum:
                return False
            if path.is_dir():
                actual_checksum = StudyOutputStore.sha256_directory(path)
            elif path.is_file():
                actual_checksum = StudyOutputStore.sha256_file(path)
            else:
                return False
            if actual_checksum != expected_checksum:
                return False
        return True

    def _register_artifact_references(self, source_artifacts: list[Any]) -> list[dict[str, Any]]:
        """缓存命中时：不再 INSERT 复制行（会撞 idx_study_output_sha256 唯一约束），
        而是**直接返回旧 study_output 的引用**作为当前 execution 的输出。

        语义：同一物理文件（content-addressed by sha256）只对应一行 study_output；
        多个 execution 通过 pipeline_jobs.output_json.data_infos 引用同一行。
        produced_by_execution_id 保留为"最初产生它的 execution"，新 execution 不动该字段。
        """
        copied: list[dict[str, Any]] = []
        for source in source_artifacts:
            logical_path = str(getattr(source, "logical_path", "") or getattr(source, "storage_path", "") or "")
            storage_uri = getattr(source, "storage_uri", None) or f"study://{getattr(self.study, 'id', '')}/{logical_path}"
            sha256 = getattr(source, "sha256", None) or getattr(source, "checksum", None)
            data_type = str(getattr(source, "data_type", "") or "")
            copied.append(
                {
                    "study_output_id": self._stringify(getattr(source, "id", None)),
                    "artifact_id": self._stringify(getattr(source, "id", None)),  # 旧 key 别名
                    "study_id": str(getattr(self.study, "id", "")),
                    # produced_by_* 保留旧 execution 信息（canonical 来源）
                    "produced_by_execution_id": self._stringify(getattr(source, "produced_by_execution_id", None)),
                    # execution_id / job_id 是"当前 execution 的消费记录"，方便消费方查询
                    "execution_id": self._stringify(getattr(self.execution, "id", None)),
                    "produced_by_job_id": self._stringify(getattr(source, "produced_by_job_id", None)),
                    "job_id": self._stringify(getattr(self.job, "id", None)),
                    "data_type": data_type,
                    "storage_path": logical_path,
                    "logical_path": logical_path,
                    "storage_uri": storage_uri,
                    "file_size": getattr(source, "file_size", None),
                    "checksum": sha256,
                    "sha256": sha256,
                    "content_hash": sha256,
                    "keep": bool(getattr(source, "keep", False)),
                    "cache_eligible": bool(getattr(source, "cache_eligible", False)),
                    "metadata_json": {},
                    "preview_json": getattr(source, "preview_json", None) or {},
                }
            )
        return copied

    def _restore_output(
        self,
        *,
        output_json: dict[str, Any],
        copied_artifacts: list[dict[str, Any]],
        node: dict[str, Any],
        source_job: Any,
    ) -> NodeOutput:
        artifact_by_storage_path = {
            artifact.get("storage_path"): artifact for artifact in copied_artifacts if artifact.get("storage_path")
        }
        artifact_by_storage_uri = {
            artifact.get("storage_uri"): artifact for artifact in copied_artifacts if artifact.get("storage_uri")
        }
        artifact_by_content_hash = {
            artifact.get("content_hash"): artifact for artifact in copied_artifacts if artifact.get("content_hash")
        }
        restored_data_infos = self._restore_value(
            output_json.get("data_infos", []),
            artifact_by_storage_path,
            artifact_by_storage_uri,
            artifact_by_content_hash,
            node,
        )
        outputs = output_json.get("outputs")
        if isinstance(outputs, dict):
            restored_outputs = self._restore_value(
                outputs,
                artifact_by_storage_path,
                artifact_by_storage_uri,
                artifact_by_content_hash,
                node,
            )
        else:
            restored_outputs = {"output": restored_data_infos}
        metadata = dict(output_json.get("metadata") or {})
        metadata["cache"] = {
            "hit": True,
            "source_execution_id": self._stringify(getattr(source_job, "execution_id", None)),
            "source_job_id": self._stringify(getattr(source_job, "id", None)),
            "node_hash": getattr(source_job, "node_hash", None),
        }
        return NodeOutput(
            node_id=str(node.get("id") or ""),
            node_type=str(node.get("type") or ""),
            outputs=restored_outputs,
            data_infos=restored_data_infos if isinstance(restored_data_infos, list) else [],
            artifacts=copied_artifacts,
            metadata=metadata,
        )

    def _restore_value(
        self,
        value: Any,
        artifact_by_storage_path: dict[str, dict[str, Any]],
        artifact_by_storage_uri: dict[str, dict[str, Any]],
        artifact_by_content_hash: dict[str, dict[str, Any]],
        node: dict[str, Any],
    ) -> Any:
        if isinstance(value, list):
            return [
                self._restore_value(item, artifact_by_storage_path, artifact_by_storage_uri, artifact_by_content_hash, node)
                for item in value
            ]
        if not isinstance(value, dict):
            return value

        restored = {
            key: self._restore_value(item, artifact_by_storage_path, artifact_by_storage_uri, artifact_by_content_hash, node)
            for key, item in value.items()
        }
        storage_path = (
            restored.get("storage_path")
            or restored.get("artifact_storage_path")
            or restored.get("fif_path")
        )
        storage_uri = restored.get("storage_uri") or restored.get("artifact_storage_uri")
        content_hash = restored.get("content_hash") or restored.get("checksum")
        artifact = (
            artifact_by_storage_uri.get(storage_uri)
            or artifact_by_storage_path.get(storage_path)
            or artifact_by_content_hash.get(content_hash)
        )
        if artifact is not None:
            restored.update(
                {
                    "artifact_id": artifact.get("artifact_id"),
                    "dataset_file_id": None,
                    "file_role": "pipeline_artifact",
                    "storage_path": artifact.get("storage_path"),
                    "storage_uri": artifact.get("storage_uri"),
                    "logical_path": artifact.get("storage_path"),
                    "artifact_storage_path": artifact.get("storage_path"),
                    "artifact_storage_uri": artifact.get("storage_uri"),
                    "file_size": artifact.get("file_size"),
                    "checksum": artifact.get("checksum"),
                    "sha256": artifact.get("sha256") or artifact.get("checksum"),
                    "content_hash": artifact.get("content_hash"),
                    "pipeline_execution_id": self._stringify(getattr(self.execution, "id", None)),
                    "execution_id": self._stringify(getattr(self.execution, "id", None)),
                    "job_id": self._stringify(getattr(self.job, "id", None)),
                }
            )
            path = self._path_from_artifact_summary(artifact)
            restored["fif_path"] = artifact.get("storage_path")
            restored["fif_abs_path"] = str(path) if path else None
            restored["fif_exists"] = bool(path and path.exists())
        if isinstance(restored.get("processing"), dict):
            restored["processing"] = {
                **restored["processing"],
                "node_id": str(node.get("id") or ""),
                "node_type": str(node.get("type") or ""),
                "cached": True,
            }
        return restored

    def _artifact_path(self, artifact: Any) -> Path:
        storage_uri = getattr(artifact, "storage_uri", None)
        if storage_uri:
            try:
                return StorageService().resolve_path(
                    storage_uri,
                    study_id=getattr(self.study, "id", None),
                    study_root=self.study_root,
                )
            except (StorageUriError, ValueError):
                pass
        storage_path = str(getattr(artifact, "storage_path", "") or "")
        path = Path(storage_path).expanduser()
        if path.is_absolute():
            return path
        return (self.study_root / storage_path).resolve()

    def _path_from_artifact_summary(self, artifact: dict[str, Any]) -> Path | None:
        storage_uri = artifact.get("storage_uri")
        if storage_uri:
            try:
                return StorageService().resolve_path(
                    storage_uri,
                    study_id=getattr(self.study, "id", None),
                    study_root=self.study_root,
                )
            except (StorageUriError, ValueError):
                pass
        return self._path_from_storage_path(str(artifact.get("storage_path") or ""))

    def _path_from_storage_path(self, storage_path: str) -> Path | None:
        if not storage_path:
            return None
        path = Path(storage_path).expanduser()
        if path.is_absolute():
            return path
        return (self.study_root / storage_path).resolve()

    @staticmethod
    def _resolve_study_root(study: Any, base_dir: str | Path | None) -> Path:
        root = base_dir
        if root is None:
            for attr in ("data_root", "study_root", "root_dir", "storage_path"):
                value = getattr(study, attr, None)
                if value:
                    root = value
                    break
        if root is None:
            raise ValueError("study.data_root or base_dir is required")
        return Path(root).expanduser().resolve()

    def _get_artifact_model(self) -> type[Any]:
        if self._artifact_model is None:
            from app.models import StudyOutput

            self._artifact_model = StudyOutput
        return self._artifact_model

    def _get_job_model(self) -> type[Any]:
        if self._job_model is None:
            from app.models import PipelineJob

            self._job_model = PipelineJob
        return self._job_model

    @staticmethod
    def _stringify(value: Any | None) -> str | None:
        if value is None:
            return None
        return str(value)
