"""Semantic JSON renderer -- serializes SemanticIR to deterministic JSON.

Registered as 'semantic_json' in RENDERER_REGISTRY.
Consumes SemanticIR (not PackageIR) for clean separation.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import IO, Any, TYPE_CHECKING

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer
from uasset_read.semantic.canonical import canonical_sort
from uasset_read.semantic.ir import SemanticIR

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class SemanticJSONRenderer(IRenderer):
    """Semantic JSON renderer -- deterministic output with canonical key ordering."""

    @property
    def format_name(self) -> str:
        return "semantic_json"

    def render(self, ir: PackageIR | SemanticIR, options: RenderOptions) -> str:
        """Render to semantic JSON.

        Accepts either SemanticIR or PackageIR. When called with SemanticIR,
        delegates to render_semantic(). PackageIR is not supported directly.
        """
        if isinstance(ir, SemanticIR):
            return self.render_semantic(ir, options)
        raise NotImplementedError(
            "SemanticJSONRenderer.render() does not accept PackageIR directly. "
            "Pass a SemanticIR instance or use render_semantic()."
        )

    def render_semantic(self, semantic_ir: SemanticIR, options: RenderOptions) -> str:
        """Render SemanticIR to deterministic JSON string.

        Args:
            semantic_ir: SemanticIR from builder
            options: RenderOptions

        Returns:
            Deterministic JSON string with canonical key ordering
        """
        data = self._build_data(semantic_ir)
        return json.dumps(
            data,
            indent=options.indent,
            ensure_ascii=False,
        )

    def render_semantic_to(
        self,
        semantic_ir: SemanticIR,
        writer: IO[str],
        options: RenderOptions | None = None,
    ) -> None:
        """Render SemanticIR to a writer stream.

        Args:
            semantic_ir: SemanticIR from builder
            writer: Writable text stream
            options: RenderOptions (optional)
        """
        if options is None:
            options = RenderOptions()
        data = self._build_data(semantic_ir)
        json.dump(
            data,
            writer,
            indent=options.indent,
            ensure_ascii=False,
        )
        writer.write("\n")

    def _build_data(self, semantic_ir: SemanticIR) -> dict[str, Any]:
        """Build the data dict from SemanticIR with canonical ordering."""
        raw = asdict(semantic_ir)
        # Convert AssetKind enum to string
        raw["asset"]["kind"] = semantic_ir.asset.kind.value
        return canonical_sort(raw)


# Register on import
register_renderer("semantic_json", SemanticJSONRenderer)
