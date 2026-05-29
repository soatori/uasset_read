# uasset_read 解析错误详细报告

**测试目标**: FirstPerson (549 文件) vs FirstPersonC (536 文件)
**UE 版本**: UE5=1017 (两个项目一致)
**解析日期**: 2026-05-29
**测试路径**: `E:\Develop\lib\UnrealEngine\Samples\FirstPerson/` & `FirstPersonC/`

---

## 一、错误分类总览

| 错误类型 | 严重度 | 出现频率 | 影响范围 |
|---------|--------|---------|---------|
| E1. Unknown EExprToken 0xFF | 高 | 极高 | 所有含事件图的蓝图 (FP) |
| E2. StructProperty 回退 (UnknownStruct) | 高 | 极高 | 所有蓝图变量/配置 |
| E3. K2Node Fallback | 高 | 极高 | 复杂蓝图节点 |
| E4. P73-RECOVERY LinkedTo 计数错误 | 中 | 部分 | 引脚连接解析 |
| E5. BPGC 字节码回退 | 中 | 高 | 函数体提取 |
| E6. StructProperty 大小不匹配 | 中 | 部分 | StaticMesh/Niagara |
| E7. 解析完全失败 | 严重 | 个别 | MaterialInstance |

---

## 二、逐类详细报告

### E1. Unknown EExprToken 0xFF

**现象**: Kismet 字节码中出现无法识别的 token `0xFF`，解析器在 tolerant 模式下跳过。

**严重程度**: 高 — 导致字节码解析中断，函数体内细节丢失。

**受影响文件示例**:

| 文件 | 出现次数 | 偏移量范围 |
|------|---------|-----------|
| `BP_ShooterCharacter.uasset` (FP) | 16 次 | 46~1917 |
| `BP_ShooterCharacter.uasset` (FPC) | 0 次 | — |
| `BP_ShooterGameMode.uasset` (FP) | 5 次 | 77~183 |
| `BP_ShooterGameMode.uasset` (FPC) | 0 次 | — |
| `BP_HorrorCharacter.uasset` (FP) | 6 次 | 132~1124 |
| `BP_HorrorCharacter.uasset` (FPC) | 0 次 | — |
| `BP_ShooterProjectile_Bullet.uasset` (FP) | 5 次 | 187~1204 |
| `ABP_TP_Rifle.uasset` (FP) | 10 次 | 13~1173 |
| `UI_Horror.uasset` (FP) | 8 次 | 77~181 |
| `StateTreeTask_FaceActor.uasset` (FP) | 0 次 | — |

**关键发现**:

- **FirstPerson 的蓝图普遍出现**，FirstPersonC 的蓝图**完全不出现**
- 原因：FP 蓝图继承自蓝图基类（如 `BP_ShooterCharacter` → `BP_FirstPersonCharacter_C`），字节码中包含蓝图虚拟函数调用；FPC 蓝图继承自 C++ 基类（→ `ShooterCharacter`），字节码更简洁
- 解析器跳过这些 token 后，**函数名可以提取，但函数体内细节丢失**

**根因推测**: `0xFF` 是 UE5.5 新增的 EExprToken（可能是委托相关操作符，如 `EX_BindDelegate`、`EX_RemoveMulticastDelegate` 等），解析器的 `EExprToken` 枚举未覆盖 5.5 版本的全部 token。

---

### E2. StructProperty 回退为 UnknownStruct

**现象**: `StructProperty` 标签大小与预期不匹配，回退为不透明的 `UnknownStruct`。

**严重程度**: 高 — 蓝图变量、配置数据完全不可读。

**受影响范围**: **所有蓝图文件**（FirstPerson 和 FirstPersonC 均受影响）

**示例**:

```
BP_ShooterGameMode (FP):
  NewVariables → [UnknownStruct, raw_size=570] ×2
  ImplementedInterfaces → [UnknownStruct, raw_size=82]
  LastEditedDocuments → [UnknownStruct, raw_size=147] ×3

BP_ShooterGameMode (FPC):
  LastEditedDocuments → [UnknownStruct, raw_size=147] ×3
```

**缺失解析的常见结构体**:

