"""Blueprint semantic IDs — readable URIs, ASCII slugs, endpoint IDs (BP-§5)."""
from __future__ import annotations

import re

GRAPH_ID_RE = r"blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*"
NODE_ID_RE = r"blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*/node/[a-z][a-z0-9-]*/[A-Za-z][A-Za-z0-9_.-]*/[0-9]+"
ENDPOINT_RE = r"(input|output|exec)\.[A-Za-z][A-Za-z0-9_.-]*"

_SLUG_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_KIND_RE = re.compile(r"[^a-z0-9-]+")


def ascii_slug(name: str) -> str:
    """ASCII slug preserving case; invalid runs collapse to '_'."""
    slug = _SLUG_RE.sub("_", name or "").strip("_")
    if not slug:
        return "unnamed"
    if not slug[0].isalpha():
        slug = "x" + slug
    return slug


def kind_slug(kind: str) -> str:
    """Lowercase slug for the <Kind> node-ID segment."""
    slug = _KIND_RE.sub("-", (kind or "").lower()).strip("-")
    return slug or "custom"


def graph_id(graph_slug: str) -> str:
    return f"blueprint://graph/{graph_slug}"


def node_id(graph_slug: str, kind: str, name_slug: str, ordinal: int) -> str:
    return f"blueprint://graph/{graph_slug}/node/{kind_slug(kind)}/{name_slug}/{ordinal}"


def data_endpoint(pin_name: str, direction: str) -> str:
    """direction: ``input`` or ``output`` (graph direction, BP-§8)."""
    return f"{direction}.{ascii_slug(pin_name)}"


_EXEC_ROLE_MAP = {"execute": "in", "then": "out"}


def exec_endpoint(pin_name: str) -> str:
    """Canonical exec role: execute->in, then->out, else lowercased slug."""
    role = _EXEC_ROLE_MAP.get((pin_name or "").lower())
    if role is None:
        role = ascii_slug(pin_name).lower().replace("_", "-") or "port"
    return f"exec.{role}"
