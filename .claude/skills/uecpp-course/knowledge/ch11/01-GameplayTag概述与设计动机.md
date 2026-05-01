# GameplayTag 概述与设计动机

## 本质定义

GameplayTag 是 Unreal Engine 中的**层级化概念标签系统**，以点号（`.`）分隔的字符串表达层次关系。

```
XG.Mode.Coding     ← 三级标签
XG.Mode.Working    ← 同级标签
Family.Space       ← 二级标签
```

## 设计动机：从 bool 到 GameplayTag 的演进

### 第一阶段：bool 标志

```cpp
bool bIsAlive;
```

- 只能表达二元状态
- 无法区分死亡原因（掉落、枪击、刀砍、侧击）

### 第二阶段：枚举（enum）

```cpp
enum EDeathType { Falling, Gunshot, Blade, SideAttack };
```

- 解决了"类型区分"问题
- 无法表达层级关系（如"技能A"和"舞蹈A"互斥，但"技能B"和"舞蹈B"也互斥）
- 无法表达父级/子级关系（如"所有技能"这个集合）

### 第三阶段：GameplayTag

```
Skill.A            ← 技能A
Skill.B            ← 技能B
Dance.A            ← 舞蹈A
Dance.B            ← 舞蹈B
```

- **层级继承**：`Skill` 匹配 `Skill.A` 和 `Skill.B`
- **互斥抽象化**：`Skill` 级标签与 `Dance` 级标签互斥 → 子级标签自动继承该约束

## 核心特性

| 特性 | 说明 |
|------|------|
| 层级结构 | 点号分隔层次，父级包含子级 |
| 预定义约束 | 不可在运行时动态创建，须在打包前注册 |
| 轻量比较 | 底层基于 FName，比较效率高 |
| 组合查询 | 支持单个标签精确匹配、容器包含匹配、复杂表达式查询 |

## 与 FName 标签的区别

Unreal Engine 中 Actor 的 Base 属性也有"标签"（通过 `Actor Has Tag` 节点访问），底层基于 FName。GameplayTag 在此基础上增加了**层次结构**、**父级匹配**和**查询表达式**能力。
