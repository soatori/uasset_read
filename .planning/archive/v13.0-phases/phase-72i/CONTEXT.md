# Phase 72-I: BP_FirstPersonCharacter 全量对比修复

**插入日期:** 2026-05-24
**来源:** `BP_FirstPersonCharacter.uasset` 解析输出 vs `蓝图节点文本参考.md` + `FirstPersonCCharacter.h/cpp` 三方系统化对比
**状态:** 🔴 待执行

## 对比基线

- **蓝图节点文本参考.md** — UE 编辑器导出的 EventGraph 全部 17 个节点的完整序列化文本
- **FirstPersonCCharacter.h** — C++ 类声明（组件属性、函数签名）
- **FirstPersonCCharacter.cpp** — C++ 实现（构造函数组件配置、输入绑定、DoMove/DoAim/DoJumpStart/DoJumpEnd）

## 问题清单（12 项）

| ID | 问题 | 严重度 | 参考值 | 当前解析输出 |
|----|------|--------|--------|-------------|
| I-01 | Pin 连接完全丢失 | 🔴 P0 | 9 条 exec 连接 | 0 connections |
| I-02 | K2Node_EnhancedInputAction 缺失 | 🔴 P0 | 4 个 | 0 个 |
| I-03 | K2Node_Knot 缺失 | 🔴 P1 | 4 个 | 0 个 |
| I-04 | EventGraph 节点总数不足 | 🔴 P1 | 17 个 | 9 个 |
| I-05 | Camera RelativeRotation 全零 | 🔴 P1 | (0, 90, -90) | (0, 0, 0) |
| I-06 | 3 个属性 Size 越界 | 🔴 P1 | 正常解析 | ParseError |
| I-07 | CharacterMovement 属性缺失 | ⚠️ P2 | 2 个属性 | 未提取 |
| I-08 | Camera RelativeLocation 不完整 | ⚠️ P2 | (-2.8, 5.89, 0) | (0, -2.8125, 0) |
| I-09 | Comment 字段缺失 | ⚠️ P2 | 含 NodeComment 等 | 仅部分字段 |
| I-10 | Blueprint.functions 为空 | ⚠️ P2 | 4 个函数 | 空 |
| I-11 | 函数参数信息缺失 | ⚠️ P3 | 含参数类型 | 仅 MemberName |
| I-12 | FString 偏移错误连锁 | ⚠️ P3 | 无警告 | 15+ 处 |

## 验收标准

- [ ] EventGraph `connections` ≥ 9
- [ ] EventGraph 节点 ≥ 13
- [ ] K2Node_EnhancedInputAction ≥ 4
- [ ] Camera RelativeRotation = (0, 90, -90)
- [ ] Camera RelativeLocation ≈ (-2.8, 5.89, 0)
- [ ] LastEditedDocuments/CategoryName/BodyInstance 无 ParseError
- [ ] CharacterMovement 含 BrakingDecelerationFalling + AirControl
- [ ] Comment 含 NodeComment
- [ ] Blueprint.functions 含 DoMove/DoAim/DoJumpStart/DoJumpEnd
- [ ] FString suspicious length < 3

## 参考文件

- `references/蓝图节点文本参考.md`
- `references/测试对照C++类/FirstPersonCCharacter.h`
- `references/测试对照C++类/FirstPersonCCharacter.cpp`
- `references/BP_FirstPersonCharacter.uasset`
