"""
Purpose: Implement workflow/Pipeline runtime support for hash, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


HASH_VERSION = "pipeline-node-hash-v2"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def params_hash(params: dict[str, Any] | None, node_spec: dict[str, Any] | None = None) -> str:
    params = params or {}
    node_spec = node_spec or {}
    properties = node_spec.get("properties") if isinstance(node_spec, dict) else []
    hashable: dict[str, Any] = {}
    excluded: set[str] = set()
    known: set[str] = set()

    if isinstance(properties, list):
        for prop in properties:
            if not isinstance(prop, dict):
                continue
            name = prop.get("name")
            if not name:
                continue
            name = str(name)
            known.add(name)
            if prop.get("hash", True) is False:
                excluded.add(name)
                continue
            if name in params:
                hashable[name] = params[name]
            elif "default" in prop:
                hashable[name] = prop.get("default")

    for key, value in params.items():
        text_key = str(key)
        if text_key not in known and text_key not in excluded:
            hashable[text_key] = value

    return sha256_json({"version": HASH_VERSION, "params": hashable})


def input_hash(inputs: dict[str, Any] | None) -> str:
    inputs = inputs or {}
    ports: dict[str, Any] = {}
    for port in sorted(str(key) for key in inputs):
        node_input = inputs[port]
        data_infos = _getattr_or_item(node_input, "data_infos", []) or []
        artifacts = _getattr_or_item(node_input, "artifacts", []) or []
        value = _getattr_or_item(node_input, "value", None)
        ports[port] = {
            "data_infos": [_data_info_signature(item) for item in data_infos if isinstance(item, dict)],
            "artifacts": [_artifact_signature(item) for item in artifacts if isinstance(item, dict)],
            "value": value,
        }
    return sha256_json({"version": HASH_VERSION, "inputs": ports})


def node_hash(
    *,
    node_type: str,
    params_digest: str,
    input_digest: str,
    node_spec: dict[str, Any] | None = None,
) -> str:
    """计算节点指纹（用于 cache hit 判定）。

    只包含影响"算法字节输出"的字段，不包含 spec metadata 版本 / 装饰字段。
    这样 spec 升级（schema_version 改、加 save 子对象、改 ui.color 等）不会破 cache。

    参与 hash 的字段:
      - node_type: 节点类型标识
      - backend.module + backend.function: 实际调用的 Python 函数（算法版本）
      - params_digest: 用户参数（过滤了 hash=false 的 cosmetic 字段）
      - input_digest: 上游 data_info 的内容签名

    显式排除:
      - schema_version: spec 元数据版本，不影响算法行为
      - backend.save_descriptor / output_kind / supports_batch / interactive: 装饰字段
      - cache / compute_cost / output_footprint: 缓存策略字段，不影响算法字节
      - save / ui: P0+ 的 metadata 渲染配置，不影响算法
    """
    node_spec = node_spec or {}
    backend = node_spec.get("backend") if isinstance(node_spec.get("backend"), dict) else {}
    payload = {
        "version": HASH_VERSION,
        "node_type": node_type,
        "backend_module": (backend or {}).get("module"),
        "backend_function": (backend or {}).get("function"),
        "params_hash": params_digest,
        "input_hash": input_digest,
    }
    return sha256_json(payload)


def trace_code(*, node_type: str, node_digest: str) -> str:
    safe_type = re.sub(r"[^A-Za-z0-9_.-]+", "-", node_type).strip("-") or "node"
    return f"{safe_type}-{node_digest[:16]}"


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _data_info_signature(data_info: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "content_hash",
        "sha256",
        "checksum",
        "artifact_id",
        "storage_path",
        "storage_uri",
        "logical_path",
        "artifact_storage_path",
        "artifact_storage_uri",
        "fif_path",
        "dataset_file_id",
        "file_role",
        "dataset_id",
        "source_dataset_id",
        "data_type",
        "processing",
    )
    return {key: data_info.get(key) for key in keys if key in data_info}


def _artifact_signature(artifact: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "content_hash",
        "checksum",
        "artifact_id",
        "storage_path",
        "artifact_type",
        "data_type",
        "source_dataset_id",
    )
    return {key: artifact.get(key) for key in keys if key in artifact}


def _getattr_or_item(value: Any, key: str, default: Any) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)
