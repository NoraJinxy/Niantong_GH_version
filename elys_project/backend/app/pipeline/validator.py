"""
Purpose: Implement workflow/Pipeline runtime support for validator, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

from typing import Any

from app.pipeline.dispatcher import NodeDispatcher, NodeExecutorNotImplemented
from app.pipeline.registry import get_node_registry
from app.schemas.pipeline import PipelineValidationIssue, PipelineValidationResponse


WILDCARD_PORT_TYPES = {"*", "any", "", None}


def port_types_compatible(source_type: str | None, target_type: str | None) -> bool:
    if source_type in WILDCARD_PORT_TYPES or target_type in WILDCARD_PORT_TYPES:
        return True
    if source_type == target_type:
        return True
    compatible_targets = {
        "analysis_result": {"analysis_result", "evoked", "epochs", "psd", "tfr", "connectivity", "microstate", "source_estimate"},
        "eeg_data": {"eeg_data", "raw", "dataset_collection"},
        # 频谱类输入(PSD/将来 TFR)同时接受连续数据与 Epochs,故既收 eeg_data 也收 epochs。
        "spectral_source": {"spectral_source", "eeg_data", "raw", "dataset_collection", "epochs"},
    }
    return bool(source_type and target_type and source_type in compatible_targets.get(target_type, set()))


def is_all_or_list(value: Any) -> bool:
    return value == "all" or isinstance(value, list)


def validate_load_data_params(
    params: dict[str, Any],
    issues: list[PipelineValidationIssue],
    node_id: str,
    node_type: str,
) -> None:
    selection_mode = params.get("selection_mode", "filter")
    if selection_mode not in {"filter", "explicit"}:
        issues.append(
            PipelineValidationIssue(
                code="LOAD_DATA_SELECTION_MODE_INVALID",
                message="LoadData.selection_mode 必须是 filter 或 explicit",
                node_id=node_id,
                node_type=node_type,
            )
        )

    dataset_filter = params.get("dataset_filter")
    if not isinstance(dataset_filter, dict):
        issues.append(
            PipelineValidationIssue(
                code="LOAD_DATA_FILTER_INVALID",
                message="LoadData.dataset_filter 必须是对象",
                node_id=node_id,
                node_type=node_type,
            )
        )
    else:
        for key in ("subjects", "sessions", "tasks", "runs", "qa_status"):
            if key in dataset_filter and not is_all_or_list(dataset_filter[key]):
                issues.append(
                    PipelineValidationIssue(
                        code="LOAD_DATA_FILTER_FIELD_INVALID",
                        message=f"LoadData.dataset_filter.{key} 必须是 all 或数组",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
        if "require_fif" in dataset_filter and not isinstance(dataset_filter["require_fif"], bool):
            issues.append(
                PipelineValidationIssue(
                    code="LOAD_DATA_REQUIRE_FIF_INVALID",
                    message="LoadData.dataset_filter.require_fif 必须是布尔值",
                    node_id=node_id,
                    node_type=node_type,
                )
            )

    dataset_ids = params.get("dataset_ids", [])
    if selection_mode == "explicit" and not (isinstance(dataset_ids, list) and dataset_ids):
        issues.append(
            PipelineValidationIssue(
                code="LOAD_DATA_DATASET_IDS_REQUIRED",
                message="LoadData 固定数据集模式至少需要选择一个 dataset_id",
                node_id=node_id,
                node_type=node_type,
            )
        )
    if dataset_ids and not isinstance(dataset_ids, list):
        issues.append(
            PipelineValidationIssue(
                code="LOAD_DATA_DATASET_IDS_INVALID",
                message="LoadData.dataset_ids 必须是数组",
                node_id=node_id,
                node_type=node_type,
            )
        )


def _effective_params(spec: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """合并属性默认值 + 用户实参，供 visible_when 判定（控制字段没显式给时用默认值）。"""
    effective: dict[str, Any] = {}
    for prop in spec.get("properties", []):
        if "default" in prop:
            effective[prop["name"]] = prop.get("default")
    for key, value in (params or {}).items():
        if value not in (None, ""):
            effective[key] = value
    return effective


def _property_visible(prop: dict[str, Any], effective_params: dict[str, Any]) -> bool:
    """visible_when: {控制字段: [允许值,...]}，全部命中才显示；无 visible_when 视为永远显示。"""
    rules = prop.get("visible_when")
    if not isinstance(rules, dict):
        return True
    for key, allowed in rules.items():
        allowed_list = allowed if isinstance(allowed, list) else [allowed]
        if effective_params.get(key) not in allowed_list:
            return False
    return True


def validate_filter_params(
    params: dict[str, Any],
    issues: list[PipelineValidationIssue],
    node_id: str,
    node_type: str,
) -> None:
    filter_type = str(params.get("filter_type") or "bandpass")
    if filter_type not in {"bandpass", "highpass", "lowpass", "notch"}:
        issues.append(
            PipelineValidationIssue(
                code="FILTER_TYPE_INVALID",
                message="filter_type 必须是 bandpass / highpass / lowpass / notch",
                node_id=node_id,
                node_type=node_type,
            )
        )
        return
    method = str(params.get("method") or "fir")
    if method == "spectrum_fit" and filter_type != "notch":
        issues.append(
            PipelineValidationIssue(
                code="FILTER_METHOD_INVALID",
                message="谱拟合(spectrum_fit) 仅适用于工频陷波(notch)",
                node_id=node_id,
                node_type=node_type,
            )
        )
    if filter_type == "bandpass":
        l_freq = params.get("l_freq")
        h_freq = params.get("h_freq")
        try:
            if l_freq not in (None, "") and h_freq not in (None, "") and float(l_freq) >= float(h_freq):
                issues.append(
                    PipelineValidationIssue(
                        code="FILTER_BAND_INVALID",
                        message="带通要求低截止 < 高截止",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
        except (TypeError, ValueError):
            pass


def topological_node_order(definition_json: dict[str, Any]) -> list[dict[str, Any]]:
    """返回需要执行的节点（拓扑顺序）。

    只包含"从某个 source 节点 (LoadData) BFS 可达"的节点 —— 游离节点（孤立 / 没有上游链路通到
    数据源）会被跳过，由 validator 给一条 NODE_DETACHED warning 提示用户。
    """
    graph = definition_json.get("graph") or {}
    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    if not isinstance(nodes, list):
        return []
    if not isinstance(links, list):
        links = []

    node_by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict) and node.get("id")}
    incoming = {node_id: 0 for node_id in node_by_id}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_by_id}
    for link in links:
        if not isinstance(link, dict):
            continue
        src = (link.get("from") or {}).get("node")
        dst = (link.get("to") or {}).get("node")
        if src in node_by_id and dst in node_by_id:
            incoming[dst] += 1
            outgoing[src].append(dst)

    # source = spec 无 required input 的节点（主要是 LoadData）。
    # 关键：孤立节点（有必需输入却没连线）incoming 也是 0，但绝不能当 source —— 否则它会把自己
    # 拉进执行集合，运行时因「没有上游输入」失败、还把整条 pipeline 拖垮（正是用户碰到的 bug）。
    # 与 validate_definition 的可达性同口径（都按 spec 是否有必需输入），保证「校验说跳过」与「执行真跳过」一致。
    registry = get_node_registry()

    def _is_source_node(node_id: str) -> bool:
        spec = registry.get(str(node_by_id[node_id].get("type") or "")) or {}
        inputs = spec.get("inputs", [])
        return (not inputs) or all(not port.get("required", True) for port in inputs)

    # 从 source BFS 找可达集合（不可达的孤立节点不进执行集合，由 validate_definition 给 NODE_DETACHED 提示）
    sources = [nid for nid in node_by_id if _is_source_node(nid)]
    reachable: set[str] = set(sources)
    bfs = list(sources)
    while bfs:
        cur = bfs.pop(0)
        for nxt in outgoing.get(cur, []):
            if nxt not in reachable:
                reachable.add(nxt)
                bfs.append(nxt)

    # 只在可达集合内做拓扑排序 —— 游离节点（不在 reachable 里）不进 ordered
    incoming_reachable = {nid: incoming[nid] for nid in reachable}
    queue = [nid for nid, count in incoming_reachable.items() if count == 0]
    ordered: list[dict[str, Any]] = []
    while queue:
        current = queue.pop(0)
        ordered.append(node_by_id[current])
        for dst in outgoing[current]:
            if dst not in reachable:
                continue
            incoming_reachable[dst] -= 1
            if incoming_reachable[dst] == 0:
                queue.append(dst)
    # 环检测失败时（不应出现）退回所有可达节点的任意顺序
    if len(ordered) != len(reachable):
        return [node_by_id[nid] for nid in reachable if nid in node_by_id]
    return ordered


def validate_definition(
    definition_json: dict[str, Any],
    *,
    db: Any | None = None,
    study: Any | None = None,
) -> PipelineValidationResponse:
    registry = get_node_registry()
    dispatcher = NodeDispatcher()
    issues: list[PipelineValidationIssue] = []
    graph = definition_json.get("graph") if isinstance(definition_json, dict) else None
    if not isinstance(graph, dict):
        return PipelineValidationResponse(
            valid=False,
            errors=[PipelineValidationIssue(code="GRAPH_MISSING", message="definition_json.graph 缺失")],
            warnings=[],
        )

    nodes = graph.get("nodes")
    links = graph.get("links", [])
    if not isinstance(nodes, list):
        issues.append(PipelineValidationIssue(code="NODES_INVALID", message="graph.nodes 必须是数组"))
        nodes = []
    if not isinstance(links, list):
        issues.append(PipelineValidationIssue(code="LINKS_INVALID", message="graph.links 必须是数组"))
        links = []
    if not nodes:
        issues.append(PipelineValidationIssue(code="NODES_EMPTY", message="工作流至少需要一个节点"))

    node_ids: set[str] = set()
    node_types: dict[str, str] = {}
    node_specs: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        if not node_id:
            issues.append(PipelineValidationIssue(code="NODE_ID_MISSING", message="节点缺少 id"))
            continue
        if node_id in node_ids:
            issues.append(PipelineValidationIssue(code="NODE_ID_DUPLICATE", message=f"节点 id 重复: {node_id}", node_id=node_id))
        node_ids.add(node_id)
        node_types[node_id] = node_type
        spec = registry.get(node_type)
        if spec is None:
            issues.append(
                PipelineValidationIssue(
                    code="NODE_SPEC_NOT_FOUND",
                    message=f"未知节点类型: {node_type}",
                    node_id=node_id,
                    node_type=node_type,
                )
            )
            continue
        node_specs[node_id] = spec
        if not dispatcher.supports(node_type):
            issues.append(
                PipelineValidationIssue(
                    **NodeExecutorNotImplemented(
                        node_id=node_id,
                        node_type=node_type,
                        title=str(spec.get("title") or node_type),
                    ).to_issue()
                )
            )

        params = node.get("params") or {}
        if not isinstance(params, dict):
            issues.append(
                PipelineValidationIssue(
                    code="PARAMS_INVALID",
                    message=f"{spec['title']} params 必须是对象",
                    node_id=node_id,
                    node_type=node_type,
                )
            )
            params = {}
        effective_params = _effective_params(spec, params)
        for prop in spec.get("properties", []):
            if not _property_visible(prop, effective_params):
                continue
            if prop.get("required") and params.get(prop["name"]) in (None, ""):
                issues.append(
                    PipelineValidationIssue(
                        code="PARAM_REQUIRED",
                        message=f"{spec['title']} 缺少必填参数: {prop['name']}",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
        if node_type == "eeg/data/load" and isinstance(params, dict):
            validate_load_data_params(params, issues, node_id, node_type)
            if db is not None and study is not None:
                from app.pipeline.load_data import resolve_load_data_selection

                resolved = resolve_load_data_selection(
                    db=db,
                    study=study,
                    params=params,
                    node_id=node_id,
                    node_type=node_type,
                )
                issues.extend(resolved.errors)
                issues.extend(resolved.warnings)
        if node_type == "eeg/filter/apply" and isinstance(params, dict):
            validate_filter_params(params, issues, node_id, node_type)

    incoming: dict[str, int] = {node_id: 0 for node_id in node_ids}
    incoming_ports: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for link in links:
        link_from = link.get("from") or {}
        link_to = link.get("to") or {}
        src = link_from.get("node")
        dst = link_to.get("node")
        src_port = link_from.get("port")
        dst_port = link_to.get("port")
        if src not in node_ids or dst not in node_ids:
            issues.append(PipelineValidationIssue(code="LINK_NODE_MISSING", message="连线引用了不存在的节点"))
            continue
        src_spec = node_specs.get(src)
        dst_spec = node_specs.get(dst)
        if src_spec and dst_spec:
            output_ports = {port["name"]: port for port in src_spec.get("outputs", [])}
            input_ports = {port["name"]: port for port in dst_spec.get("inputs", [])}
            output_port = output_ports.get(src_port)
            input_port = input_ports.get(dst_port)
            if output_port is None:
                issues.append(
                    PipelineValidationIssue(
                        code="LINK_OUTPUT_PORT_MISSING",
                        message=f"连线引用了不存在的输出端口: {src_port}",
                        node_id=src,
                        node_type=node_types.get(src),
                    )
                )
                continue
            if input_port is None:
                issues.append(
                    PipelineValidationIssue(
                        code="LINK_INPUT_PORT_MISSING",
                        message=f"连线引用了不存在的输入端口: {dst_port}",
                        node_id=dst,
                        node_type=node_types.get(dst),
                    )
                )
                continue
            if not port_types_compatible(output_port.get("type"), input_port.get("type")):
                issues.append(
                    PipelineValidationIssue(
                        code="LINK_PORT_TYPE_MISMATCH",
                        message=f"端口类型不匹配: {output_port.get('type')} -> {input_port.get('type')}",
                        node_id=dst,
                        node_type=node_types.get(dst),
                    )
                )
                continue
        incoming[dst] += 1
        if dst_port:
            incoming_ports[dst].add(str(dst_port))
        outgoing[src].append(dst)

    # 找 source 节点（没有任何 required input 的节点 —— 主要是 LoadData）。
    # 从 source 出发 BFS，得到"主链路可达节点集合"。游离节点（不在集合里）的缺输入
    # 不再阻断校验 —— 用户的预期：从 LoadData 走得通就够了，其它孤立节点最多 warning。
    source_node_ids: set[str] = set()
    for nid, spec in node_specs.items():
        inputs = spec.get("inputs", [])
        if not inputs or all(not p.get("required", True) for p in inputs):
            source_node_ids.add(nid)

    reachable: set[str] = set(source_node_ids)
    bfs_queue = list(source_node_ids)
    while bfs_queue:
        cur = bfs_queue.pop(0)
        for nxt in outgoing.get(cur, []):
            if nxt not in reachable:
                reachable.add(nxt)
                bfs_queue.append(nxt)

    detached_warned: set[str] = set()
    for node_id, spec in node_specs.items():
        if node_id in reachable:
            # 主链路上的节点：必需输入缺失 = error
            for port in spec.get("inputs", []):
                if port.get("required", True) and port.get("name") not in incoming_ports[node_id]:
                    issues.append(
                        PipelineValidationIssue(
                            code="INPUT_REQUIRED",
                            message=f"{spec['title']} 缺少必需输入: {port['name']}",
                            node_id=node_id,
                            node_type=node_types.get(node_id),
                        )
                    )
        else:
            # 游离节点：每节点一条 warning，不阻断校验
            if node_id in detached_warned:
                continue
            detached_warned.add(node_id)
            issues.append(
                PipelineValidationIssue(
                    code="NODE_DETACHED",
                    severity="warning",
                    message=f"{spec['title']} 未连入主链路（从 LoadData 不可达），运行时会跳过",
                    node_id=node_id,
                    node_type=node_types.get(node_id),
                )
            )

    # 注：旧 P4 软提示「Bad Channels 插值/RANSAC 缺上游 Ch Loc Assign」已移除——
    # 电极坐标现由「导入转 FIF 时自动绑定 montage」提供（见 engine/preprocess/montage_autobind），
    # 流水线默认不再接 Ch Loc 节点，该 graph 级提示在标准链路上恒误报。坐标真缺失（非标准命名
    # 且未上传自定义电极文件）由运行时 bad_channels 的精确报错兜底，导入 provenance.montageAutobind 可查。

    # 拓扑排序判环：用 incoming 副本，避免影响上面的 incoming_ports
    incoming_copy = dict(incoming)
    queue = [node_id for node_id, count in incoming_copy.items() if count == 0]
    visited: list[str] = []
    while queue:
        current = queue.pop(0)
        visited.append(current)
        for dst in outgoing[current]:
            incoming_copy[dst] -= 1
            if incoming_copy[dst] == 0:
                queue.append(dst)
    if len(visited) != len(node_ids):
        issues.append(PipelineValidationIssue(code="PIPELINE_CYCLE", message="工作流中存在环"))

    return PipelineValidationResponse(
        valid=not any(issue.severity == "error" for issue in issues),
        errors=[issue for issue in issues if issue.severity == "error"],
        warnings=[issue for issue in issues if issue.severity == "warning"],
    )
