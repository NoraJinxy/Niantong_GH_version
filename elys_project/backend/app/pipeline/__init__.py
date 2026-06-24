"""
Purpose: Implement workflow/Pipeline runtime support for __init__, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from .registry import NodeRegistry, get_node_registry

__all__ = ["NodeRegistry", "get_node_registry"]

