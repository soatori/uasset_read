---
phase: 3
slug: blueprint-extraction
status: planned
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 3 — 蓝图提取

> 阶段 3 的验证合同，用于执行期间的反馈采样。

---

## 测试基础设施

| 属性 | 值 |
|----------|-------|
| **框架** | pytest（来自阶段 1/2） |
| **配置文件** | 无 —— pytest.ini 在根目录 |
| **快速运行命令** | `python -m pytest tests/test_blueprint_extraction.py -v` |
| **完整套件命令** | `python -m pytest tests/ -v` |
| **估计运行时间** | ~5 秒 |

---

## 采样率

- **每次任务提交后：** 运行 `python -m pytest tests/test_blueprint_extraction.py -v`
- **每次波合并后：** 运行 `python -m pytest tests/ -v`
- **在 `/gsd-verify-work` 之前：** 完整套件必须通过
- **最大反馈延迟：** 5 秒

---

## 任务验证映射

| 任务 ID | 计划 | 波 | 需求 | 威胁参考 | 安全行为 | 测试类型 | 自动化命令 | 文件存在？ | 状态 |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | BLUE-01 | T-03-01 | ClassIndex 边界检查后查找 | unit | `pytest tests/test_blueprint_extraction.py::test_blueprint_detection -x` | ❌ Wave 0 | ⬜ 待定 |
| 03-01-02 | 01 | 1 | BLUE-02 | T-03-02 | FPackageIndex 边界检查 | unit | `pytest tests/test_blueprint_extraction.py::test_parent_class_resolution -x` | ❌ Wave 0 | ⬜ 待定 |
| 03-02-01 | 02 | 1 | BLUE-03 | T-03-03 | VarName 边界验证 | unit | `pytest tests/test_blueprint_extraction.py::test_variable_parsing -x` | ❌ Wave 0 | ⬜ 待定 |
| 03-02-02 | 02 | 1 | BLUE-05 | T-03-04 | PinType 版本感知解析 | unit | `pytest tests/test_blueprint_extraction.py::test_pin_type_parsing -x` | ❌ Wave 0 | ⬜ 待定 |
| 03-03-01 | 03 | 1 | BLUE-06 | — | PropertyFlags uint64 读取 | unit | `pytest tests/test_blueprint_extraction.py::test_variable_metadata -x` | ❌ Wave 0 | ⬜ 待定 |

*状态：⬜ 待定 · ✅ 绿色 · ❌ 红色 · ⚠️ 波动*

---

## Wave 0 需求

- [ ] `tests/test_blueprint_extraction.py` — BLUE-01、BLUE-02、BLUE-03、BLUE-05、BLUE-06 的存根
- [ ] `tests/conftest.py` 中的模拟蓝图 .uasset 数据夹具
- [ ] FirstPerson 示例资产的集成测试

现有基础设施（阶段 1/2）涵盖 pytest 和 FArchive 模式。

---

## 仅手动验证

| 行为 | 需求 | 为何手动 | 测试说明 |
|----------|-------------|------------|-------------------|
| Lyra 复杂蓝图解析 | BLUE-03 | 复杂的真实世界资产 | 解析 `LyraStarterGame/` 蓝图，验证变量提取 |

---

## 验证签字

- [ ] 所有任务都有 `<automated>` 验证或 Wave 0 依赖
- [ ] 采样连续性：无 3 个连续任务没有自动验证
- [ ] Wave 0 覆盖所有 MISSING 引用
- [ ] 无 watch-mode 标志
- [ ] 反馈延迟 < 5s
- [ ] `nyquist_compliant: true` 设置在 frontmatter

**批准：** 待定
