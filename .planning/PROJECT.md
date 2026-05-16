# uasset_read

Python 工具读取 Unreal Engine .uasset 文件（未烘焙蓝图），让 AI agent 直接解析内容。

**技术栈**: Python 3.10+，零运行时依赖 | **架构**: `.uasset → FArchive → 序列化 → 数据模型 → 属性解析 → 蓝图图 → 格式化输出 → PackageLinker`

**源码参考**: `E:\Develop\lib\UnrealEngine` (UE 5.7，只读)

## 里程碑

| 版本 | 范围 | 日期 |
|------|------|------|
| v1.0 | MVP | 2026-04-28 |
| v2.0 | 蓝图图解析 | 2026-05-02 |
| v5.1 | src layout + pyproject.toml | 2026-05-07 |
| v6.0 | ✅ 模块化重构 | 2026-05-13 |
| v7.0 | ✅ UE FLinkerLoad 对象图重建 + 技术债清理 | 2026-05-14 |
| **v8.0** | ✅ BP-to-CPP JSON 可翻译性 (Phase 47-51) | 2026-05-17 |

**历史**: `.planning/milestones/` | **详情**: `.planning/ROADMAP.md`

## 当前状态

**已发布**: v8.0 — BP-to-CPP JSON 可翻译性

`BP_FirstPersonCharacter.uasset` JSON 输出已覆盖 C++ 对照所需：
- ✅ 组件声明 + 构造函数数值（位置/旋转/缩放/标志）
- ✅ 函数签名（参数名+类型+默认值+方向）
- ✅ 输入绑定（Action→Trigger→函数）
- ✅ 执行流（BeginPlay→函数链）

**预存在问题**: 26 个测试失败（资产版本 -8 vs -9，pre-existing）

## Out of Scope

导出纹理/模型 | 修改 .uasset | Cooked 资产 | 蓝图字节码反编译 | C++ 代码生成 | MCP Server

## 关键决策

零依赖 ✓ | 参考 UE 源码 ✓ | JSON 优先 ✓ | FArchive 管道模式 ✓ | v7.0 增量采用 ✓ | v8.0 按 gap 分 phase ✓

<details>
<summary>v7.0 已解决技术债</summary>

- **Phase 44a**: 移除旧版本/UE4 兼容代码 ✅
- **Phase 44b**: 替换直接字节读取为 FArchive 方法 ✅
- **Phase 44c**: 清理废弃测试工具 ✅

</details>

---

*Last updated: 2026-05-17 after v8.0 milestone*
