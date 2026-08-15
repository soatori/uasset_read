"""Blueprint type system — TypeRef union and interned types table (BP-§11)."""
from __future__ import annotations

import json
from typing import Any


class TypeTable:
    """Builds the ``types`` table and TypeRef values in first-encounter order.

    ``type_ref_for`` accepts PinIR-shaped keyword arguments. Primitive
    categories return inline strings; complex types are interned and returned
    as ``{"$type": "t<N>"}``. Map pins: main type is the key, the terminal is
    the value (BP-§11).
    """

    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}
        self._by_encoding: dict[str, str] = {}
        self._counter = 0

    def _intern(self, entry: dict) -> dict:
        key = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        type_id = self._by_encoding.get(key)
        if type_id is None:
            type_id = f"t{self._counter}"
            self._counter += 1
            self._by_encoding[key] = type_id
            self.entries[type_id] = entry
        return {"$type": type_id}

    def type_ref_for(
        self,
        category: str = "",
        subcategory: str = "",
        subcategory_object_name: str | None = None,
        container_type: int | str = 0,
        is_reference: bool = False,
        is_const: bool = False,
        is_weak_pointer: bool = False,
        is_uobject_wrapper: bool = False,
        map_key_terminal_category: str = "",
        map_key_terminal_sub_category: str = "",
        map_key_terminal_sub_category_object_name: str | None = None,
    ) -> Any:
        base = self._base_ref(category, subcategory, subcategory_object_name,
                              container_type, is_weak_pointer, is_uobject_wrapper,
                              map_key_terminal_category, map_key_terminal_sub_category,
                              map_key_terminal_sub_category_object_name)
        if is_reference or is_const:
            entry: dict = {"kind": "ref", "target": base}
            if is_const:
                entry["const"] = True
            return self._intern(entry)
        return base

    def _base_ref(self, category, subcategory, subcategory_object_name, container_type,
                  is_weak_pointer, is_uobject_wrapper,
                  map_key_terminal_category, map_key_terminal_sub_category,
                  map_key_terminal_sub_category_object_name) -> Any:
        category = (category or "").lower()
        subcategory = (subcategory or "").lower()
        name = subcategory_object_name or ""

        code = _container_code(container_type)
        if code == 1:
            elem = self.type_ref_for(category=category, subcategory=subcategory,
                                    subcategory_object_name=subcategory_object_name)
            return self._intern({"kind": "array", "element": elem})
        if code == 2:
            elem = self.type_ref_for(category=category, subcategory=subcategory,
                                    subcategory_object_name=subcategory_object_name)
            return self._intern({"kind": "set", "element": elem})
        if code == 3:
            key_ref = self.type_ref_for(category=category, subcategory=subcategory,
                                        subcategory_object_name=subcategory_object_name)
            value_ref = self.type_ref_for(category=map_key_terminal_category,
                                          subcategory=map_key_terminal_sub_category,
                                          subcategory_object_name=map_key_terminal_sub_category_object_name)
            return self._intern({"kind": "map", "key": key_ref, "value": value_ref})

        if category in ("bool", "string", "name", "text", "byte", "int", "int64",
                        "int8", "uint8", "uint16", "uint32", "uint64", "float",
                        "double", "vector", "vector2d", "rotator", "transform",
                        "color", "guid"):
            return category
        if category == "real":
            return "double" if subcategory == "double" else "float"

        if category == "struct":
            return self._intern({"kind": "struct", "path": name or subcategory or "unnamed"})
        if category == "enum":
            return self._intern({"kind": "enum", "path": name or subcategory or "unnamed"})
        if category == "delegate":
            entry = {"kind": "delegate", "signature": name or subcategory or "unnamed"}
            if subcategory == "mcdelegate":
                entry["multicast"] = True
            return self._intern(entry)
        if category == "interface":
            return self._intern({"kind": "interface", "path": name or "unnamed"})
        if category == "class":
            return self._intern({"kind": "class", "path": name or "unnamed"})
        if category in ("object", "softobject"):
            entry = {"kind": "object", "path": name or "Object"}
            if category == "softobject":
                entry["soft"] = True
            if is_weak_pointer:
                entry["weak"] = True
            if is_uobject_wrapper:
                entry["uobject_wrapper"] = True
            return self._intern(entry)
        if category == "wildcard":
            return self._intern({"kind": "wildcard", "declared": "wildcard"})

        return self._intern({"kind": "unknown", "category": category or "unknown",
                             "name": name or subcategory or ""})


def type_ref_from_pin(table: TypeTable, pin) -> Any:
    """TypeRef for a PinIR using its FEdGraphPinType-derived fields."""
    return table.type_ref_for(
        category=getattr(pin, "pin_category", ""),
        subcategory=getattr(pin, "pin_subcategory", ""),
        subcategory_object_name=getattr(pin, "pin_subcategory_object_name", None),
        container_type=getattr(pin, "container_type", "None"),
        is_reference=getattr(pin, "is_reference", False),
        is_const=getattr(pin, "is_const", False),
        is_weak_pointer=getattr(pin, "is_weak_pointer", False),
        is_uobject_wrapper=getattr(pin, "is_uobject_wrapper", False),
        map_key_terminal_category=getattr(pin, "map_key_pin_category", ""),
        map_key_terminal_sub_category=getattr(pin, "map_key_pin_subcategory", ""),
        map_key_terminal_sub_category_object_name=getattr(pin, "map_key_pin_subcategory_object_name", None),
    )


def _container_code(value: Any) -> int:
    if isinstance(value, int):
        return value
    return {"None": 0, "Array": 1, "Set": 2, "Map": 3}.get(str(value), 0)