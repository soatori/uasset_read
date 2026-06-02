# 开发范围及统一性设计 — 细化版

**日期**: 2026-06-03  
**版本**: 0.3.8-beta  
**状态**: 已批准，待实施  
**作者**: uasset_read Contributors

---

## 1. 项目定位

**uasset_read** 是一个专为 AI 代理设计的虚幻引擎 `.uasset` 文件 **只读** Python 解析器，使 AI 代理无需 UE 编辑器即可读取和理解蓝图内容。

### 1.1 核心目标
- 提供对未烘焙/编辑器保存的 `.uasset` 文件的完整读取能力
- 使 AI 代理能够理解蓝图逻辑、变量、函数调用关系
- 输出结构化数据（JSON/Text/Markdown/C++ 骨架等格式）
- 保持零运行时依赖的轻量级设计

### 1.2 只读定位约束（全局适用）

所有功能必须围绕 **"读取 → 解析 → 输出"** 这一单向数据流设计：

| 约束 | 说明 |
|------|------|
| **不修改文件** | 禁止任何形式的文件写入、修改、回写 |
| **单向数据流** | `.uasset` → 解析器 → 输出格式，不可逆 |
| **接口签名** | 所有公共 API 必须体现只读性（`parse_*`、`export_*`、`read_*`） |
| **文档用语** | 禁止使用"保存"、"写入"、"序列化"（指写入时）等暗示写入的表述 |
| **自定义处理器** | 只能读取 archive 数据，不能 seek 回写 |

---

## 2. 资产类型支持矩阵

### 2.1 支持级别定义

| 级别 | 名称 | 含义 | 测试要求 |
|------|------|------|----------|
| **L4** | 完整解析 | 二进制结构 + 属性 + 图数据 + 业务逻辑（蓝图/Kismet） | 集成测试 + 单元测试 |
| **L3** | 结构解析 | 二进制结构 + 属性数据 + BulkData 头部 | 集成测试 |
| **L2** | 基础元数据 | 名称表、导入导出表、属性标签 | 单元测试 |
| **L1** | 摘要信息 | 仅 PackageFileSummary | 无 |
| **L0** | 不支持 | 无法解析或标记 xfail | 标记 xfail |

### 2.2 资产类型矩阵

#### 蓝图类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| Blueprint / BlueprintGeneratedClass | L4 | 变量、图、Kismet、调用链 |
| AnimBlueprint | L4 | 动画特定节点 + 事件图 |
| LevelScriptBlueprint | L3 | Actor 脚本逻辑 |
| MacroLibrary | L3 | 宏节点解析 |
| WidgetBlueprint | L2 | 基础元数据，Widget 绑定有限支持 |

#### 网格体类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| SkeletalMesh | L3 | 骨骼结构、LOD、顶点数据、材质槽 |
| StaticMesh | L3 | LOD、碰撞、顶点数据、材质槽 |
| MorphTarget | L2 | 变形目标数据 |
| Skeleton | L2 | 骨骼层次 |
| Landscape | L2 | 地形基础数据 |
| GeometryCache | L0 | 几何缓存，暂不支持 |

#### 材质类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| Material | L3 | 属性、材质表达式 |
| MaterialInstanceConstant | L3 | 父材质引用、参数覆盖 |
| MaterialFunction | L2 | 函数定义，有限支持 |
| MaterialParameterCollection | L2 | 参数集合 |

#### 纹理类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| Texture2D | L3 | 纹理属性、BulkData 头部 |
| Texture2DArray | L2 | 纹理数组基础 |
| TextureCube | L2 | 立方体贴图基础 |
| TextureRenderTarget2D | L1 | 仅摘要 |
| LightMapTexture2D | L1 | 仅摘要 |
| VirtualTexture2D | L1 | 仅摘要 |

#### 动画类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| AnimSequence | L2 | 基础元数据，压缩数据不解压 |
| AnimMontage | L2 | 基础元数据 |
| AimOffset | L2 | 基础元数据 |

