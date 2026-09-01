"""Shared helpers for asset_type_data-backed semantic extractors.

Domains share the same shape: guard on ``ExportIR.asset_type_data``,
dispatch on ``ExportIR.object_class`` and copy fixed field tuples into
named sections while tracking coverage. ``class_extractor`` wires the
guard + dispatch; per-class specs are either section tables or small
callables for the domain-specific shapes.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable


def pick(data: dict, keys: Iterable[str]) -> dict:
    """Copy keys whose value is present and not None."""
    return {k: data[k] for k in keys if data.get(k) is not None}


def key(name: str, default: Any = None) -> Callable[[dict], Any]:
    """Section value equal to ``data.get(name, default)``."""
    return lambda data: data.get(name, default)


def build_sections(domain: str, data: dict, cov, sections) -> dict:
    """Build ``{domain: {...}}`` from ``(out_key, source, cov_key, mode)`` specs.

    ``source`` is a key tuple (picked from data) or a ``callable(data)``.
    Modes: "summary" emits the section always; "section" emits it only when
    non-empty (coverage tracks emptiness either way); "raw" copies every
    truthy key of its tuple without coverage.
    """
    out: dict = {}
    for out_key, source, cov_key, mode in sections:
        if mode == "raw":
            for name in source:
                value = data.get(name)
                if value:
                    out[name] = value
            continue
        value = pick(data, source) if isinstance(source, tuple) else source(data)
        if cov_key is not None:
            cov.track(cov_key, bool(value))
        if mode == "summary" or value:
            out[out_key] = value
    return {domain: out}


def class_extractor(domain: str, classes: dict, miss_cov: str | None = None):
    """Build a ``(package_ir, export_ir, coverage_model) -> dict`` extractor.

    Dispatches ``ExportIR.object_class`` through ``classes``; a spec value is
    a section table handled by ``build_sections``, or a callable
    ``(asset_type_data, coverage_model, object_class) -> dict``. When the
    guard fails or the class is unknown, ``miss_cov`` (if given) is tracked
    as unavailable.
    """

    def build(package_ir, export_ir, coverage_model) -> dict:
        data = getattr(export_ir, "asset_type_data", None)
        object_class = getattr(export_ir, "object_class", "") or ""
        spec = classes.get(object_class)
        if spec is None or not data or not isinstance(data, dict):
            if miss_cov is not None:
                coverage_model.track(miss_cov, False)
            return {}
        if callable(spec):
            return spec(data, coverage_model, object_class)
        return build_sections(domain, data, coverage_model, spec)

    return build
