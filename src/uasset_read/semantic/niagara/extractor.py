"""Niagara semantic content extractor (#557e).

Dispatches on object_class for NiagaraSystem, NiagaraEmitter, NiagaraScript.
Parameter types use basic strings: float, int, vec2, vec3, vec4, bool, string, etc.
"""

from __future__ import annotations

from uasset_read.semantic.asset_data import class_extractor, key


def _parameters(*categories: str):
    """Read parameter groups from ``<category>_parameters`` or bare ``<category>``."""

    def build(data: dict) -> dict:
        parameters: dict = {}
        for category in categories:
            params = data.get(f"{category}_parameters") or data.get(category, [])
            if params:
                parameters[category] = params
        return parameters

    return build


# (out_key, source, coverage key, mode) section tables per class; see asset_data.
_NIAGARA_SYSTEM = (
    ("niagara_metadata", ("emitter_count", "total_spawn_rate", "has_gpu_computation"), "niagara_metadata", "summary"),
    ("emitters", key("emitters", []), "emitters", "section"),
)

_NIAGARA_EMITTER = (
    (
        "niagara_metadata",
        ("script_count", "parameter_count", "sim_stage_count", "has_gpu_computation"),
        "niagara_metadata",
        "summary",
    ),
    ("scripts", key("scripts", []), "scripts", "section"),
    ("parameters", _parameters("uniform", "input", "output"), "parameters", "section"),
)

_NIAGARA_SCRIPT = (
    (
        "niagara_metadata",
        ("script_type", "parameter_count", "has_bytecode", "bytecode_size"),
        "niagara_metadata",
        "summary",
    ),
    ("parameters", _parameters("input", "output", "uniform"), "parameters", "section"),
)


build_niagara_content = class_extractor(
    "niagara",
    {
        "NiagaraSystem": _NIAGARA_SYSTEM,
        "NiagaraEmitter": _NIAGARA_EMITTER,
        "NiagaraScript": _NIAGARA_SCRIPT,
    },
    miss_cov="niagara_metadata",
)