| 结构体类型 | 用途 | 回退数据量 |
|-----------|------|-----------|
| `UnknownStruct` (NewVariables) | 蓝图变量定义 | 557~570 bytes |
| `UnknownStruct` (ImplementedInterfaces) | 实现的接口 | 78~82 bytes |
| `UnknownStruct` (LastEditedDocuments) | 最近编辑的文档 | 147 bytes |
| `UnknownStruct` (CategorySorting) | 分类排序 | 变化 |
| `TopLevelAssetPath` | 资产路径引用 | 74 bytes |
| `PointerToUberGraphFrame` | UberGraph 帧指针 | 8 bytes |
| `Guid` | GUID/UUID | **可以解析** |

**根因**: 解析器缺少这些 UE 结构体的序列化定义，或者结构体版本（UE5=1017）的序列化格式与解析器已知版本不匹配。

---

### E3. K2Node Fallback（蓝图节点回退）

**现象**: 遇到无法识别的 K2Node 类型，回退到基本处理。

**严重程度**: 高 — 蓝图节点的具体参数和执行逻辑丢失。

**回退节点类型汇总**:

| K2Node 类型 | 出现次数 | 语义 |
|------------|---------|------|
| `K2Node_Message` | 极高频 (20+) | 跨模块消息通信 |
| `K2Node_CallDelegate` | 高频 (10+) | 委托调用 |
| `K2Node_CallArrayFunction` | 中频 (5+) | 数组操作函数 |
| `K2Node_CallParentFunction` | 中频 (5+) | 调用父类函数 |
| `K2Node_Knot` | 中频 (5+) | 引脚连线跳转 |
| `K2Node_FunctionResult` | 中频 (5+) | 函数返回值 |
| `K2Node_CreateWidget` | 低频 (2) | 创建 UI 控件 |
| `K2Node_AddDelegate` | 低频 (4) | 添加委托绑定 |
| `K2Node_MacroInstance` | 低频 (1) | 宏实例（如 Branch/For） |

**文件示例**:

| 文件 | Fallback 节点数 |
|------|----------------|
| `BP_ShooterCharacter.uasset` (FP) | 25 |
| `BP_HorrorCharacter.uasset` (FP) | 15 |
| `BP_ShooterGameMode.uasset` (FP) | 5 |
| `UI_Horror.uasset` (FP) | 4 |
| `BP_ShooterProjectile_Bullet.uasset` (FP) | 1 |
| FPC 所有文件 | **0** |

**根因**: 解析器的 K2Node 类型注册表不完整。K2Node 是 UE 蓝图序列化中的节点类型标识，每种节点类型需要单独的序列化逻辑。

---

### E4. P73-RECOVERY LinkedTo 计数错误

**现象**: Pin 连接的计数值异常，解析器尝试恢复。

**严重程度**: 中 — 引脚连接关系部分丢失。

**受影响文件**:

| 文件 | 错误数 | 异常计数值 |
|------|--------|-----------|
| `BP_ShooterGameMode.uasset` (FP) | 4 次 | 16711680, -49840721 |

**详情**:

```
[P73-RECOVERY] LinkedTo: bad count 16711680 at pos 47967, found count 0 at pos 47970
[P73-RECOVERY] LinkedTo: bad count 16711680 at pos 49139, found count 0 at pos 49142
[P73-RECOVERY] LinkedTo: bad count 16711680 at pos 50548, found count 0 at pos 50551
[P73-RECOVERY] LinkedTo: bad count -49840721 at pos 51159, found count 0 at pos 51171
```

**特征**:

- 异常计数值 `16711680` = `0xFF0000`（可能是字节序问题或填充字节）
- `-49840721` 为负数（正常计数应为非负）
- 解析器在 offset 后发现 count=0，判断为有效恢复点（confidence=medium），继续解析 SubPins

---

### E5. BPGC 字节码回退

**现象**: 无法正常提取函数字节码，回退到 BPGC（Blueprint Generated Class）扫描模式。

**严重程度**: 中 — 函数名和大致结构可提取，但精确字节码丢失。

**示例**:

```
Falling back to BPGC bytecode extraction for 'ExecuteUbergraph_BP_ShooterGameMode'
Recovered bytecode for 'ExecuteUbergraph_BP_ShooterGameMode' by scanning Function serial (3 expressions)
```

**受影响文件统计**:

