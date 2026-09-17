"""Container classification for ``.utoc`` / ``.pak`` inputs.

``inspect_container`` reports *what a container is* and *which capabilities are
available* — it never extracts bytes. TOC parsing is delegated to
:mod:`uasset_read.iostore` (no second TOC parser lives here), and traditional
FPak entry extraction stays unavailable until a redistributable traditional
FPak fixture and a separate evidence-backed task exist (ORIGIN-issue-625).

Classification follows container context plus structural checks: the file
extension picks the family, the IoStore TOC magic confirms ``.utoc``
identity, a co-located sibling ``.utoc`` (same stem, valid TOC magic)
classifies a ``.pak`` as an IoStore wrapper, and the trailing
``FPakInfo::PAK_FILE_MAGIC`` footer marks a traditional pak when no IoStore
context applies. No single invented byte tag decides Zen-ness.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from uasset_read.iostore import (
    TOC_HEADER_SIZE,
    TOC_MAGIC,
    IoStoreTocError,
    read_toc,
)
from uasset_read.models.diagnostics import Diagnostic

# FPakInfo::PAK_FILE_MAGIC (UE), little-endian. Searched only in the file
# tail, where FPakFile keeps its footer — not treated as a container-wide tag.
_FPAK_MAGIC = (0x5A6F12E1).to_bytes(4, "little")
_FPAK_FOOTER_PROBE = 4096

Capability = Literal["available", "unavailable"]


@dataclass(frozen=True)
class ContainerEntry:
    entry_id: str
    offset: int
    size: int
    compression: str | None = None


@dataclass
class ContainerReport:
    kind: Literal["traditional_pak", "iostore_wrapper", "iostore", "unknown"]
    path: str
    entry_count: int
    entries: list[ContainerEntry]
    capabilities: dict[str, Capability]
    diagnostics: list[Diagnostic]


def _diag(code: str, message: str) -> Diagnostic:
    return Diagnostic(code=code, stage="container.inspect", message=message, severity="warning")


def _has_toc_magic(path: Path) -> bool:
    """Structural sibling check: does ``path`` open with the IoStore TOC magic?"""
    try:
        with path.open("rb") as fh:
            return fh.read(len(TOC_MAGIC)) == TOC_MAGIC
    except OSError:
        return False


def _unknown(path: Path, code: str, message: str) -> ContainerReport:
    return ContainerReport(
        kind="unknown",
        path=str(path),
        entry_count=0,
        entries=[],
        capabilities={},
        diagnostics=[_diag(code, message)],
    )


def _inspect_utoc(path: Path) -> ContainerReport:
    try:
        with path.open("rb") as fh:
            header = fh.read(TOC_HEADER_SIZE)
    except OSError as exc:
        return _unknown(path, "CONTAINER_UNREADABLE", f"{path.name}: {exc}")
    if len(header) < TOC_HEADER_SIZE or header[: len(TOC_MAGIC)] != TOC_MAGIC:
        return _unknown(path, "CONTAINER_NOT_TOC", f"{path.name}: missing IoStore TOC magic")

    try:
        toc = read_toc(path)
    except IoStoreTocError as exc:
        # iostore.read_toc refuses encrypted containers before parsing; match
        # its refusal text so the missing-key case keeps a stable code.
        code = "ENCRYPTION_KEY_MISSING" if "encrypted container" in str(exc) else "CONTAINER_TOC_UNREADABLE"
        return ContainerReport(
            kind="iostore",
            path=str(path),
            entry_count=0,
            entries=[],
            capabilities={"toc_entries": "unavailable", "chunk_bytes": "unavailable"},
            diagnostics=[_diag(code, str(exc))],
        )

    entries = [ContainerEntry(entry_id, offset, size, compression) for entry_id, offset, size, compression in toc.iter_entries()]
    diagnostics = [
        _diag(
            "CHUNK_BYTES_UNAVAILABLE",
            "chunk byte extraction is not implemented; sibling .ucas is treated as absent "
            "for the blocking suite and no IoStoreChunkSource exists yet",
        )
    ]
    if any(chunk.compressed for chunk in toc.chunks):
        diagnostics.append(
            _diag(
                "COMPRESSION_UNAVAILABLE",
                f"container declares compression methods {list(toc.compression_methods[1:])}; "
                "no decompression codec is bundled",
            )
        )
    return ContainerReport(
        kind="iostore",
        path=str(path),
        entry_count=toc.entry_count,
        entries=entries,
        capabilities={"toc_entries": "available", "chunk_bytes": "unavailable"},
        diagnostics=diagnostics,
    )


def _inspect_pak(path: Path) -> ContainerReport:
    sibling_toc = path.with_suffix(".utoc")
    if sibling_toc.is_file() and _has_toc_magic(sibling_toc):
        # Container context: a same-stem IoStore TOC is co-located, so this
        # pak belongs to an IoStore container set (ORIGIN-issue-625) and is
        # classified as the wrapper. Traditional FPak entry extraction is
        # refused deliberately — no PakEntrySource exists without a
        # fixture-validated task.
        return ContainerReport(
            kind="iostore_wrapper",
            path=str(path),
            entry_count=0,
            entries=[],
            capabilities={"traditional_pak_entries": "unavailable", "chunk_bytes": "unavailable"},
            diagnostics=[
                _diag(
                    "CHUNK_BYTES_UNAVAILABLE",
                    "IoStore chunk bytes are not extractable from this wrapper; "
                    "chunk extraction is deferred with the TOC body unavailable",
                )
            ],
        )

    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            fh.seek(max(0, size - _FPAK_FOOTER_PROBE))
            tail = fh.read(_FPAK_FOOTER_PROBE)
    except OSError as exc:
        return _unknown(path, "CONTAINER_UNREADABLE", f"{path.name}: {exc}")
    if _FPAK_MAGIC in tail:
        # Structural FPak footer without IoStore context: classified honestly,
        # but entry extraction still has no validated implementation.
        return ContainerReport(
            kind="traditional_pak",
            path=str(path),
            entry_count=0,
            entries=[],
            capabilities={"traditional_pak_entries": "unavailable"},
            diagnostics=[
                _diag(
                    "TRADITIONAL_PAK_ENTRIES_UNAVAILABLE",
                    "FPak footer present but PakEntrySource extraction is not implemented",
                )
            ],
        )
    return _unknown(
        path,
        "CONTAINER_UNRECOGNIZED",
        f"{path.name}: neither a sibling IoStore TOC nor an FPak footer was found",
    )


def inspect_container(path: Path) -> ContainerReport:
    """Classify pak/iostore/unknown, count entries, report capabilities + diagnostics.

    Required by tests/test_containers.py. Wraps existing iostore.py TOC
    iteration; does not invent Traditional Pak extraction without an FPak
    fixture, and never falls back to a Legacy parse of container bytes.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".utoc":
        return _inspect_utoc(path)
    if suffix == ".pak":
        return _inspect_pak(path)
    return _unknown(path, "CONTAINER_UNRECOGNIZED", f"unrecognized container extension {suffix!r}")
