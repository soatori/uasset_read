"""Niagara semantic content extractor (#557e).

Dispatches on object_class for NiagaraSystem, NiagaraEmitter, NiagaraScript.
Parameter types use basic strings: float, int, vec2, vec3, vec4, bool, string, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _build_system(asset_type_data: dict, cov) -> dict:
    meta: dict = {}
    for key in ("emitter_count", "total_spawn_rate", "has_gpu_computation"):
        val = asset_type_data.get(key)
        if val is not None:
            meta[key] = val
    cov.track("niagara_metadata", len(meta) > 0)

    emitters = asset_type_data.get("emitters", [])
    cov.track("emitters", len(emitters) > 0)

    result: dict = {"niagara": {"niagara_metadata": meta}}
    if emitters:
        result["niagara"]["emitters"] = emitters
    return result


def _build_emitter(asset_type_data: dict, cov) -> dict:
    meta: dict = {}
    for key in ("script_count", "parameter_count", "sim_stage_count", "has_gpu_computation"):
        val = asset_type_data.get(key)
        if val is not None:
            meta[key] = val
    cov.track("niagara_metadata", len(meta) > 0)

    scripts = asset_type_data.get("scripts", [])
    cov.track("scripts", len(scripts) > 0)

    parameters: dict = {}
    for category in ("uniform", "input", "output"):
        params = asset_type_data.get(f"{category}_parameters") or asset_type_data.get(category, [])
        if params:
            parameters[category] = params
    cov.track("parameters", len(parameters) > 0)

    result: dict = {"niagara": {"niagara_metadata": meta}}
    if scripts:
        result["niagara"]["scripts"] = scripts
    if parameters:
        result["niagara"]["parameters"] = parameters
    return result


def _build_script(asset_type_data: dict, cov) -> dict:
    meta: dict = {}
    for key in ("script_type", "parameter_count", "has_bytecode", "bytecode_size"):
        val = asset_type_data.get(key)
        if val is not None:
            meta[key] = val
    cov.track("niagara_metadata", len(meta) > 0)

    parameters: dict = {}
    for category in ("input", "output", "uniform"):
        params = asset_type_data.get(f"{category}_parameters") or asset_type_data.get(category, [])
        if params:
            parameters[category] = params
    cov.track("parameters", len(parameters) > 0)

    result: dict = {"niagara": {"niagara_metadata": meta}}
    if parameters:
        result["niagara"]["parameters"] = parameters
    return result


def build_niagara_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    asset_type_data = getattr(export_ir, "asset_type_data", None)
    object_class = getattr(export_ir, "object_class", "") or ""

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("niagara_metadata", False)
        return {}

    if object_class == "NiagaraSystem":
        return _build_system(asset_type_data, coverage_model)
    elif object_class == "NiagaraEmitter":
        return _build_emitter(asset_type_data, coverage_model)
    elif object_class == "NiagaraScript":
        return _build_script(asset_type_data, coverage_model)
    else:
        coverage_model.track("niagara_metadata", False)
        return {}
