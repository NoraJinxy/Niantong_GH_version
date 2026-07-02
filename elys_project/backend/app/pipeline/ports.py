"""
Purpose: Helpers for workflow port aliases used by one_or_many inputs.
Related: app/pipeline/validator.py, app/pipeline/executor.py, frontend pipeline dynamic ports.
"""

from __future__ import annotations

import re
from typing import Any


_EXPANDED_INPUT_RE = re.compile(r"^(?P<base>.+)_(?P<index>[2-9][0-9]*)$")


def input_port_by_name(spec: dict[str, Any] | None, port_name: str | None) -> dict[str, Any] | None:
    """Resolve an input port by exact name or by expandable alias like input_2.

    NodeSpec keeps the canonical port name (`input`). Older drafts may contain
    `input_2`, `input_3`, ... aliases from a previous visual expansion model.
    Runtime/validation treats those aliases as the same canonical port when the
    base input has cardinality one_or_many.
    """
    if not spec or not port_name:
        return None
    inputs = spec.get("inputs", []) if isinstance(spec, dict) else []
    ports = {str(port.get("name") or ""): port for port in inputs if isinstance(port, dict)}
    if port_name in ports:
        return ports[port_name]
    base = expanded_input_base_name(spec, port_name)
    if base:
        return ports.get(base)
    return None


def canonical_input_port_name(spec: dict[str, Any] | None, port_name: str | None) -> str:
    """Return the NodeSpec canonical input name for an expandable alias."""
    name = str(port_name or "input")
    base = expanded_input_base_name(spec, name)
    return base or name


def expanded_input_base_name(spec: dict[str, Any] | None, port_name: str | None) -> str | None:
    """Return base port name for aliases such as input_2, or None if invalid."""
    if not spec or not port_name:
        return None
    match = _EXPANDED_INPUT_RE.match(str(port_name))
    if not match:
        return None
    base = match.group("base")
    inputs = spec.get("inputs", []) if isinstance(spec, dict) else []
    for port in inputs:
        if not isinstance(port, dict):
            continue
        if str(port.get("name") or "") == base and str(port.get("cardinality") or "") == "one_or_many":
            return base
    return None
