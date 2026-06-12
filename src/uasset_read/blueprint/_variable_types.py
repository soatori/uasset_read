"""变量类型映射和标志位工具函数。"""
from __future__ import annotations

from typing import Dict, List

from uasset_read.models.core import FEdGraphPinType
from uasset_read.models.properties import PropertyValue
from uasset_read.constants import (
    CPF_EditAnywhere, CPF_EditInstanceOnly, CPF_BlueprintReadWrite,
    CPF_BlueprintReadOnly, CPF_Net, CPF_Replicated, CPF_Transient,
    CPF_BlueprintAssignable, CPF_RepNotify, CPF_SaveGame,
)


# Pin Category → C++ 类型映射
PIN_CATEGORY_TO_CPP_TYPE: Dict[str, str] = {
    "real": "float",
    "double": "double",
    "float": "float",
    "int": "int32",
    "int32": "int32",
    "int64": "int64",
    "byte": "uint8",
    "bool": "bool",
    "boolean": "bool",
    "string": "FString",
    "name": "FName",
    "text": "FText",
    "struct": "FStruct",
    "vector": "FVector",
    "rotator": "FRotator",
    "transform": "FTransform",
    "vector2d": "FVector2D",
    "linearcolor": "FLinearColor",
    "guid": "FGuid",
    "object": "UObject*",
    "class": "UClass*",
    "widget": "UWidget*",
    " wildcard": "Wildcard",
    "exec": "void",
    "delegate": "void",
    "multicastdelegate": "void",
}


def map_pin_category_to_cpp_type(pin_category: str) -> str:
    """将 pin_category 映射到 C++ 类型。"""
    if pin_category in PIN_CATEGORY_TO_CPP_TYPE:
        return PIN_CATEGORY_TO_CPP_TYPE[pin_category]

    lower_category = pin_category.lower()
    for key, value in PIN_CATEGORY_TO_CPP_TYPE.items():
        if key.lower() == lower_category:
            return value

    if pin_category.startswith("/Script/"):
        return pin_category

    return pin_category


def map_property_flags(flags: int) -> Dict[str, bool]:
    """将 CPF_* 位标志映射到 BlueprintVariable 布尔属性。"""
    return {
        "is_edit_anywhere": bool(flags & CPF_EditAnywhere),
        "is_edit_instance_only": bool(flags & CPF_EditInstanceOnly),
        "is_blueprint_readable": bool(flags & CPF_BlueprintReadWrite),
        "is_blueprint_read_only": bool(flags & CPF_BlueprintReadOnly),
        "is_net": bool(flags & CPF_Net),
        "is_replicated": bool(flags & CPF_Replicated),
        "is_transient": bool(flags & CPF_Transient),
        "is_blueprint_assignable": bool(flags & CPF_BlueprintAssignable),
        "is_rep_notify": bool(flags & CPF_RepNotify),
        "is_save_game": bool(flags & CPF_SaveGame),
    }


def extract_pin_type_from_property(prop: PropertyValue) -> FEdGraphPinType:
    """从 PropertyValue 提取 FEdGraphPinType 类型信息。"""
    value = prop.value

    if isinstance(value, dict):
        pin_category = value.get("pin_category", "")
        pin_subcategory = value.get("pin_subcategory", "")
        pin_subcategory_object = value.get("pin_subcategory_object")
        container_type = value.get("container_type", 0)

        from uasset_read.models.properties import StructValue
        if hasattr(prop, "type") and prop.type == "StructProperty":
            if isinstance(value, dict):
                pin_category = value.get("PinCategory", value.get("pin_category", ""))
                pin_subcategory = value.get("PinSubcategory", value.get("pin_subcategory", ""))
                if "PinSubcategoryObject" in value:
                    pin_subcategory_object = value["PinSubcategoryObject"]
                elif "pin_subcategory_object" in value:
                    pin_subcategory_object = value["pin_subcategory_object"]

        return FEdGraphPinType(
            pin_category=pin_category,
            pin_subcategory=pin_subcategory,
            pin_subcategory_object=pin_subcategory_object,
            container_type=container_type,
        )

    type_mapping = {
        "BoolProperty": FEdGraphPinType(pin_category="bool"),
        "IntProperty": FEdGraphPinType(pin_category="int"),
        "Int64Property": FEdGraphPinType(pin_category="int64"),
        "FloatProperty": FEdGraphPinType(pin_category="float"),
        "DoubleProperty": FEdGraphPinType(pin_category="double"),
        "StrProperty": FEdGraphPinType(pin_category="string"),
        "NameProperty": FEdGraphPinType(pin_category="name"),
        "TextProperty": FEdGraphPinType(pin_category="text"),
        "ObjectProperty": FEdGraphPinType(pin_category="object"),
        "ClassProperty": FEdGraphPinType(pin_category="class"),
        "ArrayProperty": FEdGraphPinType(pin_category="array"),
        "StructProperty": FEdGraphPinType(pin_category="struct"),
        "MapProperty": FEdGraphPinType(pin_category="map"),
        "SetProperty": FEdGraphPinType(pin_category="set"),
        "EnumProperty": FEdGraphPinType(pin_category="byte", pin_subcategory="enum"),
        "ByteProperty": FEdGraphPinType(pin_category="byte"),
        "DelegateProperty": FEdGraphPinType(pin_category="delegate"),
        "MulticastDelegateProperty": FEdGraphPinType(pin_category="multicast_delegate"),
        "InterfaceProperty": FEdGraphPinType(pin_category="interface"),
        "WeakObjectProperty": FEdGraphPinType(pin_category="weak_object"),
        "LazyObjectProperty": FEdGraphPinType(pin_category="lazy_object"),
        "SoftObjectProperty": FEdGraphPinType(pin_category="soft_object"),
        "SoftClassProperty": FEdGraphPinType(pin_category="soft_class"),
    }

    if isinstance(value, str) and getattr(prop, 'type', None) in type_mapping:
        return type_mapping[prop.type]

    return FEdGraphPinType(pin_category=prop.type if hasattr(prop, "type") else "unknown")


# 向后兼容别名
_PIN_CATEGORY_TO_CPP_TYPE = PIN_CATEGORY_TO_CPP_TYPE
_map_pin_category_to_cpp_type = map_pin_category_to_cpp_type
_map_property_flags = map_property_flags
_extract_pin_type_from_property = extract_pin_type_from_property
