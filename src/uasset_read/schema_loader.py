"""Centralized schema loading via importlib.resources.

Works both in local development (reading from src/) and when
the package is pip-installed (reading from the wheel).
"""
from __future__ import annotations

import json
from typing import Any


def load_semantic_schema() -> dict[str, Any]:
    """Load the semantic JSON schema from the bundled package data.

    Returns:
        Parsed JSON schema as a dict.

    Raises:
        FileNotFoundError: If the schema file is missing from the package.
    """
    try:
        from importlib.resources import files
        ref = files("uasset_read.schemas").joinpath("semantic.schema.json")
        with ref.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, TypeError):
        # Fallback for Python 3.9 or if importlib.resources fails
        from pathlib import Path
        schema_path = Path(__file__).parent / "schemas" / "semantic.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(
                f"semantic.schema.json not found at {schema_path}"
            )
        return json.loads(schema_path.read_text(encoding="utf-8"))


def load_blueprint_semantic_schema() -> dict[str, Any]:
    """Load the Blueprint semantic JSON schema from the bundled package data.

    Returns:
        Parsed JSON schema as a dict.

    Raises:
        FileNotFoundError: If the schema file is missing from the package.
    """
    try:
        from importlib.resources import files
        ref = files("uasset_read.schemas").joinpath("blueprint_semantic.schema.json")
        with ref.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, TypeError):
        # Fallback for Python 3.9 or if importlib.resources fails
        from pathlib import Path
        schema_path = Path(__file__).parent / "schemas" / "blueprint_semantic.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(
                f"blueprint_semantic.schema.json not found at {schema_path}"
            )
        return json.loads(schema_path.read_text(encoding="utf-8"))