#### 粒子/Niagara 类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| NiagaraSystem | L3 | 粒子系统结构 |
| NiagaraEmitter | L3 | 发射器定义 |
| ParticleSystem (UE4) | L3 | UE4 粒子系统（legacy_file_version -8/-9） |
| P_Fire (UE4 legacy=-3) | L0 | 已知缺陷，标记 xfail |

#### 音频类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| SoundWave | L2 | 基础属性，音频数据不解析 |
| SoundCue | L2 | 音频图结构 |
| MetaSoundPatch | L1 | 仅摘要 |

#### 关卡/世界分区类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| Map/Level | L3 | Actor 层次结构、World Partition |
| WorldPartition | L2 | 世界分区基础 |
| LevelInstance | L2 | 关卡实例基础 |
| DataLayer | L2 | 数据层配置 |

#### 输入类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| InputAction | L3 | 输入动作配置 |
| InputMappingContext | L3 | 映射上下文 |

#### 数据表类

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| DataTable | L2 | 行结构，具体数据有限解析 |
| CurveTable | L2 | 曲线数据基础 |
| StringTable | L2 | 字符串表 |

#### 其他基础类型

| 类型范围 | 级别 | 说明 |
|----------|------|------|
| 所有未在以上列出的 UObject 子类 | L2 | 通过通用属性解析器读取基础元数据 |

### 2.3 统一性约束

1. **渐进支持规则**：新增资产类型必须从 L2 → L3 → L4 渐进，不允许跳过级别
2. **L3+ 必须有专用解析器**：位于 `parsers/asset_types/` 目录
3. **L3+ 必须有集成测试**：至少 1 个真实资产测试用例
4. **降级必须有日志**：不支持的类型必须记录警告并返回 L2 基础数据
5. **L0 必须有 xfail**：已知缺陷资产在测试中标记 xfail，不阻塞 CI

---

## 3. 错误处理分级体系

### 3.1 错误分级定义

| 级别 | 名称 | 标志 | 行为（tolerant） | 行为（strict） | 示例 |
|------|------|------|------------------|----------------|------|
| **E0** | Info | `INFO` | 记录，继续 | 记录，继续 | 版本检测提示、可选数据缺失 |
| **E1** | Warning | `WARN` | 记录，继续 | 记录，继续 | 非关键字段解析失败、未知属性类型 |
| **E2** | Recoverable Error | `ERR_RECOVERABLE` | 尝试恢复，继续 | **停止**，返回错误 | PropertyTag 偏移异常、BulkData 损坏 |
| **E3** | Fatal Error | `ERR_FATAL` | 停止，返回部分结果 | 停止，返回错误 | 文件头损坏、版本不支持 |
| **E4** | Panic | `ERR_PANIC` | 停止，返回空结果 | 停止，返回错误 | 内存越界、安全网触发 |

### 3.2 ErrorContext 统一结构

```python
class ErrorContext(TypedDict):
    file_path: str
    offset: int              # 当前文件偏移
    version: str             # UE 版本
    asset_type: str          # 检测到的资产类型
    severity: str            # E0|E1|E2|E3|E4
    message: str
    recovery: Optional[str]  # 恢复措施（仅 E2）
```

### 3.3 行为规则

1. tolerant 模式下 E3 返回部分结果，已解析数据仍可用（`result.is_success = False`）
2. strict 模式 E2+ 立即停止，不尝试任何恢复
3. CLI 退出码统一：E0/E1 → 0，E2(tolerant) → 1，E3+ → 2
4. E2 恢复机制必须有日志去重：相同类型的重复错误只记录一次

---

## 4. 代码统一性约束：避免重复

### 4.1 基本原则

| 原则 | 规则 |
|------|------|
| **单一错误入口** | 所有错误通过统一 `raise_error()` / `log_warn()` 函数记录 |
| **错误常量集中** | E0-E4 级别常量定义在 `constants.py` |
| **恢复逻辑抽取** | 相同类型的恢复逻辑抽取为独立函数，禁止复制粘贴 |
| **ErrorContext 统一构造** | 通过工厂函数构造，禁止手动组装 dict |
| **日志格式统一** | 格式模板定义在一处，所有模块共用 |

