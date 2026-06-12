# 本地 Issue 跟踪

> 来源：真实资产随机测试（5 批次 × 100 样本，2026-06-11）
> 样本库：`E:\Develop\lib\UnrealEngine\Samples`（19133 个 .uasset）
> **修复前累计结果**：338 success / 161 partial / 1 failed（**崩溃率 0%**）

---

## 待修复

### LOCAL-001: MapProperty StructProperty key 不支持
- **优先级**：P2
- **影响资产**：动画资产（M_Neutral_*, M_Relaxed_Run_* 等，**约 45 个 / 500 样本**）
- **现象**：`MapProperty 'CurveIdentifierToMetaData': unsupported key type 'StructProperty', returning fallback`
- **原因**：动画曲线元数据 Map 使用 StructProperty 作为 key，当前仅支持简单类型 key
- **UE 参考**：`UCurveFloat::CurveIdentifierToMetaData` — `TMap<FAnimCurveIdentifier, FAnimCurveMetaData>`

### LOCAL-002: SerializationControlExtensions 未知位
- **优先级**：P3
- **影响资产**：Interchange 相关（T_Rifle_BC, mx_System, T_MoneyBag_N, sfx_Character_*, SKM_Quinn_Simple 等，**约 11 个 / 500 样本**）
- **现象**：`SerializationControlExtensions 未知位: 0xC1 / 0x01 / 0xCD / 0xF9`
- **原因**：UE5 Interchange 框架的序列化控制扩展，位标记含义未完全实现
- **UE 参考**：`FObjectResource::SerializationControl`

### LOCAL-003: StructProperty Transform tag.size=0
- **优先级**：P2
- **影响资产**：动画 morph target（MF_Pistol_Jog_Fwd, MF_Unarmed_Walk_Right, MF_Rifle_Walk_Fwd, MF_Rifle_Jog_Right, MF_Rifle_Walk_Bwd）
- **现象**：`StructProperty 'Transform': tag.size=0 不匹配 float(48) 或 double(96), using fallback`
- **原因**：Morph target 动画中的 Transform 结构体 size 标记为 0，可能是 UE5 新增的省略编码
- **UE 参考**：`FTransform` 序列化

### LOCAL-004: StructProperty AnimNotifyTrack tag.size=0
- **优先级**：P3
- **影响资产**：动画通知（M_Neutral_AO_Crouch_X-135_Y+90, M_Relaxed_Jump_F_Land_Stand_Heavy_Lfoot）
- **现象**：`StructProperty 'AnimNotifyTrack': tag.size=0 != expected=8, using fallback`
- **原因**：AnimNotifyTrack 结构体 size 标记为 0，与 LOCAL-003 同类问题
- **UE 参考**：`FAnimNotifyTrack`

### LOCAL-004b: StructProperty FrameRate tag.size=37
- **优先级**：P3
- **影响资产**：动画元数据（MM_Pistol_Fire, Manny_clavicle_l_anim, m_med_nrw_ring_02_r_anim, Manny_lowerarm_l_anim, MF_Pistol_Idle_ADS_AO_CU）
- **现象**：`StructProperty 'FrameRate': tag.size=37 != expected=8, using fallback`
- **原因**：FrameRate 结构体 size 标记异常（37 字节而非 8），可能是嵌套结构体或序列化异常
- **UE 参考**：`FFrameRate`

### LOCAL-005: 无 stderr 输出的 partial 状态
- **优先级**：P3
- **影响资产**：BP_SideScrollingGameMode, W_ItemAcquiredList, MI_Safe, MF_ExposureCompensation 等（**约 80 个 / 500 样本**）
- **现象**：status 为 partial 但 stderr 无任何警告信息
- **原因**：可能是解析过程中某处设置了 partial 状态但未输出日志，需要排查状态设置点
- **排查方向**：grep `parse_status.*partial` 找到所有设置点，补充日志

### LOCAL-006: ArrayProperty tag.size=0
- **优先级**：P3
- **影响资产**：UI 蓝图（W_DashCooldown）
- **现象**：`ArrayProperty 'Animations': tag.size=0 < 4, 无法计算剩余数据大小`
- **原因**：ArrayProperty 的 size 标记为 0，导致无法计算元素数量，可能是空数组或序列化异常
- **UE 参考**：`TArray` 序列化

### LOCAL-008: FString 全空字节（数据损坏）
- **优先级**：P3
- **影响资产**：NS_Trangle.uasset
- **现象**：`FString at pos 251776: length=9473, encoding=UTF-8, all nulls (completely corrupted)`
- **原因**：资产内部字符串数据区域全为零字节，可能是资产本身损坏或序列化偏移错位
- **备注**：解析器正确检测并报告了损坏，未崩溃

---

## 测试统计

| 批次 | 种子 | Success | Partial | Failed | 耗时 |
|------|------|---------|---------|--------|------|
| 1 | 42 | 73 (73%) | 27 (27%) | 0 | 35.3s |
| 2 | 114 | 63 (63%) | 37 (37%) | 0 | 35.2s |
| 3 | 514 | 58 (58%) | 42 (42%) | 0 | 36.7s |
| 4 | 8192 | 72 (72%) | 27 (27%) | 1 | 37.1s |
| 5 | 2077 | 72 (72%) | 28 (28%) | 0 | 37.7s |
| **合计** | — | **338 (68%)** | **161 (32%)** | **1** | **182.0s** |

---

## 已完成/无需修复

### LOCAL-OK: 大资产解析
- 47.56MB L_Expanse_Blockout_BuiltData（第一批）
- 37.53MB T_Tiling_RockA_M（第二批）
- 15.80MB SKM_Hayakawa_Outline1（第三批）
- 15.50MB SKM_Quinn_Simple（第四批，partial 但无崩溃）
- 13.06MB T_Int_Wall1_BC（第二批）
- 12.81MB T_Quinn_02_CCRCCPlastic_MSK（第二批）

### LOCAL-OK: ExternalActors 资产
- `__ExternalActors__` 目录下的 .uasset 全部正常解析（五批均出现）

### LOCAL-OK: 零崩溃
- 原 500 个随机样本中 499 个正常完成解析流程，1 个返回 failed（LOCAL-007）；LOCAL-007 已专项修复并验证不再 failed。

### LOCAL-007: Negative generations count（已修复）
- **优先级**：P1
- **影响资产**：Blueprint_CeilingLight.uasset（StarterContent）
- **修复**：legacy=-6 资产通过 FileVersionUE4 区分 UE4/UE5，并按 UE4 PackageFileSummary 字段顺序和版本门控读取 Generations / EngineVersion。
- **验证**：`tests/test_issue_123_ue4_legacy_summary.py` 覆盖真实样本；strict/tolerant 解析不再返回 failed。
