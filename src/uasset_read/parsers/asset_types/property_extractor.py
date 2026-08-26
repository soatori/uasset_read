"""Property extraction helper functions — Eliminates duplicate patterns in asset_types handlers."""

from typing import Any, Callable, TypeVar

T = TypeVar("T")


def build_properties_dict(properties_list: list) -> dict[str, Any]:
    """Convert property list to dictionary format (name -> value).

    All handlers need to convert export.properties (property object list)
    to name -> value dictionary for extract_* functions to use.

    Args:
        properties_list: List of property objects (each with name and value attributes)

    Returns:
        name -> value dictionary
    """
    properties: dict[str, Any] = {}
    for prop in properties_list:
        if hasattr(prop, "name") and hasattr(prop, "value"):
            properties[prop.name] = prop.value
    return properties


def parse_dict_list(
    data: Any,
    parser: Callable[[dict], Any],
) -> list[Any]:
    """Parse dictionary list, skipping non-dictionary elements.

    Args:
        data: Data to parse (list or any type)
        parser: Dictionary parse function

    Returns:
        Parsed list, returns empty list if data is not a list
    """
    if not isinstance(data, list):
        return []
    return [parser(item) for item in data if isinstance(item, dict)]


def extract_property(
    properties: dict[str, Any],
    prop_name: str,
    target: Any,
    field_name: str,
    transform: Callable[[Any], Any] | None = None,
) -> bool:
    """Extract property value from properties dictionary to target object field.

    Args:
        properties: Property dictionary (name -> value)
        prop_name: Property name to extract
        target: Target object (will be set via setattr)
        field_name: Target field name
        transform: Optional value transformation function

    Returns:
        True if property exists and was set, False otherwise
    """
    if prop_name not in properties:
        return False
    value = properties[prop_name]
    if transform is not None:
        value = transform(value)
    setattr(target, field_name, value)
    return True


def extract_object_ref(
    properties: dict[str, Any],
    prop_name: str,
    target: Any,
    field_name: str,
    ref_key: str = "object_path",
) -> bool:
    """Extract object reference from properties.

    Object references are typically stored as dicts containing "object_path", "full_name", etc.
    This function extracts the value of the specified key and sets it to the target field.

    Args:
        properties: Property dictionary
        prop_name: Property name to extract
        target: Target object
        field_name: Target field name
        ref_key: Key name in the reference dict, default "object_path"

    Returns:
        True if property exists and is dict type, False otherwise
    """
    if prop_name not in properties:
        return False
    ref = properties[prop_name]
    if isinstance(ref, dict):
        setattr(target, field_name, ref.get(ref_key))
        return True
    return False


def extract_array_property(
    properties: dict[str, Any],
    prop_name: str,
    parser: Callable[[Any], list[Any]],
) -> list[Any]:
    """Extract array property from properties and parse it.

    Args:
        properties: Property dictionary
        prop_name: Property name to extract
        parser: Parse function that receives property value and returns parsed list

    Returns:
        Parsed list, returns empty list if property doesn't exist
    """
    if prop_name not in properties:
        return []
    return parser(properties[prop_name])
