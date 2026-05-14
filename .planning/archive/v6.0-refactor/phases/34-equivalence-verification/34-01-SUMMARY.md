# Phase 34-01: 等价验证测试基础设施 — 执行总结

**执行日期:** 2026-05-12
**状态:** 完成 ✓

## 任务完成情况

| 任务 | 状态 | 提交 |
|------|------|------|
| Task 1: 创建测试基础设施 — DiffRecorder、deep_compare、CLI runners、报告生成 | 完成 ✓ | cf316ba |

## 交付物

### tests/test_equivalence.py

**核心组件 (6 个 helpers):**
- **DiffRecorder** 类: 收集所有差异，不中断验证流程
  - 7 个属性字段（asset, format, field, old/new value, severity, category, note）
  - 按 severity/category 筛选方法
  - 已知 9 类差异分类列表

- **deep_compare** 函数: 递归对比任意 Python 对象
  - 支持类型变化检测、dict 键增减/值变化、list 元素变化、标量值变化
  - 返回差异列表，包含完整定位路径

- **run_old_cli / run_new_cli**: 30s 超时，Windows 路径兼容
  - subprocess.run 捕获输出和退出码
  - Path.as_posix() 避免 Windows 转义问题（Pitfall 2）
  - cwd 设置为项目根目录

- **compare_outputs**: D-01 双策略对比
  - 字符串完全相等快速通过
  - JSON: json.loads → sort_keys 规范化 → deep_compare
  - Text: ObjectProperty 和 parent_class 模式检测
  - Markdown: mermaid 块计数和存在性检测（Pitfall 4）
  - 自动分类：9 类已知差异的 severity/category 判断

- **extract_mermaid_blocks**: regex 提取 ```mermaid 块
- **build_verification_report**: 生成 MARKDOWN 格式验证报告
  - 按 severity 分组（bugs/improvements/known/diffs）
  - 各分类差异详情
  - 结论和已知差异表

**测试用例 (7+ 函数，14 个总测试用例):**
| 测试函数 | 覆盖需求 | 格式 | 资产类型 |
|----------|---------|------|---------|
| test_json_full_synthetic | 等价-01, 等价-05 | JSON Full | 合成 |
| test_json_summary_synthetic | 等价-02 | JSON Summary | 合成 |
| test_json_summary_equivalence | 等价-02, 等价-06 | JSON Summary | 3 真实资产 |
| test_text_equivalence | 等价-03 | Text | 合成+2 真实 |
| test_markdown_equivalence | 等价-04 | Markdown | 合成+2 真实 |
| test_synthetic_all_formats | 等价-05 | 全部 4 种 | 合成 |
| test_real_assets_all_formats | 等价-06 | 3 种 | BP_FirstPersonCharacter |
| test_verification_report_generated | 等价-07 | - | 报告生成 |

**关键实现点:**
- Per D-04: 记录并继续 — 所有测试 assert True，差异记录到 recorder
- Per D-07: 所有验证函数在 tests/test_equivalence.py 中
- Per Pitfall 1: json.dumps(sort_keys=True, ensure_ascii=False) 规范化
- Per Pitfall 2: Path.as_posix() Windows 路径兼容
- Per Pitfall 4: extract_mermaid_blocks 显式检测
- atexit.register: 测试进程退出时写入 VERIFICATION.md
- 全局 recorder: 所有测试共享同一实例

## 验收标准验证

✅ tests/test_equivalence.py 文件存在
✅ DiffRecorder: 1 个类定义
✅ deep_compare: 1 个函数定义
✅ run_old_cli / run_new_cli: 2 个 CLI runner
✅ extract_mermaid_blocks: 1 个 mermaid 提取函数
✅ build_verification_report: 1 个报告生成函数
✅ subprocess 调用: ≥ 2 处
✅ json.dumps sort_keys: 1 处
✅ as_posix 调用: ≥ 1 处
✅ Python 语法: 无错误（py_compile 通过）
✅ pytest 收集: 14 个测试用例
✅ 所有 helper 可导入

## 需求覆盖

- [x] 等价-01: JSON Full 输出等价（合成资产验证）
- [x] 等价-02: JSON Summary 输出等价（合成+真实资产）
- [x] 等价-03: Text 输出等价
- [x] 等价-04: Markdown 输出等价
- [x] 等价-05: 合成资产验证
- [x] 等价-06: 真实资产验证
- [x] 等价-07: VERIFICATION.md 报告生成

## 关键决策点

1. **记录并继续策略**: 所有测试使用 assert True，不中断流程
2. **路径兼容**: 全部使用 Path.as_posix()
3. **JSON 规范化**: sort_keys 确保键顺序不影响比较
4. **模块化助手**: 每个 helper 独立职责单一，可单独测试

---
**下一阶段**: 34-02 — 执行验证并修复确认的 bug
