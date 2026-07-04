---
title: Package Management
section: package
---

# Package Management

`package.py` manages .uasset + .uexp file bundling.

## Core Classes

<!-- data-api="PackageBundle" -->
```python
PackageBundle — main_path, package_kind, container, files, payloads, provider
```

<!-- data-api="PackageArchive" -->
```python
PackageArchive(main_archive, uexp_archive, tolerant)  # .uasset + .uexp merged
```

## Provider Types

| Provider | Container | Description |
|----------|-----------|-------------|
| `FileSystemPackageProvider` | filesystem | Direct file system |
| `PakPackageProvider` | pak | PAK container |
| `IoStorePackageProvider` | iostore | IoStore container |

**Related Sections**: [[Parsing Pipeline]] · [[PAK]]