| 文件 | 回退函数数 |
|------|-----------|
| `BP_ShooterCharacter.uasset` (FP) | 29 个函数 |
| `BP_ShooterGameMode.uasset` (FP) | 6 个函数 |
| `BP_HorrorCharacter.uasset` (FP) | 10 个函数 |
| `ABP_TP_Rifle.uasset` (FP) | 7 个函数 |
| `StateTreeTask_FaceActor.uasset` (FP) | 3 个函数 |
| `BPI_Shooter.uasset` (FP) | 5 个函数 |
| FPC `BP_ShooterGameMode.uasset` | 0 个回退 |

**解析器表现**: 回退后仍能通过扫描 Function serial 恢复部分表达式（3~8 个），但远少于实际数量。

---

### E6. StructProperty 大小不匹配

**现象**: StructProperty 标签声明的大小与解析器预期不符，使用回退解析。

**严重程度**: 中 — 部分数据可读，但结构体内部字段无法解析。

| 结构体 | 声明大小 | 预期大小 | 比值 | 影响文件 |
|--------|---------|---------|------|---------|
| `BoxSphereBounds` | 114 | 40 | 2.85x | `SM_ChamferCube.uasset` (FP+FPC) |
| `Vector4` | 32 | 16 | 2x | `NS_JumpPad.uasset` (FP+FPC) |
| `KAggregateGeom` | 483 | — | — | `SM_ChamferCube.uasset` |
| `BodyInstance` | 98 | — | — | `SM_ChamferCube.uasset` |

**特征**:

- `Vector4` 的 32 bytes 是预期 16 bytes 的 2 倍，可能是 UE5.5 的 Vector4 从 4 个 float 扩展为 double 精度或增加了其他字段
- `BoxSphereBounds` 的 114 bytes 也明显大于预期的 40 bytes（4×3 floats + padding）

---

### E7. 解析完全失败

**现象**: 解析器直接抛出错误，无法输出任何有效内容。

| 文件 | 错误信息 | 文件类型 |
|------|---------|---------|
| `MI_Manny_01_New.uasset` | Cannot read 4 bytes at position 17961, only 2 bytes remaining | MaterialInstance |
| `MI_Manny_02_New.uasset` | Negative generations count: -1240814712 | MaterialInstance |

**严重程度**: 严重 — 完全不可解析。

**根因推测**: MaterialInstance 的序列化格式与解析器预期完全不同，可能是 UE5.5 改变了 MI 的存储结构（Parent 引用的偏移计算错误）。

---

## 三、FirstPerson vs FirstPersonC 错误对比

| 维度 | FirstPerson | FirstPersonC |
|------|-------------|--------------|
| **EExprToken 0xFF** | 大量（几乎所有蓝图） | 无 |
| **K2Node Fallback** | 大量（20+ 类型） | 极少 |
| **BPGC 回退** | 大量函数 | 少量函数 |
| **P73-RECOVERY** | 有 | 无 |
| **StructProperty 回退** | 所有蓝图 | 所有蓝图（同左） |
| **Struct 大小不匹配** | 有（StaticMesh/Niagara） | 有（StaticMesh/Niagara，同左） |
| **完全失败** | MaterialInstance | MaterialInstance（同左） |
| **总体复杂度** | 高（271 exports 的蓝图） | 低（56 exports 的蓝图） |
| **纯解析错误** | 少 | 少 |

**结论**: FirstPersonC 因为继承链更短、逻辑下沉到 C++，解析错误显著少于 FirstPerson。但**结构性问题**（E2/E6/E7）在两个项目中完全一致，说明是解析器核心能力缺失，而非文件差异导致。

---

## 四、优先级修复建议

| 优先级 | 错误类型 | 预估工作量 | 收益 |
|--------|---------|-----------|------|
| P0 | E2. StructProperty UnknownStruct 回退 | 大 | 最高 — 解锁蓝图变量/配置数据 |
| P1 | E1. EExprToken 0xFF 补充 | 中 | 高 — 修复 FirstPerson 蓝图字节码 |
| P1 | E3. K2Node 类型注册 | 大 | 高 — 解锁蓝图节点细节 |
| P2 | E6. StructProperty 大小不匹配 | 中 | 中 — 改善 StaticMesh/Niagara |
| P2 | E4. P73-RECOVERY 优化 | 小 | 中 — 提升引脚连接可靠性 |
| P3 | E7. MaterialInstance 完全失败 | 大 | 低 — 仅影响 MI 类型 |
