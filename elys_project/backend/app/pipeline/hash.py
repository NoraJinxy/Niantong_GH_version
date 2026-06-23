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

# 纯运行时 / 记账字段：交互节点 resume 时由执行器/路由注入，不是真正的算法参数，
# 引擎从不读它们。尤其 decision_version 每次 resume 自增 —— 若进 params_hash，
# 交互节点（artifact_mark / ica_apply / event_manager）每次 resume 都换 node_hash、
# 永远命不中缓存、每 resume 必重算。这些字段无内容区分度（真正的决策内容由
# excluded_components / bad_segments / bad_channels / channel_action / events /
# group_operations 等真实参数承载，照常参与 hash），故一律排除。
RUNTIME_PARAM_KEYS = frozenset({
    "decision_version",
    "interaction_decision",
})


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
            if name in RUNTIME_PARAM_KEYS or prop.get("hash", True) is False:
                excluded.add(name)
                continue
            if name in params:
                hashable[name] = params[name]
            elif "default" in prop:
                hashable[name] = prop.get("default")

    for key, value in params.items():
        text_key = str(key)
        if text_key in RUNTIME_PARAM_KEYS:
            continue
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


# 签名只取「内容身份」字段：内容哈希 + 存储定位 + artifact_id + 数据类型。
#
# 关键不变式：缓存恢复必须对下游 input_hash 透明 —— 同一份上游产物，无论这次是
# 「新鲜计算」（dispatcher 经 StudyOutputSummary.to_dict() 生成 data_info/artifact）
# 还是「命中缓存恢复」（cache.py 重建 data_info/artifact），算出的签名必须完全一致；
# 否则只要上游命中缓存，紧邻下游的 input_hash 就漂移、必然 cache miss 一次。
#
# 两条路径在「溯源 / 来源 / 表示层」字段上并不逐字段一致（实测漂移点）：
#   - data_info.processing：缓存恢复时被注入 cached=True（新鲜运行没有）；
#   - artifact.artifact_type / source_dataset_id：to_dict() 带，_register_artifact_references 不带。
# 这些都不是数据内容 —— 内容身份由 content_hash/sha256 + 存储路径 + artifact_id 唯一确定。
# 故签名一律排除这些字段，既消除漂移、又不会误命中（不同内容 → 不同 sha256）。


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
        # 刻意不含 "processing"：溯源元数据，缓存恢复路径与新鲜路径不一致（见上）。
    )
    return {key: data_info.get(key) for key in keys if key in data_info}


def _artifact_signature(artifact: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "content_hash",
        "checksum",
        "artifact_id",
        "storage_path",
        "data_type",
        # 刻意不含 "artifact_type"（恒为 "derivative"、无区分度）与 "source_dataset_id"
        # （溯源字段，缓存恢复路径不填）：两者会让 fresh/cached 的 artifact 签名漂移（见上）。
    )
    return {key: artifact.get(key) for key in keys if key in artifact}


def _getattr_or_item(value: Any, key: str, default: Any) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)
