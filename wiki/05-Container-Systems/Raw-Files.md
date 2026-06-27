---
title: Raw File Parsing
section: raw
---

# Raw File Parsing

## Core API

<!-- data-api="parse_raw_file" -->
```python
parse_raw_file(path: str) -> RawFileResult
```

## Supported Types

| Type | Function | Description |
|------|----------|-------------|
| `.json` | `parse_json_descriptor` | JSON descriptor |
| `.ini` | `parse_ini_file` | INI configuration file |
| `.locres` | `parse_locres` | Localization resource |
| `.locmeta` | `parse_locmeta` | Localization metadata |
| `.ogg / .wav` | `parse_audio_metadata` | Audio metadata |
