# Phase 78 Index — UObject 继承树 + PackageLinker 重构

**Milestone:** v14.0 — CUE4Parse 核心对齐  
**Requirements:** COR-03, COR-04  
**Status:** Planned  
**Updated:** 2026-05-27

## 目标

把当前 `uasset_read` 的 linker 体系从“本包对象壳 + 局部 preload”推进到更接近 CUE4Parse 的 **Package-centered + lazy + provider-aware** 架构。

Phase 78 不直接实现完整 IoStore，但要先把接口边界和主路径收敛好，避免 Phase 79 再返工 graph / linker / package 解析链。

## 计划索引

| Plan | Wave | Focus | Requirement | 状态 |
|------|------|-------|-------------|------|
| [78-01](./78-01-PLAN.md) | 1 | 反射层次、导出类标签、SuperField、class/template 引用 | COR-03 | ⬜ Planned |
| [78-02](./78-02-PLAN.md) | 2 | 独立 archive、生命周期交接、属性时序、位置安全 preload | COR-04 | ⬜ Planned |
| [78-03](./78-03-PLAN.md) | 3 | Provider、跨包解析、linker 入口/graph 单一路径、`/Script/` 占位符 | COR-04 | ⬜ Planned |

## 覆盖矩阵

| CUE4Parse 参考能力 | 78-01 | 78-02 | 78-03 | 后续 |
|--------------------|-------|-------|-------|------|
| UObject 反射层次 | ✅ | - | - | - |
| 导出类标签分层 | ✅ | - | - | - |
| Super / Template / Class 引用 | ✅ | - | - | - |
| Linker archive 生命周期 | - | ✅ | - | - |
| Linker 入口时序收敛 | - | ✅ | ✅ | - |
| Lazy preload + save/restore | - | ✅ | - | - |
| Package-centered resolver | - | 部分 | ✅ | - |
| Graph linker-aware 主路径 | - | 部分 | ✅ | - |
| `/Script/` import 占位符策略 | - | - | ✅ | - |
| 跨包 import provider 接口 | - | - | ✅ | Phase 79 落地 |
| IoStore `FPackageObjectIndex` | - | - | 接口预留 | Phase 79 |

## 执行顺序

1. `78-01`：先把反射层次与导出类标签拆开，补齐 SuperField 链。  
2. `78-02`：再稳定 archive 生命周期、linker 入口时序、lazy preload。  
3. `78-03`：最后收敛 graph / resolver / provider 边界，形成可供 Phase 79 扩展的主架构。

## 设计约束

- `graph` / `blueprint` / `property` 解析不再长期维持“有 linker / 无 linker”双轨主实现。
- `parse_uasset_with_linker()` 不再保留“先无 linker 解析一轮 export properties”的长期主路径。
- `PackageLinker` 继续负责本包对象图，但要抽出 provider/resolver 接口承接跨包解析。
- `/Script/` import 保持占位符，不引入真实脚本包加载。
- linker 持有的 archive 不在函数返回前关闭，生命周期由 result/context manager 管理。
- IoStore 特有 `PublicExportHash` / `FPackageObjectIndex` 不在 Phase 78 实装，但接口命名要避免把传统 `FPackageIndex` 写死到所有调用方。
