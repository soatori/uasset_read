"""PackageSource field semantics analyzer.

Interprets the PackageSource uint32 field to identify asset provenance:
shipping vs non-shipping builds, modder-made vs Epic-made assets.

Reference: UE source — UPackage::PackageSource is set during save:
  - Shipping builds: random number (high entropy)
  - Non-shipping builds: CRC32 of uppercased filename

Usage:
    from uasset_read.core.package_source import interpret_package_source

    info = interpret_package_source(0x12345678, "MyAsset")
    print(info.build_type)      # "non-shipping"
    print(info.is_crc)          # True
    print(info.description)     # "CRC32 of filename"
"""

from dataclasses import dataclass


@dataclass
class PackageSourceInfo:
    """Interpreted PackageSource field information."""

    value: int
    """Raw uint32 value from PackageSource field."""

    build_type: str
    """Classified build type: 'shipping', 'non-shipping', 'unset', 'unknown'."""

    is_random: bool
    """True if value appears to be a random number (shipping build)."""

    is_crc: bool
    """True if value appears to be a CRC32 of filename (non-shipping build)."""

    description: str
    """Human-readable description of the value."""

    @property
    def is_shipping(self) -> bool:
        """True if this appears to be a shipping build asset."""
        return self.build_type == "shipping"

    @property
    def is_editor(self) -> bool:
        """True if this appears to be an editor-saved asset."""
        return self.build_type == "non-shipping"

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "value": self.value,
            "build_type": self.build_type,
            "is_random": self.is_random,
            "is_crc": self.is_crc,
            "description": self.description,
        }


def _crc32_uppercase_filename(filename: str | None) -> int:
    """Compute CRC32 of uppercased filename (matches UE's behavior)."""
    if not filename:
        return 0
    import binascii
    return binascii.crc32(filename.upper().encode("utf-8")) & 0xFFFFFFFF


def interpret_package_source(
    value: int,
    filename: str | None = None,
) -> PackageSourceInfo:
    """Interpret PackageSource field value.

    In UE, PackageSource is:
      - Shipping builds: random number (typically large, high entropy)
      - Non-shipping builds: CRC32 of uppercased package filename
      - 0: unset or unknown

    Args:
        value: Raw uint32 PackageSource value
        filename: Original filename for CRC verification (optional)

    Returns:
        PackageSourceInfo with classification and metadata
    """
    if value == 0:
        return PackageSourceInfo(
            value=0,
            build_type="unset",
            is_random=False,
            is_crc=False,
            description="Unset (value is 0)",
        )

    # Heuristic: CRC32 values are evenly distributed across 32-bit space.
    # Shipping random values also use full range, but we can cross-check
    # with filename if available.
    is_likely_random = value > 0xF0000000

    # If filename provided, compute expected CRC and compare
    if filename:
        expected_crc = _crc32_uppercase_filename(filename)
        if expected_crc == value:
            return PackageSourceInfo(
                value=value,
                build_type="non-shipping",
                is_random=False,
                is_crc=True,
                description=f"CRC32 of '{filename.upper()}' (matches)",
            )
        elif expected_crc != 0:
            return PackageSourceInfo(
                value=value,
                build_type="shipping" if is_likely_random else "unknown",
                is_random=is_likely_random,
                is_crc=False,
                description=(
                    f"Does not match CRC32 of '{filename.upper()}' "
                    f"(expected 0x{expected_crc:08X})"
                ),
            )

    # No filename to compare — use heuristic
    if is_likely_random:
        return PackageSourceInfo(
            value=value,
            build_type="shipping",
            is_random=True,
            is_crc=False,
            description="Likely random value (shipping build)",
        )
    else:
        return PackageSourceInfo(
            value=value,
            build_type="non-shipping",
            is_random=False,
            is_crc=True,
            description="Likely CRC32 of filename (non-shipping build)",
        )
