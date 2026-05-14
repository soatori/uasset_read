# Phase 26: 蓝图元数据增强

**阶段编号**: 26
**所属里程碑**: v5.0 架构重构与蓝图编译研究
**状态**: 📅 Planned
**预计完成**: 2026-05-10

## 上下文

### 问题陈述

当前 uasset_read 项目已能够解析蓝图的基本结构，包括变量、函数、事件等。但对于元数据的解析还不够完整：

1. **变量元数据**：缺少默认值、属性修饰符（EditAnywhere、BlueprintReadWrite 等）的完整解析
2. **函数元数据**：缺少参数详细描述、返回值信息、函数属性（BlueprintCallable、BlueprintPure 等）
3. **事件元数据**：缺少自定义事件、多播事件、接口事件的支持

### 目标

增强蓝图变量、函数、事件的解析能力，为 C++ 代码生成提供完整的元数据支持。

### 依赖

- Phase 25: 蓝图编译流程研究 ✓ COMPLETE

---

## 需求

### META-01: 增强变量解析（默认值、属性）

**描述**：增强变量元数据解析，提取默认值和属性修饰符

**接受标准**:
- [ ] 解析变量默认值
- [ ] 解析属性修饰符（EditAnywhere、BlueprintReadWrite、Category、VisibleAnywhere 等）
- [ ] 解析变量类型详细信息（基础类型、结构体、枚举等）
- [ ] 解析变量可见性（Public、Private、Protected）

### META-02: 增强函数解析（参数、返回值、属性）

**描述**：增强函数元数据解析，提取参数详细信息和函数属性

**接受标准**:
- [ ] 解析函数参数（名称、类型、默认值、输入/输出）
- [ ] 解析函数返回值（类型、是否为 void）
- [ ] 解析函数属性（BlueprintCallable、BlueprintPure、BlueprintEvent 等）
- [ ] 解析函数访问修饰符（Public、Private、Protected）

### META-03: 增强事件解析（自定义、多播、接口）

**描述**：增强事件元数据解析，支持自定义事件、多播事件、接口事件

**接受标准**:
- [ ] 解析自定义事件（事件名称、参数）
- [ ] 解析多播事件（委托类型、绑定信息）
- [ ] 解析接口事件（接口定义、实现）
- [ ] 解析重写事件（父类事件、重写标志）

### META-04: 添加到 JSON 输出

**描述**：将增强的元数据添加到 JSON 输出

**接受标准**:
- [ ] JSON 输出包含增强变量元数据
- [ ] JSON 输出包含增强函数元数据
- [ ] JSON 输出包含增强事件元数据
- [ ] 更新 JSON Schema

---

## 成功标准

### Phase 26 完成时必须为真的条件

1. **META-01**: 变量元数据完整（默认值、属性、可见性）
2. **META-02**: 函数元数据完整（参数、返回值、属性）
3. **META-03**: 事件元数据完整（自定义、多播、接口）
4. **META-04**: JSON 输出包含增强元数据

---

## 计划

### 26-01: META-01 增强变量解析（默认值、属性）

**状态**: 📅 Planned

**输出**:
- 更新 `src/core/models.py` - BlueprintVariable 扩展
- 更新 `src/core/archive.py` - 变量属性解析

**关键文件**:
- `src/core/models.py` - BlueprintVariable、BlueprintMetadata 类
- `src/core/archive.py` - 属性读取函数

---

### 26-02: META-02 增强函数解析（参数、返回值、属性）

**状态**: 📅 Planned

**输出**:
- 更新 `src/core/models.py` - BlueprintFunction 扩展
- 更新 `src/core/archive.py` - 函数参数解析

**关键文件**:
- `src/core/models.py` - BlueprintFunction、FunctionParameter 类
- `src/core/archive.py` - UFunction 解析

---

### 26-03: META-03 增强事件解析（自定义、多播、接口）

**状态**: 📅 Planned

**输出**:
- 更新 `src/core/models.py` - BlueprintEvent 扩展
- 更新 `src/core/archive.py` - 事件解析

**关键文件**:
- `src/core/models.py` - BlueprintEvent、MulticastDelegate 类
- `src/core/archive.py` - 事件解析逻辑

---

### 26-04: META-04 添加到 JSON 输出

**状态**: 📅 Planned

**输出**:
- 更新 `src/output/json.py` - 元数据输出格式
- 更新 `.planning/schemas/BLUEPRINT_JSON_SCHEMA.md` - Schema 扩展

**关键文件**:
- `src/output/json.py` - JSON 格式化
- `.planning/schemas/BLUEPRINT_JSON_SCHEMA.md` - Schema 定义

---

## 输出文件

| 文件 | 描述 | 位置 |
|------|------|------|
| BlueprintVariable (扩展) | 变量元数据增强 | `src/core/models.py` |
| BlueprintFunction (新增) | 函数元数据定义 | `src/core/models.py` |
| BlueprintEvent (新增) | 事件元数据定义 | `src/core/models.py` |
| JSON 格式化 (更新) | 元数据输出 | `src/output/json.py` |
| JSON Schema (更新) | Schema 扩展 | `.planning/schemas/BLUEPRINT_JSON_SCHEMA.md` |

---

## 参考资料

### UE 源码
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\UnrealType.h` - FProperty、UFunction 定义
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\ObjectMacros.h` - 宏定义（UPROPERTY、UFUNCTION）

### 项目文件
- `E:\Develop\uasset_read\.planning\research\NODE_TO_CPP_MAPPING.md` - 节点到 C++ 映射
- `E:\Develop\uasset_read\src\core\models.py` - 当前数据模型

---

## 验证计划

### META-01 验证
- [ ] 变量默认值正确解析
- [ ] 变量属性正确解析
- [ ] 变量可见性正确解析

### META-02 验证
- [ ] 函数参数正确解析
- [ ] 函数返回值正确解析
- [ ] 函数属性正确解析

### META-03 验证
- [ ] 自定义事件正确解析
- [ ] 多播事件正确解析
- [ ] 接口事件正确解析

### META-04 验证
- [ ] JSON 输出包含变量元数据
- [ ] JSON 输出包含函数元数据
- [ ] JSON 输出包含事件元数据
- [ ] JSON Schema 验证通过

---

## 时间估算

| 活动 | 估算时间 |
|------|----------|
| META-01: 增强变量解析 | 1 天 |
| META-02: 增强函数解析 | 1 天 |
| META-03: 增强事件解析 | 1 天 |
| META-04: 添加到 JSON 输出 | 0.5 天 |

**Phase 26 总计**：约 3.5 天

---

*创建日期：2026-05-06*