# Phase 66 — Agent 翻译管线

## 来源
利用 Phase 65 修复后的图解析输出，构建 BP 节点 JSON → C++ 代码生成的翻译管线。

## 目标
Agent 输入：BP_FirstPersonCharacter.uasset 解析结果（正确的函数引用 + Pin 连接）
Agent 输出：等效 C++ 代码（.h / .cpp）

## 翻译规则参考
- v10.0 Phase 56-60: cpp_gen 模块骨架、类型映射、函数签名/体翻译
- UE C++ 编码规范：UCLASS/UFUNCTION/UPROPERTY 宏、A/U/I 前缀
- Blueprint 节点 → C++ 映射表（Phase 58 已有基础）

## 验证目标
对 BP_FirstPersonCharacter 的 Aim/Move/EventGraph 生成可读的 C++ 代码，包含：
1. 正确的类声明（继承自 ACharacter）
2. 函数签名（参数类型、返回值）
3. 函数体（函数调用、参数传递）
4. 组件初始化（构造函数中的 CreateDefaultSubobject）
