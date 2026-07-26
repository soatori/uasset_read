"""Internal parse pipeline package.

Consolidates the uasset parse lifecycle (stages, config, memory, error handling,
post-processing, and the core entry points) into a single internal package.

Usage from outside the package should go through the re-export shims in
``uasset_read.parse_stages``, ``uasset_read.parse_uasset``, etc., so that
existing import paths keep working.
"""
