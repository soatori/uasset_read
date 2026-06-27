---
title: 包管理
section: package
---

# 包管理

`package.py` 管理 .uasset + .uexp 文件捆绑。

## 核心类

<!-- data-api="PackageBundle" -->
```python
PackageBundle — main_path, package_kind, container, files, payloads, provider
```

<!-- data-api="PackageArchive" -->
```python
PackageArchive(main_archive, uexp_archive, tolerant)  # .uasset + .uexp 合并
```

## Provider 类型

| Provider | 容器 | 说明 |
|----------|------|------|
| `FileSystemPackageProvider` | filesystem | 直接文件系统 |
| `PakPackageProvider` | pak | PAK 容器 |
| `IoStorePackageProvider` | iostore | IoStore 容器 |

**相关章节**: [[解析管线]] · [[PAK]]
