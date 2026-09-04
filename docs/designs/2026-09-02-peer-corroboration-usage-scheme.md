# 案例项目（external/ peer）佐证使用方案

status: current

> 针对"实现先行"工作流的证据缺口：本地 UE 树单一版本浅克隆（5.8.1-release）无法保证源码引用与
> fixture 时代（4.27/5.2）二进制完全匹配，单一源码阅读也可能误读。本方案定义 peer 案例项目
> （external/ 九个解析器）在证据链中的位置、触发条件与记录形式。来源：2026-09-02 四族 handler
> 引用核对（`temp/ue-source-handler-claims-audit-2026-09-02.md`）与 09-02 全模块审计实践
> （`temp/ue-source-audit-2026-09-02.md`）。**两份审计产物位于 `temp/`：不入库，且被 CI 的
> `^temp/` 黑名单阻挡**。它们只是本机 provenance，不是可验证证据。任何依赖其结论的表述必须在
> 受版本控制的文档内自足——peer 事实见 `docs/reference/external-peer-inventory.md`。

## 1. 原则（不因本方案改变）

- UE C++ 源码是二进制布局的唯一权威；peer 是佐证，不是证明。
- 真实 fixture + 结构断言仍是"支持宣称"的最终验收；peer 共识不能替代 fixture gate。
- "全 peer 同错"= 共享盲区：既不能豁免源码裁决，也不构成我们的 gap（记录为"与 X 同错"）。

## 2. 三种必查 peer 的场景

| 场景 | 动作 | 注释形式 |
| --- | --- | --- |
| 实现先行（fixture 缺失）且 peer 覆盖该布局 | 逐字段比对 peer 解析器 | `Corroborated (not proof): CUE4Parse X, UAssetAPI Y`（先例 `legacy.py:1101`；全仓目前仅此一处，先例很薄） |
| 实现先行且 peer 零覆盖 | 不做猜测，照常实现 | 注明 `No peer parser decodes this type`（先例 `handlers.py:1766` AnimLayerInterfaceHandler；措辞以代码为准） |
| 跨时代风险字段（新增/重命名属性、版本门控、枚举序） | 比对 peer 的版本枚举副本与分支处理 | 结论记入审查报告而非仅注释 |

## 3. 执行规则

1. **禁止**裸复数措辞 `corroborated by peers`（CI `peer-evidence-hygiene` 步骤按字符串拒绝）。
   共识必须逐一点名 peer 及其符号，形式为 `Corroborated (not proof): <Peer> <symbol>`；
   ≥2 **相互独立**的实现才可称共识——UAssetGUI 委托 UAssetAPI，二者只计一个实现。
2. 实现先行的 docstring 必须带三件套：UE source 相对路径引用、peer 佐证/零覆盖声明、
   时代假设（该字段是否 4.27→5.8 稳定，不稳定时给出门控条件）。
3. 时代负向断言（"旧版没有 X"）在本地只有 5.8 单树时必须标注证据等级：枚举序佐证 / CUE4Parse
   副本 / 知识性高置信——禁止把三者写成源码证明。
4. 每轮模块级审查保留 peer 覆盖矩阵一栏（哪个 peer 覆盖该布局、是否一致）。**矩阵结论必须落进
   受版本控制的文档**：peer 静态事实进 `docs/reference/external-peer-inventory.md`，逐字段核对
   结论进对应设计/审查文档。`temp/` 不入库且被 CI 拉黑，只能当运行日志，不得作为唯一载体。
5. fixture 到位后 peer 声明降级为背景信息，验收以 fixture 断言为准。

## 4. peer 清单

清单本体（语言、pin commit、日期、许可证、逐行核实过的覆盖域）在
**`docs/reference/external-peer-inventory.md`**。本节不再内嵌副本：旧版在此重复一份表格，
而那份表格有两行事实错误（Unreal-Library 实为 C# 而非 Python；uasset-rs / uasset-reader-js
只佐证包头布局，**不解析 tagged property 值**），而 `external/` 被 `.gitignore:5` 忽略，
原计划写入的 `external/README.md` 永远无法入库，pin 记录对任何 clone 都不可见。

两条授权红线（详见 inventory）：**AssetToJson 无 LICENSE 文件** = 保留所有权利；
**UE4TextExtractor 为 MIT NON-AI License**，而本项目主要消费者是 AI agent——二者只允许
人类直接阅读，不得将内容转录进仓库或据此生成入库代码。Lyra/ALS 属 Epic EULA 的 fixture
不得入仓库（先例 #619）。

## 5. 边界

- peer 分歧时以 UE 源码为准；源码与 peer 持续冲突且 fixture 缺席 → 该功能维持 summary 级、
  声明降级，不做猜测性解码。
- 本方案只约束证据与注释，不改变 handler 分级（capability）、诊断或输出契约。
- **从属关系**：本方案不放宽 `.claude/rules/constraints.md` Test Organization 末条——一条
  `Corroborated (not proof):` 注释**不构成** version/asset-support 宣称，它只能出现在
  summary/实现先行档位的代码里。支撑宣称仍需 UE source evidence + real fixture +
  structural assertions。本方案的原则部分已由 constraints.md「UE source reference required」
  覆盖，此处只补操作细则。
