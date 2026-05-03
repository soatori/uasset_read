# v4.0 Requirements — 节点属性深度解析（最终版）

**Milestone:** v4.0
**Created:** 2026-05-04
**Status:** Active
**依据:** UE源码研究（`.planning/research/UE_TEXT_FORMAT_SOURCE.md`）

---

## 设计原则

1. **镜像UE序列化结构** — 按`UEdGraphPin::Serialize`顺序解析二进制
2. **输出整理后的JSON** — 高层抽象结构，隐藏底层字节细节
3. **连接关系构建** — 构建清晰的执行流图和数据流图

---

## Requirements

### PHASE-18: Pin序列化解析

**目标**: 解析Pin二进制数据，构建高层JSON结构

- [ ] **PIN-01**: 解析Pin基础信息
  ```json
  {
    "pin_id": "13FD260E4EE18FD0AA5F7085F9B509D6",
    "pin_name": "execute",
    "direction": "input",
    "tooltip": ""
  }
  ```

- [ ] **PIN-02**: 解析PinType结构
  ```json
  {
    "pin_type": {
      "category": "exec",
      "sub_category": "",
      "sub_category_object": null,
      "container_type": "none",
      "is_reference": false,
      "is_const": false
    }
  }
  ```

- [ ] **PIN-03**: 解析默认值
  ```json
  {
    "default_value": "",
    "default_object": null,
    "default_text": null
  }
  ```

- [ ] **PIN-04**: 解析连接引用
  ```json
  {
    "linked_to": [
      {"node": "K2Node_EnhancedInputAction_5", "pin_id": "6412140B4E7EF6147A86BA8D2AFE9BA4"}
    ],
    "sub_pins": [],
    "parent_pin": null
  }
  ```

- [ ] **PIN-05**: 解析显示属性
  ```json
  {
    "hidden": false,
    "not_connectable": false,
    "advanced_view": false,
    "orphaned": false
  }
  ```

### PHASE-19: 连接关系重建

**目标**: 构建节点间连接图，输出清晰的流程结构

- [ ] **LINK-01**: 构建节点连接映射
  ```json
  {
    "connections": [
      {
        "from": {"node": "K2Node_EnhancedInputAction_5", "pin": "Started"},
        "to": {"node": "K2Node_CallFunction_1193", "pin": "execute"}
      }
    ]
  }
  ```

- [ ] **LINK-02**: 构建执行流图
  ```json
  {
    "execution_flows": [
      {
        "entry": "K2Node_EnhancedInputAction_5",
        "chain": ["K2Node_CallFunction_1193", "K2Node_CallFunction_9386"]
      }
    ]
  }
  ```

- [ ] **LINK-03**: 构建数据流图
  ```json
  {
    "data_flows": [
      {
        "source": {"node": "K2Node_EnhancedInputAction_3", "pin": "ActionValue_X"},
        "target": {"node": "K2Node_CallFunction_5", "pin": "Left / Right"}
      }
    ]
  }
  ```

### PHASE-20: 整合输出

**目标**: 输出完整的节点JSON结构，包含所有解析信息

- [ ] **OUT-01**: 节点完整JSON结构
  ```json
  {
    "node_name": "K2Node_CallFunction_1193",
    "node_type": "CallFunction",
    "node_guid": "F923268743B7B52D669FFB960CA79833",
    "position": {"x": 3136, "y": -1040},
    "function_reference": {
      "member_name": "Jump",
      "self_context": true
    },
    "pins": [
      {
        "pin_id": "...",
        "pin_name": "execute",
        "pin_type": {...},
        "linked_to": [...]
      }
    ]
  }
  ```

- [ ] **OUT-02**: Graph完整JSON结构
  ```json
  {
    "graph_name": "EventGraph",
    "graph_type": "event",
    "nodes": [...],
    "execution_flows": [...],
    "data_flows": [...]
  }
  ```

- [ ] **OUT-03**: 蓝图完整JSON结构
  ```json
  {
    "blueprint_name": "BP_FirstPersonCharacter",
    "parent_class": "FirstPersonCharacter",
    "graphs": [...],
    "variables": [...]
  }
  ```

### PHASE-21: 验证测试

**目标**: 验证JSON输出与UE编辑器信息一致

- [ ] **TEST-01**: 节点数量匹配
  - JSON中节点数与导出表一致

- [ ] **TEST-02**: 连接关系验证
  - Jump执行流程正确构建
  - IA_Jump → Jump → StopJumping

- [ ] **TEST-03**: 数据流验证
  - ActionValue_X → Left/Right 参数
  - ActionValue_Y → Forward/Backward 参数

- [ ] **TEST-04**: 节点属性验证
  - FunctionReference.MemberName正确提取
  - NodeGuid正确解析

---

## 输出设计原则

1. **不暴露字节细节** — JSON中不出现offset、size、raw_bytes等底层信息
2. **语义化命名** — 使用`pin_name`而非`PinName_FName_Index`
3. **结构化引用** — 使用`{"node": "...", "pin": "..."}`而非GUID字符串
4. **分类清晰** — 区分execution_flows和data_flows
5. **默认值省略** — 空值/null/false使用JSON null/false而非字符串

---

## Out of Scope

| 功能 | 原因 |
|------|------|
| Cooked资产解析 | 仅支持Editor保存的资产 |
| 蓝图字节码反编译 | 不同序列化路径 |
| UE文本格式输出 | 输出整理后的JSON |
| 自动C++生成 | 仅提供参考JSON |
| MCP Server封装 | 延后至后续里程碑 |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIN-01 | Phase 18 | Pending |
| PIN-02 | Phase 18 | Pending |
| PIN-03 | Phase 18 | Pending |
| PIN-04 | Phase 18 | Pending |
| PIN-05 | Phase 18 | Pending |
| LINK-01 | Phase 19 | Pending |
| LINK-02 | Phase 19 | Pending |
| LINK-03 | Phase 19 | Pending |
| OUT-01 | Phase 20 | Pending |
| OUT-02 | Phase 20 | Pending |
| OUT-03 | Phase 20 | Pending |
| TEST-01 | Phase 21 | Pending |
| TEST-02 | Phase 21 | Pending |
| TEST-03 | Phase 21 | Pending |
| TEST-04 | Phase 21 | Pending |

**Coverage:** 15/15 requirements mapped ✓

---

*最终版：2026-05-04 — 严格避免字节细节，输出整理后的JSON*