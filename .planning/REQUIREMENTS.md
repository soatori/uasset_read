# v10.0 Requirements

## 需求类别

### [C++ 类骨架]
- [ ] **CPP-01**: 从蓝图导出父类继承链（如 `BP_FirstPersonCharacter → Character → Pawn → Actor`），输出等价 C++ 类声明
- [ ] **CPP-02**: 从蓝图组件列表生成 UPROPERTY 声明（类别+变量名+标记如 `VisibleAnywhere` / `Instanced`）
- [ ] **CPP-03**: 从蓝图变量生成 UPROPERTY 声明（类型+C++ 类型名+默认值+Blueprint 可见性标记）

### [函数签名映射]
- [ ] **FUNC-01**: 从函数图节点提取完整函数签名（函数名+参数名+参数类型+返回值+方向/const 推断）
- [ ] **FUNC-02**: 从函数调用节点提取目标函数引用（MemberName + MemberParent 类），输出等价 C++ 调用语句
- [ ] **FUNC-03**: 区分 UFUNCTION 类型（BlueprintCallable / BlueprintPure / BlueprintImplementableEvent）并生成对应宏

### [函数体逻辑翻译]
- [ ] **BODY-01**: 从执行流（execution pins + then 链）生成 C++ 语句序列
- [ ] **BODY-02**: 从数据流（pure function 返回值 → 参数输入）生成 C++ 赋值表达式
- [ ] **BODY-03**: 从 Branch/Sequence/ForEach 等控制流节点生成 C++ if/for 语句
- [ ] **BODY-04**: 从 Pure 函数调用生成内联表达式（如 `GetActorRightVector() * Scale`）

### [组件初始化]
- [ ] **COMP-01**: 从组件变换数据生成构造函数中的组件创建代码（`CreateDefaultSubobject` + 位置/旋转/缩放）
- [ ] **COMP-02**: 从组件属性导出默认值初始化（如 `CameraBoom->TargetArmLength = 400.0f`）

### [验证与测试]
- [ ] **TEST-01**: 基于 `reference/蓝图节点文本参考.md` 编写 golden-path 集成测试
- [ ] **TEST-02**: 验证 BP_FirstPersonCharacter 的 Move/Aim 函数 JSON 输出与等价 C++ 实现匹配
- [ ] **TEST-03**: 验证 Jump/StopJumping 事件驱动的函数调用链输出

## 未来需求

- [ ] 自动 C++ 代码生成（非参考手册模式，而是直接 .cpp/.h 文件）
- [ ] 多蓝图包交叉引用解析（ImportMap/ExportMap 跨包链接）
- [ ] 材质/动画蓝图支持

## Out of Scope

- C++ 代码自动编译验证（仅生成源码，不编译）
- Cooked 资产解析
- 蓝图字节码反编译

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CPP-01 | Phase 56 | Pending |
| CPP-02 | Phase 56 | Pending |
| CPP-03 | Phase 56 | Pending |
| FUNC-01 | Phase 57 | Pending |
| FUNC-02 | Phase 57 | Pending |
| FUNC-03 | Phase 57 | Pending |
| BODY-01 | Phase 58 | Pending |
| BODY-02 | Phase 58 | Pending |
| BODY-03 | Phase 58 | Pending |
| BODY-04 | Phase 58 | Pending |
| COMP-01 | Phase 59 | Pending |
| COMP-02 | Phase 59 | Pending |
| TEST-01 | Phase 60 | Pending |
| TEST-02 | Phase 60 | Pending |
| TEST-03 | Phase 60 | Pending |

**Coverage: 15/15 v1 requirements mapped**
