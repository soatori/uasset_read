"""Animation Blueprint semantic IDs — readable URIs and pose endpoint IDs.

Slug/endpoint primitives are shared with the Blueprint module; only the
URI builders and the pose endpoint are animation-specific.
"""

from __future__ import annotations

from uasset_read.semantic.blueprint.ids import (
    ascii_slug,
    data_endpoint,
    exec_endpoint,
    kind_slug,
)

__all__ = [
    "ascii_slug",
    "data_endpoint",
    "exec_endpoint",
    "kind_slug",
    "graph_id",
    "node_id",
    "state_machine_id",
    "state_id",
    "pose_endpoint",
]


def graph_id(graph_slug: str) -> str:
    return f"animblueprint://graph/{graph_slug}"


def node_id(graph_slug: str, kind: str, name_slug: str, ordinal: int) -> str:
    return f"animblueprint://graph/{graph_slug}/node/{kind_slug(kind)}/{name_slug}/{ordinal}"


def state_machine_id(slug: str) -> str:
    return f"animblueprint://state_machine/{slug}"


def state_id(machine_slug: str, state_slug: str) -> str:
    return f"animblueprint://state_machine/{machine_slug}/state/{state_slug}"


def pose_endpoint(pin_name: str, direction: str) -> str:
    """Pose endpoint for animation pose connections."""
    return f"pose.{direction}.{ascii_slug(pin_name)}"
