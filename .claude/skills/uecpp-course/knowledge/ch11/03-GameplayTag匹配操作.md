# GameplayTag 匹配操作

## 核心数据结构

| 类型 | 说明 |
|------|------|
| `FGameplayTag` | 单个标签，底层封装 FName |
| `FGameplayTagContainer` | 标签容器，底层为 TArray<FName> |

## 匹配模式分类

### 概念包含匹配（Conceptual Match）

父级标签包含子级标签。例如注册了 `Family.Space` 的 Actor：

| 查询标签 | 是否匹配 | 说明 |
|----------|---------|------|
| `Family` | 是 | 父级包含子级 |
| `Family.Space` | 是 | 完全匹配 |
| `Family.Space.Kitchen` | 否 | 不存在此子级 |

### 精确匹配（Exact Match）

要求完全一致，不继承父级关系。

## 匹配 API

### MatchTag（单标签匹配）

| API | 模式 | 说明 |
|-----|------|------|
| `HasTag(Tag)` | 概念包含 | 子级标签是否包含查询标签（父级） |
| `HasTagExact(Tag)` | 精确 | 要求完全一致 |

### MatchAny（OR 逻辑）

| API | 说明 |
|-----|------|
| `HasAny(Container)` | 容器中包含任意一个匹配标签即返回 true |
| `HasAnyExact(Container)` | 精确版本的 Any 匹配 |

### MatchAll（AND 逻辑）

| API | 说明 |
|-----|------|
| `HasAll(Container)` | 容器中包含所有查询标签才返回 true |
| `HasAllExact(Container)` | 精确版本的 All 匹配 |

## GameplayTagQuery（复杂表达式查询）

使用类似 Behavior Tree 的 Sequence/Selector 结构构建条件组合：

- **Sequence**：所有子条件都必须满足（AND）
- **Selector**：任一子条件满足即可（OR）
- 支持嵌套组合，表达能力远超简单的 HasTag/HasAll

适用于需要运行时动态构建复杂匹配规则的场景。

## 空标签规则

- 空 `FGameplayTag`（默认构造）和空 `FGameplayTagContainer` 的匹配操作始终返回 `false`
- 不存在"默认匹配"行为
