"""Blueprint diff mode — unified comparison output.

Compares two parsed Blueprint assets and generates structured diff output
showing structural differences between them.

Usage:
    from uasset_read.core.blueprint_diff import diff_blueprints

    diff = diff_blueprints(result_a, result_b)
    print(diff.format_unified())
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ChangeType(Enum):
    """Type of change."""
    ADDED = auto()
    REMOVED = auto()
    MODIFIED = auto()


class ChangeCategory(Enum):
    """Category of change."""
    VARIABLE = "variable"
    FUNCTION = "function"
    EVENT = "event"
    COMPONENT = "component"
    PROPERTY = "property"


@dataclass
class Change:
    """A single diff change entry."""

    change_type: ChangeType
    category: ChangeCategory
    path: str
    """Location in Blueprint hierarchy (e.g. "Variables.Health")."""

    old_value: Any = None
    new_value: Any = None

    def format_unified(self, context: int = 3) -> str:
        """Format as unified diff line."""
        prefix = {
            ChangeType.ADDED: "+",
            ChangeType.REMOVED: "-",
            ChangeType.MODIFIED: "~",
        }[self.change_type]

        line = f"{prefix} [{self.category.value}] {self.path}"
        if self.change_type == ChangeType.MODIFIED:
            line += f"  ({self.old_value} -> {self.new_value})"
        return line


@dataclass
class DiffSummary:
    """Summary of all changes."""

    total_changes: int = 0
    variables_added: int = 0
    variables_removed: int = 0
    variables_modified: int = 0
    functions_added: int = 0
    functions_removed: int = 0
    functions_modified: int = 0
    events_added: int = 0
    events_removed: int = 0

    @property
    def has_changes(self) -> bool:
        return self.total_changes > 0

    def to_dict(self) -> dict:
        return {
            "total_changes": self.total_changes,
            "variables": {
                "added": self.variables_added,
                "removed": self.variables_removed,
                "modified": self.variables_modified,
            },
            "functions": {
                "added": self.functions_added,
                "removed": self.functions_removed,
                "modified": self.functions_modified,
            },
            "events": {
                "added": self.events_added,
                "removed": self.events_removed,
            },
        }


@dataclass
class BlueprintDiff:
    """Complete diff result between two Blueprint assets."""

    changes: list[Change] = field(default_factory=list)
    summary: DiffSummary = field(default_factory=DiffSummary)

    @property
    def has_changes(self) -> bool:
        return self.summary.has_changes

    def format_unified(self) -> str:
        """Format as unified diff output."""
        lines: list[str] = []

        lines.append(f"=== Blueprint Diff ({self.summary.total_changes} changes) ===")
        lines.append("")

        # Group by category
        by_category: dict[str, list[Change]] = {}
        for change in self.changes:
            cat = change.category.value
            by_category.setdefault(cat, []).append(change)

        for category, changes in sorted(by_category.items()):
            lines.append(f"--- {category} ---")
            for change in changes:
                lines.append(change.format_unified())
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "summary": self.summary.to_dict(),
            "changes": [
                {
                    "type": c.change_type.name.lower(),
                    "category": c.category.value,
                    "path": c.path,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                }
                for c in self.changes
            ],
        }


def _index_by_name(items: list, name_attr: str = "name") -> dict[str, Any]:
    """Index a list of objects by their name attribute."""
    result = {}
    for item in items:
        name = getattr(item, name_attr, None)
        if name:
            result[name] = item
    return result


def _compare_variables(
    vars_a: dict[str, Any],
    vars_b: dict[str, Any],
) -> list[Change]:
    """Compare two sets of variables."""
    changes: list[Change] = []

    for name, var_a in vars_a.items():
        if name not in vars_b:
            changes.append(Change(
                change_type=ChangeType.REMOVED,
                category=ChangeCategory.VARIABLE,
                path=f"Variables.{name}",
                old_value=var_a,
            ))
        else:
            # Compare type
            type_a = getattr(var_a, "variable_type", None)
            type_b = getattr(vars_b[name], "variable_type", None)
            if type_a != type_b:
                changes.append(Change(
                    change_type=ChangeType.MODIFIED,
                    category=ChangeCategory.VARIABLE,
                    path=f"Variables.{name}.type",
                    old_value=type_a,
                    new_value=type_b,
                ))

    for name in vars_b:
        if name not in vars_a:
            changes.append(Change(
                change_type=ChangeType.ADDED,
                category=ChangeCategory.VARIABLE,
                path=f"Variables.{name}",
                new_value=vars_b[name],
            ))

    return changes


def _compare_functions(
    funcs_a: dict[str, Any],
    funcs_b: dict[str, Any],
) -> list[Change]:
    """Compare two sets of functions."""
    changes: list[Change] = []

    for name in funcs_a:
        if name not in funcs_b:
            changes.append(Change(
                change_type=ChangeType.REMOVED,
                category=ChangeCategory.FUNCTION,
                path=f"Functions.{name}",
            ))
        # Note: full function comparison would require bytecode diff

    for name in funcs_b:
        if name not in funcs_a:
            changes.append(Change(
                change_type=ChangeType.ADDED,
                category=ChangeCategory.FUNCTION,
                path=f"Functions.{name}",
            ))

    return changes


def _compare_events(
    events_a: dict[str, Any],
    events_b: dict[str, Any],
) -> list[Change]:
    """Compare two sets of events."""
    changes: list[Change] = []

    for name in events_a:
        if name not in events_b:
            changes.append(Change(
                change_type=ChangeType.REMOVED,
                category=ChangeCategory.EVENT,
                path=f"Events.{name}",
            ))

    for name in events_b:
        if name not in events_a:
            changes.append(Change(
                change_type=ChangeType.ADDED,
                category=ChangeCategory.EVENT,
                path=f"Events.{name}",
            ))

    return changes


def diff_blueprints(
    result_a: Any,
    result_b: Any,
) -> BlueprintDiff:
    """Compare two parsed Blueprint results and generate a diff.

    Args:
        result_a: First parse result (ParseResult)
        result_b: Second parse result (ParseResult)

    Returns:
        BlueprintDiff with changes and summary
    """
    diff = BlueprintDiff()

    # Get metadata
    meta_a = getattr(result_a, "blueprint_metadata", None)
    meta_b = getattr(result_b, "blueprint_metadata", None)

    if meta_a and meta_b:
        # Compare variables (BlueprintVariable uses var_name attribute)
        vars_a = _index_by_name(getattr(meta_a, "variables", []) or [], name_attr="var_name")
        vars_b = _index_by_name(getattr(meta_b, "variables", []) or [], name_attr="var_name")
        diff.changes.extend(_compare_variables(vars_a, vars_b))

        # Compare functions
        funcs_a = _index_by_name(getattr(meta_a, "functions", []) or [])
        funcs_b = _index_by_name(getattr(meta_b, "functions", []) or [])
        diff.changes.extend(_compare_functions(funcs_a, funcs_b))

        # Compare events
        events_a = _index_by_name(getattr(meta_a, "events", []) or [])
        events_b = _index_by_name(getattr(meta_b, "events", []) or [])
        diff.changes.extend(_compare_events(events_a, events_b))

    # Build summary
    summary = DiffSummary(total_changes=len(diff.changes))
    for change in diff.changes:
        if change.category == ChangeCategory.VARIABLE:
            if change.change_type == ChangeType.ADDED:
                summary.variables_added += 1
            elif change.change_type == ChangeType.REMOVED:
                summary.variables_removed += 1
            elif change.change_type == ChangeType.MODIFIED:
                summary.variables_modified += 1
        elif change.category == ChangeCategory.FUNCTION:
            if change.change_type == ChangeType.ADDED:
                summary.functions_added += 1
            elif change.change_type == ChangeType.REMOVED:
                summary.functions_removed += 1
            elif change.change_type == ChangeType.MODIFIED:
                summary.functions_modified += 1
        elif change.category == ChangeCategory.EVENT:
            if change.change_type == ChangeType.ADDED:
                summary.events_added += 1
            elif change.change_type == ChangeType.REMOVED:
                summary.events_removed += 1

    diff.summary = summary
    return diff
