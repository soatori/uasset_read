"""Asset handlers — domain-specific enrichments for package objects.

The AssetHandler protocol defines how domain extractors add semantic
extensions to ObjectRecord instances. Handlers are registered by class
name and invoked lazily when depth >= asset.
"""

from __future__ import annotations

from typing import Any, Protocol

from uasset_read.models.object_model import ObjectRecord
from uasset_read.versioning import VersionContext


class AssetHandler(Protocol):
    """Domain handler that enriches an object with semantic data.

    Handlers may declare a capability tier via a ``capability`` member:
    either a plain ``"summary"``/``"decoded"`` string, or a callable of the
    produced result for handlers whose tier depends on the data actually
    found. Undeclared handlers are summary-tier: only decoded-tier output
    may yield ``status.semantic = "complete"`` (#629).
    """

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool: ...

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None: ...
