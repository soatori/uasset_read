"""C++ projection AST and declaration builder (Blueprint Header View scope).

``build_cpp_ast`` consumes typed ``BlueprintSemantic`` only. Type names are
derived from measured pin/reflection data; unresolved types stay explicit
(``CppType.resolved is False``) and are never silently replaced with ``void``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from uasset_read.kismet.native_fields import (
    NativeFieldDeclaration,
    _CPF_ConstParm,
    _CPF_Parm,
    _CPF_ReferenceParm,
    _CPF_ReturnParm,
    build_native_function_signature,
    native_field_cpp_type,
)
from uasset_read.models.analysis import (
    BlueprintSemantic,
    FunctionDeclaration,
    FunctionParameter,
    VariableDefinition,
)


@dataclass
class CppType:
    name: str
    is_pointer: bool = False
    is_reference: bool = False
    resolved: bool = True


@dataclass
class CppParam:
    name: str
    type: CppType
    direction: Literal["in", "out", "inout"] = "in"
    default: str | None = None


@dataclass
class CppFunctionDecl:
    name: str
    return_type: CppType
    params: list[CppParam]
    specifiers: list[str]
    is_const: bool = False
    # Measured native reflection signature (kismet/native_fields helpers).
    native_signature: str | None = None


@dataclass
class CppPropertyDecl:
    name: str
    type: CppType
    specifiers: list[str]


@dataclass
class CppComponentDecl:
    name: str
    type: CppType


@dataclass
class CppDispatcherDecl:
    name: str
    params: list[CppParam]


@dataclass
class CppConstructorDecl:
    name: str
    parent_call: str | None
    component_initializers: list[str]
    variable_initializers: list[str]
    body: list["CppStmt"]
    status: Literal["translated", "represented", "untranslated", "unavailable"]


@dataclass
class CppClassDecl:
    name: str
    parent: str
    functions: list[CppFunctionDecl]
    properties: list[CppPropertyDecl]
    components: list[CppComponentDecl]
    dispatchers: list[CppDispatcherDecl]
    constructors: list[CppConstructorDecl]


@dataclass
class CppStmt:
    kind: str
    text: str
    statement_index: int | None = None
    serialized_start: int | None = None
    serialized_end: int | None = None
    function_name: str | None = None
    object_id: str | None = None
    source_node_id: str | None = None
    source_range: Any | None = None
    status: Literal["translated", "represented", "untranslated", "unavailable"] = "unavailable"
    diagnostic: str | None = None


# UE Blueprint pin_category / subcategory → C++ type (measured pin data only).
_SCALAR_CPP: dict[str, str] = {
    "bool": "bool",
    "int": "int32",
    "int64": "int64",
    "float": "float",
    "string": "FString",
    "text": "FText",
    "name": "FName",
    "byte": "uint8",
    "class": "UClass*",
}

_REAL_SUB_CPP: dict[str, str] = {
    "double": "double",
    "float": "float",
}

_DELEGATE_CATS = frozenset({"delegate", "mcdelegate"})
_EXEC_CATS = frozenset({"exec", "exec_"})


def _sanitize_unresolved(raw: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", raw or "unknown")
    if cleaned and cleaned[0].isdigit():
        cleaned = f"U{cleaned}"
    return cleaned or "unknown"


def _unresolved_type(raw: str) -> CppType:
    return CppType(name=_sanitize_unresolved(raw), resolved=False)


def _pin_category(vt: dict[str, Any]) -> str:
    return str(vt.get("pin_category") or "")


def _pin_subcategory(vt: dict[str, Any]) -> str:
    sub = str(vt.get("pin_subcategory") or "")
    return "" if sub in {"", "None", "none", "NULL"} else sub


def _scalar_from_pin(vt: dict[str, Any]) -> CppType:
    cat = _pin_category(vt)
    sub = _pin_subcategory(vt)
    if cat in _DELEGATE_CATS:
        return CppType(name="FMulticastScriptDelegate" if cat == "mcdelegate" else "FScriptDelegate")
    if cat == "real":
        if sub in _REAL_SUB_CPP:
            return CppType(name=_REAL_SUB_CPP[sub])
        return _unresolved_type(f"real:{sub}" if sub else "real")
    if cat in _SCALAR_CPP:
        return CppType(name=_SCALAR_CPP[cat])
    if cat == "object":
        # pin_subcategory_object is a package index; unresolved until a class name is measured.
        if sub:
            return CppType(name=f"{sub}*", is_pointer=True)
        return _unresolved_type("object")
    if cat == "struct":
        if sub:
            return CppType(name=f"F{sub}" if not sub.startswith("F") else sub)
        return _unresolved_type("struct")
    if cat == "enum":
        if sub:
            return CppType(name=sub)
        return _unresolved_type("enum")
    if not cat:
        return _unresolved_type("missing_pin_category")
    return _unresolved_type(cat if not sub else f"{cat}:{sub}")


def cpp_type_from_pin(vt: dict[str, Any] | None) -> CppType:
    """Map one measured FEdGraphPinType dict to a CppType."""
    if not isinstance(vt, dict):
        return _unresolved_type("missing_pin_type")
    container = 0
    try:
        container = int(vt.get("container_type") or 0)
    except (TypeError, ValueError):
        container = 0
    key = _scalar_from_pin(vt)
    if container == 1:
        return CppType(name=f"TArray<{key.name}>", resolved=key.resolved)
    if container == 2:
        return CppType(name=f"TSet<{key.name}>", resolved=key.resolved)
    if container == 3:
        term_cat = str(vt.get("map_terminal_category") or "")
        term_sub = str(vt.get("map_terminal_subcategory") or "")
        if term_sub in {"", "None", "none", "NULL"}:
            term_sub = ""
        if not term_cat or term_cat in {"None", "none"}:
            return CppType(name=f"TMap<{key.name}, {_sanitize_unresolved('map_value')}>", resolved=False)
        value = _scalar_from_pin(
            {"pin_category": term_cat, "pin_subcategory": term_sub or vt.get("map_terminal_subcategory")}
        )
        return CppType(name=f"TMap<{key.name}, {value.name}>", resolved=key.resolved and value.resolved)
    return key


def cpp_type_from_type_name(type_name: str | None, *, unresolved: bool = False) -> CppType:
    """Fallback mapper for projected ``type_name`` strings like ``real:double``."""
    if not type_name:
        return _unresolved_type("missing_type_name")
    raw = str(type_name)
    if ":" in raw:
        cat, _, sub = raw.partition(":")
        return cpp_type_from_pin({"pin_category": cat, "pin_subcategory": sub})
    mapped = cpp_type_from_pin({"pin_category": raw})
    if unresolved and mapped.resolved:
        return _unresolved_type(raw)
    return mapped


def _variable_cpp_type(var: VariableDefinition) -> CppType:
    if var.cpp_type:
        text = str(var.cpp_type)
        if text.startswith("unresolved:") or var.unresolved:
            return _unresolved_type(text.removeprefix("unresolved:").strip() or text)
        return CppType(name=text, resolved=not var.unresolved)
    raw = var.raw_type if isinstance(var.raw_type, dict) else None
    vt = raw.get("VarType") if raw else None
    if isinstance(vt, dict) and vt:
        return cpp_type_from_pin(vt)
    return cpp_type_from_type_name(var.type_name, unresolved=var.unresolved)


def _parameter_cpp_type(param: FunctionParameter) -> CppType:
    if param.cpp_type:
        text = str(param.cpp_type)
        if text.startswith("unresolved:"):
            return _unresolved_type(text.removeprefix("unresolved:").strip() or text)
        return CppType(name=text, resolved=True)
    return cpp_type_from_type_name(param.type_name, unresolved=not param.type_name)


def _direction(value: str | None) -> Literal["in", "out", "inout"]:
    if value in {"out", "inout"}:
        return value  # type: ignore[return-value]
    return "in"


def _is_exec_pin(pin: Any) -> bool:
    category = str(getattr(pin, "category", None) or "").lower()
    return category in _EXEC_CATS or category.startswith("exec")


def _graph_signature(semantic: BlueprintSemantic, function_name: str) -> tuple[list[CppParam], CppType, bool]:
    """Measure params/return from FunctionEntry/FunctionResult graph pins.

    UE convention (Header View scope): FunctionEntry non-exec output pins are
    function inputs; FunctionResult non-exec input pins are outputs. A missing
    FunctionResult ReturnValue pin measures as void only when a result node
    exists for that function.
    """
    params: list[CppParam] = []
    return_type: CppType | None = None
    saw_result = False
    saw_entry = False
    for graph in semantic.graphs:
        for node in graph.nodes:
            meta = node.metadata
            node_fn = (meta.function_name if meta else None) or ""
            # Delegate signature graphs may name the dispatcher rather than the UFunction.
            if node_fn != function_name and graph.name != function_name:
                continue
            class_name = node.class_name or ""
            if class_name.endswith("FunctionEntry") or class_name == "K2Node_FunctionEntry":
                saw_entry = True
                for pin in node.pins:
                    if _is_exec_pin(pin):
                        continue
                    if str(pin.direction or "").lower() != "output":
                        continue
                    params.append(
                        CppParam(
                            name=pin.name,
                            type=cpp_type_from_pin(
                                {
                                    "pin_category": pin.category,
                                    "pin_subcategory": pin.subcategory,
                                }
                            ),
                            direction="in",
                        )
                    )
            elif class_name.endswith("FunctionResult") or class_name == "K2Node_FunctionResult":
                saw_result = True
                for pin in node.pins:
                    if _is_exec_pin(pin):
                        continue
                    if str(pin.direction or "").lower() != "input":
                        continue
                    ctype = cpp_type_from_pin({"pin_category": pin.category, "pin_subcategory": pin.subcategory})
                    if pin.name == "ReturnValue":
                        return_type = ctype
                    else:
                        params.append(CppParam(name=pin.name, type=ctype, direction="out"))
    if return_type is None and saw_result:
        return_type = CppType(name="void", resolved=True)
    if return_type is None:
        return_type = _unresolved_type("return_type")
        measured = False
    else:
        measured = True
    if not saw_entry and not saw_result:
        # No graph evidence for this declaration name.
        measured = False
    return params, return_type, measured


def _native_function_parts(
    name: str, fields: list[NativeFieldDeclaration]
) -> tuple[CppType, list[CppParam], str | None]:
    """Structured signature from measured native fields via in-tree helpers.

    Uses ``native_field_cpp_type`` for each reflected type and
    ``build_native_function_signature`` for the auditable signature string.
    """
    params: list[CppParam] = []
    ret = CppType(name="void", resolved=True)
    for field in fields:
        flags = field.property_flags or 0
        if not (flags & _CPF_Parm):
            continue
        raw_cpp = native_field_cpp_type(field)
        resolved = not raw_cpp.startswith("/*")
        is_ref = bool(flags & _CPF_ReferenceParm)
        is_const = bool(flags & _CPF_ConstParm)
        ctype = CppType(name=raw_cpp, is_reference=is_ref, resolved=resolved)
        if flags & _CPF_ReturnParm:
            ret = ctype
            continue
        if is_ref and not is_const:
            direction: Literal["in", "out", "inout"] = "out"
        else:
            direction = "in"
        params.append(CppParam(name=field.name or "param", type=ctype, direction=direction))
    signature: str | None
    try:
        signature = build_native_function_signature(name, list(fields))
    except Exception:
        signature = None
    return ret, params, signature


def _function_decl(semantic: BlueprintSemantic, fd: FunctionDeclaration) -> CppFunctionDecl:
    native_params: list[CppParam] | None = None
    native_ret: CppType | None = None
    native_sig: str | None = None
    if fd.native_fields:
        native_ret, native_params, native_sig = _native_function_parts(fd.name, list(fd.native_fields))

    graph_params, graph_return, graph_measured = _graph_signature(semantic, fd.name)
    if native_sig and native_params is not None and native_ret is not None:
        # Measured native reflection wins for signature fidelity.
        params = native_params
        ret = native_ret
    elif fd.parameters:
        params = [
            CppParam(
                name=p.name,
                type=_parameter_cpp_type(p),
                direction=_direction(p.direction),
            )
            for p in fd.parameters
        ]
        if fd.return_type or fd.cpp_return_type:
            ret = CppType(name=str(fd.cpp_return_type or fd.return_type), resolved=not fd.unresolved)
        elif graph_measured:
            ret = graph_return
        else:
            ret = _unresolved_type("return_type")
    elif graph_params or graph_measured:
        params = graph_params
        if fd.cpp_return_type or fd.return_type:
            ret = CppType(name=str(fd.cpp_return_type or fd.return_type), resolved=not fd.unresolved)
        else:
            ret = graph_return
    else:
        params = []
        if fd.cpp_return_type or fd.return_type:
            ret = CppType(name=str(fd.cpp_return_type or fd.return_type), resolved=not fd.unresolved)
        else:
            ret = _unresolved_type("return_type")
    return CppFunctionDecl(
        name=fd.name,
        return_type=ret,
        params=params,
        specifiers=["UFUNCTION"],
        is_const=False,
        native_signature=native_sig,
    )


def build_cpp_ast(semantic: BlueprintSemantic) -> CppClassDecl:
    """Build the Header-View-scope C++ class AST from typed Blueprint IR."""
    declaration = semantic.declaration
    class_name = declaration.class_name or semantic.name or "UnresolvedBlueprint"
    parent = declaration.parent_class or semantic.parent_class or "UObject"

    properties: list[CppPropertyDecl] = []
    dispatchers: list[CppDispatcherDecl] = []
    dispatcher_names: set[str] = set()

    for item in semantic.dispatchers:
        params = [
            CppParam(
                name=p.name,
                type=_parameter_cpp_type(p),
                direction=_direction(p.direction),
            )
            for p in item.parameters
        ]
        dispatchers.append(CppDispatcherDecl(name=item.name, params=params))
        dispatcher_names.add(item.name)

    for var in semantic.variable_definitions:
        ctype = _variable_cpp_type(var)
        raw = var.raw_type if isinstance(var.raw_type, dict) else None
        vt = raw.get("VarType") if raw else None
        pin_cat = _pin_category(vt) if isinstance(vt, dict) else ""
        type_name = (var.type_name or "").split(":", 1)[0]
        if pin_cat in _DELEGATE_CATS or type_name in _DELEGATE_CATS:
            if var.name not in dispatcher_names:
                dispatchers.append(CppDispatcherDecl(name=var.name, params=[]))
                dispatcher_names.add(var.name)
            continue
        properties.append(CppPropertyDecl(name=var.name, type=ctype, specifiers=["UPROPERTY"]))

    functions = [_function_decl(semantic, fd) for fd in semantic.function_declarations]

    components = [
        CppComponentDecl(
            name=item.name,
            type=CppType(name=f"{item.class_name}*" if item.class_name else "UObject*", is_pointer=True),
        )
        for item in semantic.components
    ]

    constructors = [
        CppConstructorDecl(
            name=item.name,
            parent_call=item.parent_call,
            component_initializers=list(item.component_initializers),
            variable_initializers=list(item.variable_initializers),
            body=[],
            status="represented" if item.parent_call else ("untranslated" if item.unresolved else "represented"),
        )
        for item in semantic.constructors
    ]

    return CppClassDecl(
        name=class_name,
        parent=parent,
        functions=functions,
        properties=properties,
        components=components,
        dispatchers=dispatchers,
        constructors=constructors,
    )
