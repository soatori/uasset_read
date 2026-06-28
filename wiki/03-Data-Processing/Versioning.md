---
title: Version Management
section: versioning
---

# Version Management

<!-- data-api="build_version_container" -->
```python
build_version_container(summary) → VersionContainer
```

## CustomVersion GUIDs

| GUID | Name | Description |
|------|------|-------------|
| `FFrameworkObjectVersion` | Framework Object Version | Blueprint graph structure version |
| `FUE5MainStreamObjectVersion` | UE5 Mainstream Version | UE5 core version |
| `FReleaseObjectVersion` | Release Object Version | UE release version |

> [!TIP]
> Version management is responsible for reading and unifying version numbers of various CustomVersion GUIDs from PackageFileSummary.
>
> **Related Sections**: [[Serializers]] · [[Parsers]]
