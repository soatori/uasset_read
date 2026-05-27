# UObject 继承 + Linker 重构 — CUE4Parse 架构收敛

## 背景

当前 linker 体系是"本包对象壳 + 局部 preload"，需要推进到更接近 CUE4Parse 的 Package-centered + lazy + provider-aware 架构。

## 架构

分 3 个 wave 执行，顺序不可颠倒：

### Wave 1: 反射层次 + SuperField 链

**新建 `src/uasset_read/models/uobject.py`：**

UObject → UField → UEnum/UStruct/UClass/UFunction 反射层次模型。

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

class UObjectCategory(Enum):
    UObject = "UObject"
    UField = "UField"
    UEnum = "UEnum"
    UStruct = "UStruct"
    UClass = "UClass"
    UFunction = "UFunction"
    Unknown = "Unknown"

@dataclass
class UObjectBase:
    name: str
    category: UObjectCategory = UObjectCategory.Unknown
    super_field_name: Optional[str] = None
    class_package: Optional[str] = None

    def is_field(self) -> bool:
        return self.category in (
            UObjectCategory.UField, UObjectCategory.UEnum,
            UObjectCategory.UStruct, UObjectCategory.UClass,
            UObjectCategory.UFunction,
        )

@dataclass
class UField(UObjectBase):
    category: UObjectCategory = UObjectCategory.UField

@dataclass
class UEnum(UField):
    category: UObjectCategory = UObjectCategory.UEnum
    enum_values: List[str] = None

@dataclass
class UStruct(UField):
    category: UObjectCategory = UObjectCategory.UStruct
    children: List[str] = None

@dataclass
class UClass(UStruct):
    category: UObjectCategory = UObjectCategory.UClass

@dataclass
class UFunction(UStruct):
    category: UObjectCategory = UObjectCategory.UFunction
```

导出类标签分类：

```python
class ExportClassTag(Enum):
    Unknown = "Unknown"
    Graph = "Graph"
    GraphNode = "GraphNode"
    GraphPin = "GraphPin"
    BlueprintClass = "BlueprintClass"
    Component = "Component"
    Actor = "Actor"

def get_reflection_category(class_name: str) -> UObjectCategory: ...
def get_export_class_tag(class_name: str) -> ExportClassTag: ...
```

**修改 `src/uasset_read/link/linker.py`：**

- `build_super_tree()` — 在 `link()` 中解析 SuperIndex → UObjectInstance
- `resolve_class_ref(export_index)` — 返回 class UObjectInstance
- `resolve_template_ref(export_index)` — 返回 template UObjectInstance
- `link()` 增加 `build_super_tree()` 调用

**修改 `src/uasset_read/link/object_instance.py`：**

- 新增 `super: Optional["UObjectInstance"] = None` 字段
- 新增 `get_super_field_chain()` 方法（20 层深度限制）
- 新增 `reflection_category` 和 `export_class_tag` 属性

### Wave 2: 独立 Archive + 生命周期 + 位置安全 preload

- 每个 `PackageLinker` 拥有独立的 `_archive` 引用
- `LinkerParseResult` 管理 archive 生命周期（不在函数返回前关闭）
- `preload()` 使用 save/restore 模式，不污染 archive 位置
- 连续 `parse_uasset(file_A)` + `parse_uasset(file_B)` 无缓存串扰

### Wave 3: Provider 接口 + Graph 单一路径

- `PackageLinker` 增加 provider/resolver 边界
- graph/blueprint/pin 解析统一走 linker-aware 主路径
- `/Script/` import 明确采用占位符策略
- 为 Phase 79 IoStore 建立不返工的接口面

## 关键文件

- `src/uasset_read/models/uobject.py` — 新建，反射层次模型
- `src/uasset_read/link/linker.py` — SuperField 链 + class/template 引用
- `src/uasset_read/link/object_instance.py` — super 字段 + 分类属性
- `src/uasset_read/link/result.py` — LinkerParseResult 生命周期
- `src/uasset_read/parse_uasset.py` — 独立 archive 创建

## 测试

- `tests/test_uobject_hierarchy.py` — 反射层次分类测试
- `tests/test_superfield_chain.py` — SuperField chain 解析测试
- `tests/test_linker_class_template.py` — class_ref / template_ref 测试
- `tests/test_linker_isolation.py` — 缓存串扰隔离测试
- `tests/test_linker_lazy_preload.py` — lazy preload 测试

## 验收标准

- BPGC SuperField chain 返回 3+ 层深度
- 连续 parse_uasset 无缓存串扰
- `/Script/` import 保持占位符，不引入真实脚本包加载
- link() 包含 build_super_tree() 调用
