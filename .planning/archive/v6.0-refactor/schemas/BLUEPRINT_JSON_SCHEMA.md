# 蓝图 JSON Schema

## 版本信息

- Schema 版本: 1.0
- 目标: 规范化蓝图解析结果的 JSON 输出格式
- 用途: C++ 代码生成、数据分析、API 响应

## 完整 Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "status"],
  "properties": {
    "version": {
      "type": "string",
      "description": "Schema 版本号"
    },
    "status": {
      "type": "string",
      "enum": ["success", "fail", "error"],
      "description": "解析状态"
    },
    "message": {
      "type": "string",
      "description": "状态消息（可选）"
    },
    "code": {
      "type": "string",
      "description": "错误代码（可选）"
    },
    "errors": {
      "type": "array",
      "items": {"type": "string"},
      "description": "解析错误列表"
    },
    "warnings": {
      "type": "array",
      "items": {"type": "string"},
      "description": "警告列表"
    },
    "asset": {
      "type": "object",
      "properties": {
        "package_path": {
          "type": "string",
          "description": "资产路径（如 /Game/Blueprints/MyBlueprint）"
        },
        "file_version_ue4": {
          "type": "integer",
          "description": "UE4 文件版本号"
        },
        "file_version_ue5": {
          "type": "integer",
          "description": "UE5 文件版本号"
        },
        "legacy_file_version": {
          "type": "integer",
          "description": "Legacy 文件版本号"
        },
        "package_flags": {
          "type": "integer",
          "description": "包标志位"
        }
      }
    },
    "blueprint": {
      "type": "object",
      "properties": {
        "is_blueprint": {
          "type": "boolean",
          "description": "是否为蓝图"
        },
        "name": {
          "type": "string",
          "description": "蓝图名称"
        },
        "parent_class": {
          "type": "string",
          "description": "父类名（直接父类）"
        },
        "blueprint_type": {
          "type": "string",
          "enum": ["Normal", "Interface", "Macro", "Function", "Class"],
          "description": "蓝图类型"
        },
        "variables": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/variable"
          },
          "description": "变量列表"
        },
        "functions": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/function"
          },
          "description": "函数列表"
        },
        "events": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/event"
          },
          "description": "事件列表"
        },
        "detection_warning": {
          "type": "string",
          "description": "检测警告（如有）"
        }
      }
    },
    "graphs": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/graph"
      },
      "description": "蓝图图列表"
    },
    "dependencies": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": {"type": "string"},
          "class_name": {"type": "string"},
          "object_name": {"type": "string"},
          "package": {"type": "string"}
        }
      },
      "description": "硬依赖列表"
    },
    "soft_references": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "type": {"type": "string"}
        }
      },
      "description": "软引用列表"
    },
    "circular_dependencies": {
      "type": "array",
      "items": {
        "type": "array",
        "items": {"type": "string"}
      },
      "description": "循环依赖路径列表"
    },
    "metadata": {
      "type": "object",
      "properties": {
        "parse_time_ms": {
          "type": "number",
          "description": "解析耗时（毫秒）"
        },
        "file_size": {
          "type": "integer",
          "description": "文件大小（字节）"
        },
        "mmap_used": {
          "type": "boolean",
          "description": "是否使用 mmap"
        }
      }
    }
  },
  "definitions": {
    "variable": {
      "type": "object",
      "required": ["name", "type"],
      "properties": {
        "name": {
          "type": "string",
          "description": "变量名"
        },
        "type": {
          "type": "object",
          "description": "变量类型信息（Phase 26：增强）",
          "properties": {
            "pin_category": {"type": "string"},
            "pin_sub_category": {"type": "string"},
            "container_type": {"type": "integer"},
            "is_reference": {"type": "boolean"},
            "is_const": {"type": "boolean"}
          }
        },
        "category": {
          "type": "string",
          "description": "分类"
        },
        "default_value": {
          "description": "默认值",
          "oneOf": [
            {"type": "string"},
            {"type": "number"},
            {"type": "boolean"},
            {"type": "null"}
          ]
        },
        "friendly_name": {
          "type": "string",
          "description": "友好名称"
        },
        "is_component": {
          "type": "boolean",
          "description": "是否为组件变量"
        },
        "visibility": {
          "type": "string",
          "enum": ["EditAnywhere", "EditDefaultsOnly", "EditInstanceOnly", "VisibleAnywhere", "VisibleInstanceOnly"],
          "description": "可见性"
        },
        "property_flags": {
          "type": "integer",
          "description": "属性标志位（CPF_*）"
        },
        "flags_labels": {
          "type": "array",
          "items": {"type": "string"},
          "description": "标志位标签列表"
        },
        "metadata": {
          "type": "object",
          "additionalProperties": {"type": "string"},
          "description": "元数据字典"
        },
        "edit_condition": {
          "type": "string",
          "description": "EditCondition 表达式（Phase 26：增强）"
        },
        "edit_category": {
          "type": "string",
          "description": "编辑分类（Phase 26：增强）"
        },
        "edit_widget": {
          "type": "string",
          "description": "编辑控件（SpinBox、Slider等）（Phase 26：增强）"
        },
        "is_edit_anywhere": {
          "type": "boolean",
          "description": "EditAnywhere 标志（Phase 26：增强）"
        },
        "is_edit_instance_only": {
          "type": "boolean",
          "description": "EditInstanceOnly 标志（Phase 26：增强）"
        },
        "is_visible_anywhere": {
          "type": "boolean",
          "description": "VisibleAnywhere 标志（Phase 26：增强）"
        },
        "is_blueprint_read_only": {
          "type": "boolean",
          "description": "BlueprintReadOnly 标志（Phase 26：增强）"
        },
        "is_blueprint_readable": {
          "type": "boolean",
          "description": "BlueprintReadWrite 读取标志（Phase 26：增强）"
        },
        "is_blueprint_writable": {
          "type": "boolean",
          "description": "BlueprintReadWrite 写入标志（Phase 26：增强）"
        },
        "is_blueprint_assignable": {
          "type": "boolean",
          "description": "BlueprintAssignable 标志（Phase 26：增强）"
        },
        "is_blueprint_callable": {
          "type": "boolean",
          "description": "BlueprintCallable 标志（Phase 26：增强）"
        },
        "is_transient": {
          "type": "boolean",
          "description": "Transient 标志（Phase 26：增强）"
        },
        "is_duplicate_transient": {
          "type": "boolean",
          "description": "DuplicateTransient 标志（Phase 26：增强）"
        },
        "is_text_export_transient": {
          "type": "boolean",
          "description": "TextExportTransient 标志（Phase 26：增强）"
        },
        "is_non_transient": {
          "type": "boolean",
          "description": "NonTransient 标志（Phase 26：增强）"
        },
        "is_export_object": {
          "type": "boolean",
          "description": "ExportObject 标志（Phase 26：增强）"
        },
        "is_save_game": {
          "type": "boolean",
          "description": "SaveGame 标志（Phase 26：增强）"
        },
        "is_no_clear": {
          "type": "boolean",
          "description": "NoClear 标志（Phase 26：增强）"
        },
        "is_reference_only": {
          "type": "boolean",
          "description": "ReferenceOnly 标志（Phase 26：增强）"
        },
        "is_rep_notify": {
          "type": "boolean",
          "description": "RepNotify 标志（Phase 26：增强）"
        },
        "is_interp": {
          "type": "boolean",
          "description": "Interp 标志（Phase 26：增强）"
        },
        "is_expose_on_spawn": {
          "type": "boolean",
          "description": "ExposeOnSpawn 标志（Phase 26：增强）"
        },
        "is_net": {
          "type": "boolean",
          "description": "Net 标志（Phase 26：增强）"
        },
        "is_replicated": {
          "type": "boolean",
          "description": "Replicated 标志（Phase 26：增强）"
        },
        "is_non_pi_ed_duplicate_transient": {
          "type": "boolean",
          "description": "NonPIEDuplicateTransient 标志（Phase 26：增强）"
        },
        "meta_data": {
          "type": "object",
          "description": "元数据字典（Phase 26：增强）"
        }
      }
    },
    "function": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": {
          "type": "string",
          "description": "函数名"
        },
        "return_type": {
          "type": "string",
          "description": "返回类型"
        },
        "function_flags": {
          "type": "integer",
          "description": "函数标志位（FUNC_*）（Phase 26：增强）"
        },
        "parameters": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/parameter"
          },
          "description": "参数列表"
        },
        "is_pure": {
          "type": "boolean",
          "description": "是否为纯函数（Phase 26：增强）"
        },
        "is_blueprint_callable": {
          "type": "boolean",
          "description": "是否可在蓝图中调用（Phase 26：增强）"
        },
        "is_blueprint_event": {
          "type": "boolean",
          "description": "是否为蓝图事件（Phase 26：增强）"
        },
        "is_blueprint_implementable_event": {
          "type": "boolean",
          "description": "是否为可实现的蓝图事件（Phase 26：增强）"
        },
        "is_native": {
          "type": "boolean",
          "description": "是否为原生函数（Phase 26：增强）"
        },
        "is_const": {
          "type": "boolean",
          "description": "是否为常量函数（Phase 26：增强）"
        },
        "is_static": {
          "type": "boolean",
          "description": "是否为静态函数（Phase 26：增强）"
        },
        "is_virtual": {
          "type": "boolean",
          "description": "是否为虚函数（Phase 26：增强）"
        },
        "is_exec": {
          "type": "boolean",
          "description": "是否为 Exec 函数（Phase 26：增强）"
        },
        "is_net": {
          "type": "boolean",
          "description": "是否为网络函数（Phase 26：增强）"
        },
        "is_net_reliable": {
          "type": "boolean",
          "description": "是否为可靠网络函数（Phase 26：增强）"
        },
        "is_net_server": {
          "type": "boolean",
          "description": "是否为服务器函数（Phase 26：增强）"
        },
        "is_net_client": {
          "type": "boolean",
          "description": "是否为客户端函数（Phase 26：增强）"
        },
        "is_net_multicast": {
          "type": "boolean",
          "description": "是否为多播网络函数（Phase 26：增强）"
        },
        "is_blueprint_private": {
          "type": "boolean",
          "description": "是否为蓝图私有（Phase 26：增强）"
        },
        "is_blueprint_protected": {
          "type": "boolean",
          "description": "是否为蓝图保护（Phase 26：增强）"
        },
        "is_blueprint_public": {
          "type": "boolean",
          "description": "是否为蓝图公开（Phase 26：增强）"
        },
        "is_blueprint_pure": {
          "type": "boolean",
          "description": "是否为蓝图纯函数（Phase 26：增强）"
        },
        "is_blueprint_cosmetic": {
          "type": "boolean",
          "description": "是否为蓝图装饰（Phase 26：增强）"
        },
        "is_editor_only": {
          "type": "boolean",
          "description": "是否仅用于编辑器（Phase 26：增强）"
        },
        "is_final": {
          "type": "boolean",
          "description": "是否为最终函数（Phase 26：增强）"
        },
        "is_delegate": {
          "type": "boolean",
          "description": "是否为委托（Phase 26：增强）"
        },
        "is_multicast_delegate": {
          "type": "boolean",
          "description": "是否为多播委托（Phase 26：增强）"
        },
        "is_has_out_parms": {
          "type": "boolean",
          "description": "是否有输出参数（Phase 26：增强）"
        },
        "is_has_defaults": {
          "type": "boolean",
          "description": "是否有默认值（Phase 26：增强）"
        },
        "access_specifier": {
          "type": "string",
          "enum": ["Public", "Private", "Protected"],
          "description": "访问修饰符（Phase 26：增强）"
        },
        "meta_data": {
          "type": "object",
          "description": "元数据字典（Phase 26：增强）"
        }
      }
    },
    "parameter": {
      "type": "object",
      "required": ["name", "type", "direction"],
      "properties": {
        "name": {
          "type": "string",
          "description": "参数名"
        },
        "type": {
          "type": "string",
          "description": "参数类型"
        },
        "default_value": {
          "description": "默认值（Phase 26：增强）"
        },
        "is_input": {
          "type": "boolean",
          "description": "是否为输入参数（Phase 26：增强）"
        },
        "is_output": {
          "type": "boolean",
          "description": "是否为输出参数（Phase 26：增强）"
        },
        "is_optional": {
          "type": "boolean",
          "description": "是否为可选参数（Phase 26：增强）"
        },
        "property_flags": {
          "type": "integer",
          "description": "属性标志位（Phase 26：增强）"
        },
        "meta_data": {
          "type": "object",
          "description": "元数据字典（Phase 26：增强）"
        }
      }
    },
    "event": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": {
          "type": "string",
          "description": "事件名"
        },
        "event_type": {
          "type": "string",
          "enum": ["CustomEvent", "OverriddenEvent", "InterfaceEvent", "Unknown"],
          "description": "事件类型（Phase 26：增强）"
        },
        "function_flags": {
          "type": "integer",
          "description": "函数标志位（Phase 26：增强）"
        },
        "is_blueprint_event": {
          "type": "boolean",
          "description": "是否为蓝图事件（Phase 26：增强）"
        },
        "is_blueprint_implementable_event": {
          "type": "boolean",
          "description": "是否为可实现的蓝图事件（Phase 26：增强）"
        },
        "is_net": {
          "type": "boolean",
          "description": "是否为网络事件（Phase 26：增强）"
        },
        "is_net_multicast": {
          "type": "boolean",
          "description": "是否为多播网络事件（Phase 26：增强）"
        },
        "is_net_reliable": {
          "type": "boolean",
          "description": "是否为可靠网络事件（Phase 26：增强）"
        },
        "is_net_client": {
          "type": "boolean",
          "description": "是否为客户端事件（Phase 26：增强）"
        },
        "is_net_server": {
          "type": "boolean",
          "description": "是否为服务器事件（Phase 26：增强）"
        },
        "is_replicated": {
          "type": "boolean",
          "description": "是否为复制事件（Phase 26：增强）"
        },
        "is_cosmetic": {
          "type": "boolean",
          "description": "是否为装饰事件（Phase 26：增强）"
        },
        "is_static": {
          "type": "boolean",
          "description": "是否为静态事件（Phase 26：增强）"
        },
        "is_multicast": {
          "type": "boolean",
          "description": "是否为多播事件（Phase 26：增强）"
        },
        "is_override": {
          "type": "boolean",
          "description": "是否为重写事件（Phase 26：增强）"
        },
        "override_parent_class": {
          "type": "string",
          "description": "重写的父类（Phase 26：增强）"
        },
        "override_parent_event": {
          "type": "string",
          "description": "重写的父事件（Phase 26：增强）"
        },
        "is_interface_event": {
          "type": "boolean",
          "description": "是否为接口事件（Phase 26：增强）"
        },
        "interface_class": {
          "type": "string",
          "description": "接口类名（Phase 26：增强）"
        },
        "parameters": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/parameter"
          },
          "description": "参数列表（Phase 26：增强）"
        },
        "multicast_delegate": {
          "$ref": "#/definitions/multicast_delegate",
          "description": "多播委托信息（Phase 26：增强）"
        },
        "meta_data": {
          "type": "object",
          "description": "元数据字典（Phase 26：增强）"
        }
      }
    },
    "multicast_delegate": {
      "type": "object",
      "properties": {
        "delegate_name": {
          "type": "string",
          "description": "委托名称（Phase 26：新增）"
        },
        "signature_function": {
          "type": "string",
          "description": "签名函数（Phase 26：新增）"
        },
        "is_callable_in_blueprint": {
          "type": "boolean",
          "description": "是否可在蓝图中调用（Phase 26：新增）"
        }
      }
    },
    "graph": {
      "type": "object",
      "required": ["name", "class"],
      "properties": {
        "name": {
          "type": "string",
          "description": "图名称"
        },
        "class": {
          "type": "string",
          "description": "图类名（如 EdGraph, UberEdGraph）"
        },
        "schema": {
          "type": "string",
          "description": "图 Schema"
        },
        "guid": {
          "type": "string",
          "description": "图 GUID"
        },
        "is_editable": {
          "type": "boolean",
          "description": "是否可编辑"
        },
        "nodes": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/node"
          },
          "description": "节点列表"
        },
        "execution_flows": {
          "type": "array",
          "items": {
            "type": "array",
            "items": {"type": "string"}
          },
          "description": "执行流路径"
        },
        "data_flows": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "source": {
                "type": "object",
                "properties": {
                  "node_id": {"type": "string"},
                  "pin_id": {"type": "string"},
                  "pin_name": {"type": "string"}
                }
              },
              "target": {
                "type": "object",
                "properties": {
                  "node_id": {"type": "string"},
                  "pin_id": {"type": "string"},
                  "pin_name": {"type": "string"}
                }
              }
            }
          },
          "description": "数据流连接"
        }
      }
    },
    "node": {
      "type": "object",
      "required": ["guid", "class_name"],
      "properties": {
        "guid": {
          "type": "string",
          "description": "节点 GUID"
        },
        "class_name": {
          "type": "string",
          "description": "节点类名（如 K2Node_CallFunction, K2Node_Event）"
        },
        "position": {
          "type": "object",
          "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"}
          },
          "description": "节点位置（像素）"
        },
        "comment": {
          "type": "string",
          "description": "注释文本"
        },
        "pins": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/pin"
          },
          "description": "引脚列表"
        },
        "node_data": {
          "type": "object",
          "description": "节点类型特定数据"
        }
      }
    },
    "pin": {
      "type": "object",
      "required": ["id", "name", "direction"],
      "properties": {
        "id": {
          "type": "string",
          "description": "引脚 ID（GUID）"
        },
        "name": {
          "type": "string",
          "description": "引脚名称"
        },
        "direction": {
          "type": "string",
          "enum": ["Input", "Output", "None"],
          "description": "引脚方向"
        },
        "tooltip": {
          "type": "string",
          "description": "工具提示"
        },
        "pin_type": {
          "type": "object",
          "properties": {
            "category": {
              "type": "string",
              "description": "引脚类别（如 bool, int, exec）"
            },
            "sub_category": {
              "type": "string",
              "description": "子类别"
            },
            "sub_category_object": {
              "type": "string",
              "description": "子类别对象类名"
            },
            "container_type": {
              "type": "integer",
              "description": "容器类型（0=None, 1=Array, 2=Set, 3=Map）"
            },
            "is_reference": {
              "type": "boolean",
              "description": "是否为引用"
            }
          },
          "description": "引脚类型信息"
        },
        "default_value": {
          "type": "string",
          "description": "默认值"
        },
        "default_object": {
          "type": "string",
          "description": "默认对象引用"
        },
        "linked_to": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "node_guid": {"type": "string"},
              "pin_id": {"type": "string"},
              "pin_name": {"type": "string"}
            }
          },
          "description": "连接的引脚列表"
        },
        "hidden": {
          "type": "boolean",
          "description": "是否隐藏"
        },
        "not_connectable": {
          "type": "boolean",
          "description": "是否不可连接"
        },
        "advanced_view": {
          "type": "boolean",
          "description": "是否在高级视图中"
        }
      }
    }
  }
}
```

## 示例输出

```json
{
  "version": "1.0",
  "status": "success",
  "errors": [],
  "warnings": [],
  "asset": {
    "package_path": "/Game/Blueprints/BP_MyCharacter",
    "file_version_ue4": 512,
    "file_version_ue5": 517,
    "legacy_file_version": -9,
    "package_flags": 0
  },
  "blueprint": {
    "is_blueprint": true,
    "name": "BP_MyCharacter",
    "parent_class": "ACharacter",
    "blueprint_type": "Normal",
    "variables": [
      {
        "name": "Health",
        "type": {
          "pin_category": "float",
          "pin_sub_category": "",
          "container_type": 0,
          "is_reference": false,
          "is_const": false
        },
        "category": "Stats",
        "default_value": 100.0,
        "friendly_name": "Health",
        "is_component": false,
        "visibility": "EditAnywhere",
        "property_flags": 65536,
        "flags_labels": ["Edit", "BlueprintReadWrite"],
        "metadata": {},
        "edit_condition": "",
        "edit_category": "",
        "edit_widget": "",
        "is_edit_anywhere": true,
        "is_edit_instance_only": false,
        "is_visible_anywhere": false,
        "is_blueprint_read_only": false,
        "is_blueprint_readable": true,
        "is_blueprint_writable": true,
        "is_blueprint_assignable": false,
        "is_blueprint_callable": false,
        "is_transient": false,
        "is_duplicate_transient": false,
        "is_text_export_transient": false,
        "is_non_transient": false,
        "is_export_object": false,
        "is_save_game": false,
        "is_no_clear": false,
        "is_reference_only": false,
        "is_rep_notify": false,
        "is_interp": false,
        "is_expose_on_spawn": false,
        "is_net": false,
        "is_replicated": false,
        "is_non_pi_ed_duplicate_transient": false,
        "meta_data": {}
      }
    ],
    "functions": [
      {
        "name": "TakeDamage",
        "return_type": "float",
        "function_flags": 0,
        "parameters": [
          {
            "name": "DamageAmount",
            "type": "float",
            "default_value": null,
            "is_input": true,
            "is_output": false,
            "is_optional": false,
            "property_flags": 0,
            "meta_data": {}
          }
        ],
        "is_pure": false,
        "is_blueprint_callable": true,
        "is_blueprint_event": false,
        "is_blueprint_implementable_event": false,
        "is_native": false,
        "is_const": false,
        "is_static": false,
        "is_virtual": false,
        "is_exec": false,
        "is_net": false,
        "is_net_reliable": false,
        "is_net_server": false,
        "is_net_client": false,
        "is_net_multicast": false,
        "is_blueprint_private": false,
        "is_blueprint_protected": false,
        "is_blueprint_public": true,
        "is_blueprint_pure": false,
        "is_blueprint_cosmetic": false,
        "is_editor_only": false,
        "is_final": false,
        "is_delegate": false,
        "is_multicast_delegate": false,
        "is_has_out_parms": false,
        "is_has_defaults": false,
        "access_specifier": "Public",
        "meta_data": {}
      }
    ],
    "events": [
      {
        "name": "OnDeath",
        "event_type": "CustomEvent",
        "function_flags": 0,
        "is_blueprint_event": true,
        "is_blueprint_implementable_event": false,
        "is_net": false,
        "is_net_multicast": false,
        "is_net_reliable": false,
        "is_net_client": false,
        "is_net_server": false,
        "is_replicated": false,
        "is_cosmetic": false,
        "is_static": false,
        "is_multicast": false,
        "is_override": false,
        "override_parent_class": "",
        "override_parent_event": "",
        "is_interface_event": false,
        "interface_class": "",
        "parameters": [],
        "multicast_delegate": null,
        "meta_data": {}
      }
    ]
  },
  "graphs": [
    {
      "name": "EventGraph",
      "class": "EdGraph",
      "schema": null,
      "guid": "01234567-89AB-CDEF-0123-456789ABCDEF",
      "is_editable": true,
      "nodes": [
        {
          "guid": "89ABCDEF-0123-4567-89AB-CDEF01234567",
          "class_name": "K2Node_Event",
          "position": {"x": 0, "y": 0},
          "comment": "",
          "pins": [
            {
              "id": "ABCDEF01-2345-6789-ABCD-EF0123456789",
              "name": "Then",
              "direction": "Output",
              "tooltip": "",
              "pin_type": {"category": "exec"},
              "linked_to": []
            }
          ],
          "node_data": null
        }
      ],
      "execution_flows": [],
      "data_flows": []
    }
  ],
  "dependencies": [],
  "soft_references": [],
  "circular_dependencies": [],
  "metadata": {
    "parse_time_ms": 123.45,
    "file_size": 102400,
    "mmap_used": false
  }
}
```

## C++ 代码生成映射

此 JSON Schema 设计考虑了 C++ 代码生成的需求：

### 变量映射
- `name` → 变量名（转换为 PascalCase/CamelCase）
- `type` → C++ 类型（如 `float`, `FString`, `UObject*`）
- `visibility` → UPROPERTY 宏参数
- `default_value` → 构造函数初始化列表
- `flags_labels` → UPROPERTY 标志位

### 函数映射
- `name` → 函数名
- `return_type` → 函数返回类型
- `parameters` → 函数参数列表
- `is_blueprint_callable` → `UFUNCTION(BlueprintCallable)`
- `is_pure` → `UFUNCTION(BlueprintPure)`

### 事件映射
- `name` → 事件名
- `is_multicast` → 多播委托或事件
- `is_override` → virtual 关键字

### 图映射
- `execution_flows` → 函数体代码结构
- `data_flows` → 变量引用和传递