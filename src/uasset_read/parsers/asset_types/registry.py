"""Single owner for asset-handler registration and domain dispatch.

Handler *classes* stay in ``handlers_impl``; they import only
``register_handler`` from this module. Every in-tree caller of
``run_handlers`` / ``get_handlers`` / ``_HANDLERS`` must use this module —
``handlers_impl`` must not re-own the registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ...models.diagnostics import Diagnostic, make_diagnostic
from ...models.object_model import CoverageEntry, ObjectRecord

# Loaded once on first dispatch so importing this module alone does not
# pull every handler class; ``handlers_impl`` registers on import.
_handlers_loaded = False


@dataclass
class DomainResult:
    status: Literal["complete", "partial", "unavailable", "not_requested"]
    semantic: dict[str, Any] | None = None
    coverage: list[CoverageEntry] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    reason: str | None = None


class _SupportsClasses:
    """Mixin: matches export class names listed in ``classes``."""

    classes: tuple[str, ...] = ()

    def supports(self, obj: ObjectRecord, depth: str) -> bool:
        return (obj.class_name or "") in self.classes


_HANDLERS: list[Any] = []


def _ensure_loaded() -> None:
    global _handlers_loaded
    if _handlers_loaded:
        return
    _handlers_loaded = True
    from uasset_read.parsers.asset_types import handlers_impl  # noqa: F401


def register_handler(handler: Any) -> None:
    """Append a handler instance to the single global registry."""
    _HANDLERS.append(handler)


def get_handlers() -> list[Any]:
    """Return the live handler list (mutation is how tests isolate)."""
    _ensure_loaded()
    return _HANDLERS


def run_handlers(
    obj: ObjectRecord,
    depth: str,
    all_objects: list[ObjectRecord],
    package_data: Any,
) -> DomainResult:
    """Run all matching handlers on one object.

    Handler failure only affects this object — no propagation.
    ``status`` is bound to the capability tier: ``complete`` only when a
    decoded-tier handler produced output; summary-tier results and failures
    stay ``partial`` (#629). No matching handler is ``not_requested``.
    """
    _ensure_loaded()
    semantic: dict[str, Any] = {}
    coverage: list[CoverageEntry] = []
    diagnostics: list[Diagnostic] = []
    matched = False
    failed = False
    decoded = False

    for handler in _HANDLERS:
        try:
            if handler.supports(obj, depth):
                matched = True
                result = handler.enrich(obj, depth, all_objects, package_data)
                if result is not None:
                    semantic.update(result)
                    cap = getattr(handler, "capability", "summary")
                    tier = str(cap(result)) if callable(cap) else str(cap)
                    if tier == "decoded":
                        decoded = True
        except Exception as e:
            matched = True
            failed = True
            handler_name = type(handler).__name__
            coverage.append(
                CoverageEntry(
                    feature=f"handler.{handler_name}",
                    status="missing",
                    detail=f"Handler error: {e}",
                )
            )
            diagnostics.append(
                make_diagnostic(
                    code="HANDLER_FAILURE",
                    message=f"{handler_name} failed for {obj.id}: {e}",
                    stage="semantic.handler",
                    object_id=obj.id,
                )
            )

    if not matched:
        return DomainResult(
            status="not_requested",
            semantic=None,
            coverage=coverage,
            diagnostics=diagnostics,
            reason="no_domain_decoder",
        )

    obj.status.semantic = "complete" if (decoded and not failed) else "partial"
    status: Literal["complete", "partial", "unavailable", "not_requested"] = (
        "complete" if (decoded and not failed) else "partial"
    )
    if failed and not decoded:
        status = "partial"
    return DomainResult(
        status=status,
        semantic=semantic or None,
        coverage=coverage,
        diagnostics=diagnostics,
        reason=None,
    )