### 4.2 架构层面的防重复机制

1. **属性解析器注册表模式**（已存在，需巩固）
   - 40+ 种属性解析器通过 `CUSTOM_PROPERTY_HANDLERS` 注册表统一管理
   - 新增解析器只需注册，不需要修改分发逻辑
   - 禁止在 `parse_property_value()` 中写 `if/elif` 链

2. **节点类型读取器模式**（已存在，需巩固）
   - `read_k2node_call_function`、`read_k2node_event` 等通过节点类型分发
   - 新增节点类型只需添加读取器并注册
   - 禁止在 `read_ue_graph_node()` 中直接写 `if node_type == "..."`

3. **资产类型解析器模式**（已存在，需扩展）
   - `parsers/asset_types/` 中每个文件负责一种资产类型
   - 通过类名自动路由（参考 `ObjectTypeRegistry` 模式）
   - 禁止在核心解析管线中硬编码资产类型判断

4. **版本常量单一来源**
   - 所有 UE 版本常量只在 `constants.py` 定义
   - 其他模块一律 import，禁止复制数值

5. **格式化器接口统一**
   - 所有格式化器实现 `format_xxx()` 签名：`def format_xxx(data, options) -> str`
   - 禁止一个用返回值、一个用写入文件、一个用 print

---

## 5. 未知和自定义资产类型的处理策略

### 5.1 场景分类

| 场景 | 示例 | 说明 |
|------|------|------|
| **游戏自定义类型** | `FortItemDefinition`、`BL3Objects` | 游戏项目自定义的 UObject 子类 |
| **插件类型** | `DLSS`、`ACE`、`Wwise` 中间件资产 | 第三方插件引入的类型 |
| **新 UE 版本类型** | UE 5.5+ 新增的资产类型 | 尚未被解析器支持的官方类型 |
| **自定义属性类型** | 游戏项目扩展的 FPropertyTag 类型 | 非标准属性类型 |

### 5.2 未知资产类型分级处理

| 步骤 | 行为 | 输出 |
|------|------|------|
| **Step 1: 类名匹配** | 尝试在类型注册表中查找 | 找到 → 使用专用解析器 |
| **Step 2: 父类回退** | 检查是否是已知父类的子类（如 `XXXBlueprint` → `Blueprint`） | 匹配父类 → 使用父类解析器 |
| **Step 3: 通用解析器** | 无法匹配任何已知类型时，使用通用 UObject 解析器 | 返回 L2 基础元数据 |
| **Step 4: 原始数据** | 通用解析也失败时，仅记录 PackageFileSummary | 返回 L1 摘要 |

### 5.3 未知属性类型分级处理

| 场景 | 行为 | 日志级别 |
|------|------|----------|
| 属性类型名在已知类型表中 | 使用对应解析器 | — |
| 属性类型名不在表中，但值 ≤ 属性类型阈值 | 使用序号映射（旧版 UE4） | E1 Warning |
| 属性类型名不在表中，且值 > 阈值 | 跳过该属性，记录未知类型 | E1 Warning |
| 属性类型在自定义处理器注册表中 | 使用自定义处理器 | — |

### 5.4 自定义属性处理器扩展

```python
# 用户/项目扩展方式
from uasset_read import register_custom_property, CustomPropertyContext

@register_custom_property("CustomGameplayTag")
def parse_custom_gameplay_tag(ctx: CustomPropertyContext) -> PropertyValue:
    """处理游戏自定义的 GameplayTag 属性"""
    # 解析逻辑...
    return parsed_value
```

**约束**：
- 自定义处理器必须实现 `parse(ctx) -> PropertyValue` 接口
- 自定义处理器的异常被视为 E2（可恢复），不阻断后续解析
- 自定义处理器只影响注册了它的项目，不影响核心解析

