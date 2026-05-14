# Phase 31: 蓝图图解析模块 - Validation Strategy

**Phase:** 31
**Date:** 2026-05-12

## Validation Architecture

### Dimension 1: Binary Parsing Correctness
| Function | Verify Command | Expected |
|----------|---------------|----------|
| read_ed_graph_pin_type | `python -c "from uasset_read.serializers.graph import read_ed_graph_pin_type; print('OK')"` | Import succeeds |
| read_ue_graph_pin | `python -c "from uasset_read.serializers.graph import read_ue_graph_pin; print('OK')"` | Import succeeds |
| read_ue_graph_node | `python -c "from uasset_read.serializers.graph import read_ue_graph_node; print('OK')"` | Import succeeds |
| read_ue_graph | `python -c "from uasset_read.serializers.graph import read_ue_graph; print('OK')"` | Import succeeds |

### Dimension 2: Node Type Dispatch
| Type | Verify Command | Expected |
|------|---------------|----------|
| K2Node_CallFunction | `grep -c "def read_k2node_call_function" src/uasset_read/serializers/graph.py` | >= 1 |
| K2Node_Event | `grep -c "def read_k2node_event" src/uasset_read/serializers/graph.py` | >= 1 |
| K2Node_Knot | `grep -c "def read_k2node_knot" src/uasset_read/serializers/graph.py` | >= 1 |
| EdGraphNode_Comment | `grep -c "def read_edgraph_node_comment" src/uasset_read/serializers/graph.py` | >= 1 |
| K2Node_EnhancedInputAction | `grep -c "def read_k2node_enhanced_input" src/uasset_read/serializers/graph.py` | >= 1 |

### Dimension 3: Factory Pattern
| Check | Command | Expected |
|-------|---------|----------|
| Factory function exists | `grep -c "def create_node_from_archive" src/uasset_read/serializers/graph.py` | >= 1 |
| 5 type cases covered | `grep -c 'case "K2Node_' src/uasset_read/serializers/graph.py` | >= 5 |
| Unknown fallback | `grep -c "case _:" src/uasset_read/serializers/graph.py` | >= 1 |

### Dimension 4: Flow Building
| Function | Verify Command | Expected |
|----------|---------------|----------|
| extract_blueprint_graphs | `python -c "from uasset_read.graph import extract_blueprint_graphs; print('OK')"` | Import succeeds |
| build_execution_flows | `python -c "from uasset_read.graph import build_execution_flows; print('OK')"` | Import succeeds |
| build_data_flows | `python -c "from uasset_read.graph import build_data_flows; print('OK')"` | Import succeeds |
| build_connections_map | `python -c "from uasset_read.graph import build_connections_map; print('OK')"` | Import succeeds |

### Dimension 5: Safety Constants
| Constant | Verify Command | Expected |
|----------|---------------|----------|
| MAX_PINS_PER_NODE in graph.py | `grep "MAX_PINS_PER_NODE" src/uasset_read/serializers/graph.py` | Present |
| MAX_NODES_PER_GRAPH in graph.py | `grep "MAX_NODES_PER_GRAPH" src/uasset_read/serializers/graph.py` | Present |
| MAX_LINKEDTO_PER_PIN in graph.py | `grep "MAX_LINKEDTO_PER_PIN" src/uasset_read/serializers/graph.py` | Present |

### Dimension 6: Model Delegation
| Check | Command | Expected |
|-------|---------|----------|
| No NotImplementedError in core.py | `grep -c "NotImplementedError" src/uasset_read/models/core.py` | 0 |
| No NotImplementedError in node_types.py | `grep -c "NotImplementedError" src/uasset_read/models/node_types.py` | 0 |
| from_archive delegates in core.py | `grep -c "from uasset_read.serializers.graph import" src/uasset_read/models/core.py` | >= 5 |

### Dimension 7: No Circular Imports
| Check | Command | Expected |
|-------|---------|----------|
| Top-level import | `python -c "import uasset_read; print('OK')"` | Exit 0 |
| Graph module import | `python -c "from uasset_read.graph import extract_blueprint_graphs; print('OK')"` | Exit 0 |

### Dimension 8: Test Compatibility
| Check | Command | Expected |
|-------|---------|----------|
| Graph parsing test imports | `python -c "exec(open('tests/test_graph_parsing.py').read().split('def test_')[0])"` | No ImportError |
| Full test suite | `pytest tests/test_graph_parsing.py -v --tb=short` | Pass (skips acceptable) |
