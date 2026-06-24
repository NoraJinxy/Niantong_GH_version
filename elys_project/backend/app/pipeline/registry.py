"""
Purpose: Implement workflow/Pipeline runtime support for registry, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class NodeRegistry:
    """Load and validate workflow NodeSpec JSON files."""

    def __init__(self, node_dir: Path | None = None):
        self.node_dir = node_dir or Path(__file__).parent / "nodes"
        self._specs: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        specs: dict[str, dict[str, Any]] = {}
        for path in sorted(self.node_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                spec = json.load(handle)
            self._validate_spec(spec, path)
            node_type = spec["type"]
            if node_type in specs:
                raise ValueError(f"Duplicate node type: {node_type}")
            specs[node_type] = spec
        self._specs = specs

    def list_specs(self, *, phase: str | None = None) -> list[dict[str, Any]]:
        values = list(self._specs.values())
        if phase:
            values = [spec for spec in values if spec.get("phase") == phase]
        return values

    def get(self, node_type: str) -> dict[str, Any] | None:
        return self._specs.get(node_type)

    @staticmethod
    def _validate_spec(spec: dict[str, Any], path: Path) -> None:
        required = ("schema_version", "type", "title", "category", "phase", "outputs", "backend")
        missing = [key for key in required if key not in spec]
        if missing:
            raise ValueError(f"{path.name}: missing required fields: {', '.join(missing)}")
        if "/" not in spec["type"]:
            raise ValueError(f"{path.name}: node type must be namespaced")
        if spec["phase"] not in {"phase1", "phase2", "phase3"}:
            raise ValueError(f"{path.name}: invalid phase {spec['phase']}")

        property_names: set[str] = set()
        for prop in spec.get("properties", []):
            name = prop.get("name")
            if not name:
                raise ValueError(f"{path.name}: property name is required")
            if name in property_names:
                raise ValueError(f"{path.name}: duplicate property {name}")
            property_names.add(name)
            prop.setdefault("hash", True)


@lru_cache()
def get_node_registry() -> NodeRegistry:
    return NodeRegistry()