### 5.5 统一性约束（未知类型）

1. **未知类型不抛异常**：未知类型必须优雅降级（L2 → L1），而不是直接报错
2. **每次未知类型记录必须包含**：`asset_type`、`class_name`、`file_path`、`offset`
3. **相同未知类型日志去重**：同一文件中相同的未知类型只记录一次 Warning
4. **自定义处理器必须有隔离**：自定义处理器的异常不能污染核心解析管线
5. **回退链必须可配置**：用户可以通过配置禁用某些回退步骤

---

## 6. 未知但结构可识别类型的诊断输出

### 6.1 场景定义

当解析器遇到未知类型，但能够识别其基本结构（如确认是标准 UObject 布局、有可读取的 PropertyTag 列表），输出关键字符供后续分析。

### 6.2 输出结构

```json
{
  "status": {
    "diagnostics": {
      "unknown_types": [
        {
          "class_name": "CustomFortItemDefinition",
          "object_name": "DA_Sword_Common",
          "outer_path": "/Game/Items/Weapons/Sword",
          "serial_offset": 1024,
          "serial_size": 2048,
          "properties_sample": [
            {"name": "DisplayName", "type": "TextProperty"},
            {"name": "Rarity", "type": "ByteProperty"},
            {"name": "CustomGameData", "type": "UnknownType"}
          ],
          "properties_truncated": true,
          "properties_total_count": 35
        }
      ]
    }
  }
}
```

### 6.3 限制约束

| 限制项 | 值 | 说明 |
|--------|-----|------|
| **属性样本数量** | ≤ 20 个 | 避免输出过多数据 |
| **类型名称长度** | ≤ 128 字符 | 防止恶意长字符串 |
| **对象路径长度** | ≤ 256 字符 | 同上 |
| **单个文件诊断条目** | ≤ 10 个 | 避免同一文件大量未知类型 |
| **总计诊断条目** | ≤ 50 个/次解析 | 全局上限 |
| **原始二进制采样** | 不允许 | 仅输出结构化信息，不输出原始字节 |

### 6.4 使用场景

1. **开发者分析新游戏资产**：运行解析器后查看 `diagnostics.unknown_types`，了解需要添加哪些类型的支持
2. **用户报告问题**：提供诊断输出给维护者，帮助定位解析失败原因
3. **自动化类型发现**：批量扫描后统计未知类型出现频率，优先实现高频类型

---

## 7. 测试策略

### 7.1 未知类型测试

| 测试类型 | 用例 | 验证 |
|----------|------|------|
| 未知资产类型 | 使用一个不存在于注册表中的 class_name | 验证降级到 L2，返回基础元数据 |
| 未知属性类型 | 手动构造包含未知 PropertyTag 的测试数据 | 验证跳过该属性，继续解析后续属性 |
| 自定义处理器 | 注册一个自定义处理器并解析 | 验证自定义处理器被正确调用 |
| 自定义处理器异常 | 自定义处理器抛出异常 | 验证记录 E2 错误，不阻断后续解析 |
| 诊断输出限制 | 构造大量未知类型 | 验证诊断输出不超过限制 |

### 7.2 现有测试要求（保持不变）

- ≥ 200 个单元测试
- ≥ 40 个集成测试
- 100% 通过率（xfail 除外）
- 至少 12 种资产类型覆盖
- 稳定资产必须通过 strict 和 tolerant 双模式

---

## 8. 未来可能的扩展方向（需另行规划）

1. **Cooked 资产支持** — 需要研究 UE cooked 格式
2. **写入能力** — 需要完整的序列化器实现（非当前阶段）
3. **更多资产类型** — 根据需求扩展专用解析器
4. **游戏特定解析器目录** — 按游戏项目组织自定义类型
5. **性能优化** — 并行解析、缓存机制
6. **Web API** — 提供 HTTP 接口服务

---

**版本**: 0.3.8-beta  
**最后更新**: 2026-06-03  
**维护者**: uasset_read Contributors
