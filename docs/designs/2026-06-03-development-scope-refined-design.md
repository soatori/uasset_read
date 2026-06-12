# 开发范围及统一性设计

**日期**: 2026-06-03 | **状态**: 已批准

## 1. 项目定位

**只读** `.uasset` 解析器，单向数据流：`.uasset` → 解析 → 输出。

| 铁律 | 说明 |
|------|------|
| 零写入 | 禁止修改/回写/保存 .uasset |
| 接口签名 | 仅 `parse_*`、`export_*`、`read_*` |
| 文档用语 | 禁用"保存/写入/序列化(写入)" |
| 自定义处理器 | 仅可读 archive，不可 seek 回写 |

---

## 2. 资产类型支持矩阵

### 支持级别

| 级别 | 含义 | 测试要求 |
|------|------|----------|
| **L4** | 完整解析（结构+属性+图+逻辑） | 集成+单元 |
| **L3** | 结构解析（结构+属性+BulkData头部） | 集成 |
| **L2** | 基础元数据（名称表+导入导出+属性标签） | 单元 |
| **L1** | 仅 PackageFileSummary | — |
| **L0** | 不支持 / xfail | xfail |

### 资产矩阵

| 资产类型 | 级别 | 说明 |
|----------|------|------|
| Blueprint / BPGC | L4 | 变量、图、Kismet、调用链 |
| AnimBlueprint | L4 | 动画节点+事件图 |
| LevelScriptBlueprint | L3 | Actor 脚本逻辑 |
| MacroLibrary | L3 | 宏节点解析 |
| WidgetBlueprint | L2 | 基础元数据 |
| SkeletalMesh | L3 | 骨骼、LOD、顶点、材质槽 |
| StaticMesh | L3 | LOD、碰撞、顶点、材质槽 |
| MorphTarget / Skeleton / Landscape | L2 | 基础数据 |
| GeometryCache | L0 | 暂不支持 |
| Material | L3 | 属性+表达式 |
| MaterialInstanceConstant | L3 | 父材质+参数覆盖 |
| MaterialFunction / MPC | L2 | 有限支持 |
| Texture2D | L3 | 属性+BulkData 头部 |
| Texture2DArray / TextureCube | L2 | 基础数据 |
| TextureRenderTarget/LightMap/Virtual | L1 | 仅摘要 |
| AnimSequence / AnimMontage / AimOffset | L2 | 基础元数据，压缩数据不解压 |
| NiagaraSystem / NiagaraEmitter | L3 | 粒子结构 |
| ParticleSystem (UE4) | L3 | legacy -8/-9 |
| P_Fire (UE4 legacy=-3) | L0 | xfail |
| SoundWave / SoundCue | L2 | 基础属性，音频数据不解析 |
| MetaSoundPatch | L1 | 仅摘要 |
| Map/Level | L3 | Actor 层次+World Partition |
| WorldPartition / LevelInstance / DataLayer | L2 | 基础数据 |
| InputAction / InputMappingContext | L3 | 输入配置 |
| DataTable / CurveTable / StringTable | L2 | 基础数据 |
| 其他 UObject 子类 | L2 | 通用解析器 |

### 约束
1. L2 → L3 → L4 渐进，不可跳级
2. L3+ 必须有 `parsers/asset_types/` 专用解析器 + 集成测试
3. 降级必须记录警告，L0 必须 xfail

---

## 3. 错误处理分级

### 分级定义

| 级别 | tolerant | strict | 示例 |
|------|----------|--------|------|
| **E0** Info | 记录继续 | 记录继续 | 版本提示、可选数据缺失 |
| **E1** Warning | 记录继续 | 记录继续 | 未知属性类型 |
| **E2** Recoverable | 尝试恢复 | **停止** | PropertyTag 偏移异常 |
| **E3** Fatal | 返回部分结果 | 停止 | 文件头损坏、版本不支持 |
| **E4** Panic | 返回空结果 | 停止 | 内存越界、安全网触发 |

### ErrorContext

