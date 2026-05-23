# Phase 61: Kismet 表达式系统 - Discussion Log

**Date:** 2026-05-19
**Mode:** discuss (default interactive)

## Discussion Areas

### 1. 表达式类族设计
**Question:** KismetExpression 类族怎么拆分？
**Options:**
- 细粒度子类 (Recommended) — 独立子类文件，每个 dataclass + from_archive
- 单文件聚合 — 所有子类在一个 expression.py 中
- 扁平 + type 分派 — 一个 dataclass 用 type 字段区分
**Decision:** 细粒度子类。遵循现有 node_types.py 模式。

### 2. 字节码读取策略
**Question:** FKismetArchive 怎么设计？
**Options:**
- FArchive 子类 (Recommended) — 继承 FArchive，添加 kismet-specific 方法
- 独立包装器 — 内部持有 FArchive 实例
- 直接扩展 FArchive — 在 FArchive 上直接加方法
**Decision:** FArchive 子类。新建 kismet/archive.py，复用 FArchive 原语。

### 3. CUE4Parse 参考获取
**Question:** EExprToken 枚举和 KismetExpression 的参考从哪里获取？
**Options:**
- UE 源码提取 (Recommended)
- 在线 CUE4Parse
- 混合验证
**Decision:** 混合验证。优先本地 CUE4Parse（`E:\Develop\lib\CUE4Parse`），用 UE 源码验证。发现 CUE4Parse 在 `E:\Develop\lib\CUE4Parse` 路径存在完整文件。

### 4. 测试边界
**Question:** Phase 61 的测试覆盖到什么程度？
**Options:**
- 基础单元测试 (Recommended)
- 包含 roundtrip 测试
- Phase 61 不加测试
**Decision:** Phase 61 不加测试。测试从 Phase 62 开始。

## Key Discoveries

- CUE4Parse Kismet 参考文件完整可读：
  - `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Kismet\EExprToken.cs` — 126 行，~110 个 EExprToken 值
  - `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Kismet\KismetExpression.cs` — 1510 行，完整类族
  - `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Readers\FKismetArchive.cs` — 268 行，读取器实现

---

*Phase: 61-Kismet 表达式系统*
*Discussion completed: 2026-05-19*
