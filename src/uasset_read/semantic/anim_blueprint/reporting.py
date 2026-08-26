"""Animation Blueprint coverage entries and aggregated diagnostics.

Reuses the BlueprintReporting implementation from the blueprint module.
"""

from uasset_read.semantic.blueprint.reporting import BlueprintReporting

__all__ = ["AnimBlueprintReporting"]

# Alias for consistency with animation blueprint module naming
AnimBlueprintReporting = BlueprintReporting
