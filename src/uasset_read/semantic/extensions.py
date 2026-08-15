"""Extension registry — maps exact UE class names to domain extractors.

Extractor contract (v2, package-scoped):

    extractor(package_ir, export_ir, coverage_model, evidence_list) -> dict

The returned dict is merged into SemanticIR.content. Reserved envelope keys
must not appear in it except the overridable set {coverage, diagnostics,
references}, which a domain format may redefine.
"""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR

_REGISTRY: dict[str, Callable] = {}
_DOMAIN_FORMATS: dict[str, tuple[str, str]] = {}


def register_extension(
    class_name: str,
    extractor: Callable,
    *,
    domain_format: str | None = None,
    domain_format_version: str | None = None,
) -> None:
    """Register a domain extractor for an exact UE class name.

    Raises ValueError on duplicate registration, or when domain_format and
    domain_format_version are not provided together.
    """
    if class_name in _REGISTRY:
        raise ValueError(f"Extension already registered for class '{class_name}'")
    if bool(domain_format) != bool(domain_format_version):
        raise ValueError("domain_format and domain_format_version must be provided together")
    _REGISTRY[class_name] = extractor
    if domain_format:
        _DOMAIN_FORMATS[class_name] = (domain_format, domain_format_version)


def get_extractor(class_name: str) -> Callable | None:
    """Get the registered extractor for a class, or None."""
    return _REGISTRY.get(class_name)


def get_domain_format(class_name: str) -> tuple[str, str] | None:
    """Get (format, format_version) for a domain-format class, or None."""
    return _DOMAIN_FORMATS.get(class_name)


def is_registered(class_name: str) -> bool:
    """Check whether a class has a registered extractor."""
    return class_name in _REGISTRY
