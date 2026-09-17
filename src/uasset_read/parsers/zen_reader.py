"""ZenPackageReader — explicit availability boundary for Zen/IoStore packages.

The committed suite contains no real Zen-layout package payload (fixture
limit): full name/import/export/payload decoding is a separate follow-up whose
entry condition is a redistributable package fixture plus a concrete
package/chunk selection API. This module therefore never invents empty
objects or a Legacy document from Zen/container bytes — it validates the
inputs and returns an explicit ``ZenReadResult(status="unavailable")`` with a
bounded diagnostic.

Zen summary layout facts (``AsyncLoading2.h:302-316``) live here only; legacy
code must not import Zen-only structs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from uasset_read.containers import ContainerReport
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.models.document import PackageDocument
from uasset_read.versioning import VersionContext


@dataclass
class ZenReadResult:
    document: PackageDocument | None
    diagnostics: list[Diagnostic]
    status: Literal["unavailable"]
    reason: str | None = None


def _diag(code: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity="warning",
        code=code,
        message=message,
        stage="zen.read",
    )


class ZenPackageReader:
    """Reader entry for Zen packages; currently the explicit unavailable boundary."""

    def read_from_container(
        self,
        report: ContainerReport,
        package_id: str,
        *,
        depth: str = "package",
        chunk_source=None,
        context: VersionContext | None = None,
    ) -> ZenReadResult:
        """Attempt a Zen package read from container metadata.

        Always returns an unavailable result for now: without concrete chunk
        bytes (or a committed Zen package fixture) there is nothing honest to
        decode. Never fabricates a document.
        """
        _ = depth, context  # reserved for the follow-up real-fixture task
        diagnostics: list[Diagnostic] = [
            Diagnostic(
                severity="warning",
                code="ZEN_PACKAGE_FIXTURE_UNAVAILABLE",
                message=(
                    "no redistributable Zen package payload is committed; "
                    "full Zen decoding is deferred to a follow-up task"
                ),
                stage="zen.read",
            )
        ]
        reason = "zen_package_fixture_unavailable"
        if chunk_source is None:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="ZEN_CHUNK_BYTES_UNAVAILABLE",
                    message=(
                        f"chunk bytes for package_id={package_id!r} are not available; "
                        "IoStore chunk extraction is not implemented"
                    ),
                    stage="zen.read",
                )
            )
            reason = "chunk_bytes_unavailable"
        if not package_id:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="ZEN_PACKAGE_ID_MISSING",
                    message="a concrete package_id is required for a Zen read",
                    stage="zen.read",
                )
            )
        # Carry container-level diagnostics so callers see the full boundary.
        diagnostics.extend(report.diagnostics)
        return ZenReadResult(
            document=None,
            diagnostics=diagnostics,
            status="unavailable",
            reason=reason,
        )
