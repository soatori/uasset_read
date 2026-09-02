# 案例项目（external/ peer）佐证使用方案

status: target

> 针对"实现先行"工作流的证据缺口：本地 UE 树单一版本浅克隆（5.8.1-release）无法保证源码引用与
> fixture 时代（4.27/5.2）二进制完全匹配，单一源码阅读也可能误读。本方案定义 peer 案例项目
> （external/ 九个解析器）在证据链中的位置、触发条件与记录形式。来源：2026-09-02 四族 handler
> 引用核对（`temp/ue-source-handler-claims-audit-2026-09-02.md`）与 09-02 全模块审计实践
> （`temp/ue-source-audit-2026-09-02.md`）。

## 1. 原则（不因本方案改变）

- UE C++ 源码是二进制布局的唯一权威；peer 是佐证，不是证明。
- 真实 fixture + 结构断言仍是"支持宣称"的最终验收；peer 共识不能替代 fixture gate。
- "全 peer 同错"= 共享盲区：既不能豁免源码裁决，也不构成我们的 gap（记录为"与 X 同错"）。

## 2. 三种必查 peer 的场景

| 场景 | 动作 | 注释形式 |
|---|---|---|
| 实现先行（fixture 缺失）且 peer 覆盖该布局 | 逐字段比对 peer 解析器 | `Corroborated (not proof): CUE4Parse X, UAssetAPI Y`（先例 legacy.py:845） |
| 实现先行且 peer 零覆盖 | 不做猜测，照常实现 | docstring 注明 `No peer parser covers this type`（先例 AnimLayerInterfaceHandler） |
| 跨时代风险字段（新增/重命名属性、版本门控、枚举序） | 比对 peer 的版本枚举副本与分支处理 | 结论记入审查报告而非仅注释 |

## 3. 执行规则

1. 独立实现共识数 ≥2 才可写 "corroborated by peers"；单 peer 只能写点名佐证，不写复数共识。
2. 实现先行的 docstring 必须带三件套：UE source 相对路径引用、peer 佐证/零覆盖声明、
   时代假设（该字段是否 4.27→5.8 稳定，不稳定时给出门控条件）。
3. 时代负向断言（"旧版没有 X"）在本地只有 5.8 单树时必须标注证据等级：枚举序佐证 / CUE4Parse
   副本 / 知识性高置信——禁止把三者写成源码证明。
4. 每轮模块级审查保留 peer 覆盖矩阵一栏（哪个 peer 覆盖该布局、是否一致），审查产物落 `temp/`。
5. fixture 到位后 peer 声明降级为背景信息，验收以 fixture 断言为准。

## 4. external/ 清单（pin 提交，2026-09-02 核对）

| Peer | 语言/焦点 | 对本项目有用的覆盖域 |
|---|---|---|
| CUE4Parse | C# / 全引擎资产，游戏文件 | 资产类导出、Zen/IoStore、.usmap 兼容参考、版本枚举副本 |
| UAssetAPI | C# / loose 包 | 编辑器自保存包、StringTableExport、export 表细节 |
| UAssetGUI | C# UI | 委托 UAssetAPI，无独立解析 |
| uasset-rs | Rust | 经典包属性解析 |
| uasset-reader-js | JS | 经典包属性解析 |
| Unreal-Library | Python | UE3/UE4/UE5 宽版本扫描 |
| AssetToJson | 采集器 | 资产 JSON 字段对照 |
| UE4TextExtractor | 文本 | LocRes/文本历史类型（FText 旁证） |
| UnrealBPInspect | Blueprint | 蓝图字节码旁证 |

引入/升级新 peer 需在 `external/README.md`（待建）记录 pin commit、日期与再分发授权
（Lyra/ALS 属 Epic EULA 的 fixture 不得入仓库，先例 #619 备注）。

## 5. 边界

- peer 分歧时以 UE 源码为准；源码与 peer 持续冲突且 fixture 缺席 → 该功能维持 summary 级、
  声明降级，不做猜测性解码。
- 本方案只约束证据与注释，不改变 handler 分级（capability）、诊断或输出契约。
