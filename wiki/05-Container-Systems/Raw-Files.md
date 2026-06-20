---
title: 原始文件解析
section: raw
---

# 原始文件解析

## 核心 API

<!-- data-api="parse_raw_file" -->
```python
parse_raw_file(path: str) -> RawFileResult
```

## 支持的类型

| 类型 | 函数 | 说明 |
|------|------|------|
| `.json` | `parse_json_descriptor` | JSON 描述符 |
| `.ini` | `parse_ini_file` | INI 配置文件 |
| `.locres` | `parse_locres` | 本地化资源 |
| `.locmeta` | `parse_locmeta` | 本地化元数据 |
| `.ogg / .wav` | `parse_audio_metadata` | 音频元数据 |
