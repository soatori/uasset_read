---
name: asset-parse-compare
description: 解析 uasset 文件并与 CUE4Parse/UE 源码对比，生成标准化差异报告
---

# Asset Parse Compare（资产对比测试）

## 适用场景

- "解析并对比这个 uasset"
- "与 CUE4Parse 对比"
- "随机抽取测试"
- 需要验证解析正确性时

## 输入

- uasset 文件路径或目录
- 对比目标：CUE4Parse 输出 / UE 源码行为 / 预期 JSON
- 可选：关注字段或结构类型

## 流程

1. **解析资产**
   ```bash
   python run.py <file.uasset> --json > temp/actual.json
   ```

2. **获取参考输出**
   - CUE4Parse：运行参考解析器或读取缓存输出
   - UE 源码：查询对应类的序列化逻辑
   - 预期 JSON：读取提供的参考文件

3. **结构化对比**
   - 加载两份 JSON
   - 递归对比关键字段
   - 标记差异类型：缺失/多余/值不同/类型不同

4. **生成报告**
   ```markdown
   # 对比报告：<文件名>
   
   ## 摘要
   - 总字段数：X
   - 匹配：Y (Z%)
   - 差异：N
   
   ## 差异详情
   | 路径 | 实际值 | 期望值 | 类型 |
   |---|---|---|---|
   | exports[0].name | "Foo" | "Bar" | 值不同 |
   
   ## 根因分析
   - 差异 1：缺少 XXX 字段 → 对应 UE 源码 LinkerLoad.cpp:1234
   ```

5. **保存报告**
   - 报告保存到 `docs/reports/compare-<timestamp>.md`
   - 差异数据保存到 `temp/compare-diff.json`

## 输出

- 对比报告（Markdown）
- 差异数据（JSON）
- 修复建议（可选）

## 边界

- 不修改源文件
- 大文件（>10MB）时仅对比关键结构
- 遇到加密/烘焙资产时跳过并记录原因

## 项目特定约束

- 样本路径：`E:\Develop\lib\UnrealEngine\Samples`
- 参考 UE 源码确认字段含义
- 报告使用中文