```python
class ErrorContext(TypedDict):
    file_path: str; offset: int; version: str; asset_type: str
    severity: str; message: str; recovery: Optional[str]
```

### 规则
- CLI 退出码：E0/E1→0，E2(tolerant)→1，E3+→2
- E2 恢复必须有日志去重
- strict 模式 E2+ 不尝试任何恢复

---

## 4. 代码统一性约束

| 原则 | 规则 |
|------|------|
| 单一错误入口 | 统一 `raise_error()`/`log_warn()`，禁止裸 `print()`/`logging.warning()` |
| 常量集中 | E0-E4 定义在 `constants.py`，禁止复制数值 |
| 恢复逻辑抽取 | 相同恢复逻辑抽取为函数，禁止复制粘贴 |
| ErrorContext 工厂化 | 通过 `make_error_context()` 构造 |

### 防重复架构

| 机制 | 状态 | 规则 |
|------|------|------|
| 属性解析器注册表 | 已存在 | 禁止 `if/elif` 链，通过 `CUSTOM_PROPERTY_HANDLERS` 注册 |
| 节点类型读取器 | 已存在 | 禁止 `read_ue_graph_node()` 中硬编码 if |
| 资产类型解析器 | 已存在 | 通过类名自动路由，禁止核心管线硬编码 |
| 版本常量 | 已存在 | 仅在 `constants.py` 定义，其他模块 import |
| 格式化器接口 | 统一 | `def format_xxx(data, options) -> str` |

---

## 5. 未知和自定义类型处理

### 未知资产回退链

```
Step1 类名匹配 → Step2 父类回退(XXXBlueprint→Blueprint) → Step3 通用UObject(L2) → Step4 仅摘要(L1)
```

### 未知属性处理

| 场景 | 行为 |
|------|------|
| 在已知类型表中 | 使用对应解析器 |
| ≤ 阈值(旧版UE4) | 序号映射，E1 Warning |
| > 阈值 | 跳过，E1 Warning |
| 在自定义注册表中 | 使用自定义处理器 |

### 自定义处理器

```python
@register_custom_property("CustomGameplayTag")
def parse_custom_gameplay_tag(ctx: CustomPropertyContext) -> PropertyValue: ...
```

- 异常视为 E2（可恢复），不阻断后续解析
- 不污染核心解析管线

### 约束
1. 未知类型优雅降级（L2→L1），不抛异常
2. 记录必须含：asset_type、class_name、file_path、offset
3. 相同未知类型日志去重
4. 回退链可配置

---

## 6. 诊断输出（未知但结构可识别）

输出位置：`ParseResult.status.diagnostics.unknown_types[]`

```json
{
  "class_name": "CustomFortItemDefinition",
  "object_name": "DA_Sword_Common",
  "outer_path": "/Game/Items/Weapons/Sword",
  "serial_offset": 1024, "serial_size": 2048,
  "properties_sample": [{"name": "DisplayName", "type": "TextProperty"}],
  "properties_truncated": true, "properties_total_count": 35
}
```

### 限制

| 项目 | 上限 |
|------|------|
| 属性样本 | ≤ 20 个 |
| 类型名长度 | ≤ 128 字符 |
| 对象路径 | ≤ 256 字符 |
| 单文件条目 | ≤ 10 个 |
| 总计条目 | ≤ 50 个/次解析 |
| 原始二进制 | 不允许 |

---

## 7. 测试策略

| 测试 | 用例 | 验证 |
|------|------|------|
| 未知资产类型 | 不存在于注册表的 class_name | 降级到 L2 |
| 未知属性类型 | 未知 PropertyTag | 跳过并继续 |
| 自定义处理器 | 注册并调用 | 正确调用 |
| 自定义处理器异常 | 抛出异常 | E2 错误，不阻断 |
| 诊断输出限制 | 大量未知类型 | 不超上限 |

### 现有要求（不变）
≥ 200 单元测试 · ≥ 40 集成测试 · 100% 通过率(xfail 除外) · 12+ 资产类型 · strict/tolerant 双模式

---

**维护者**: uasset_read Contributors
