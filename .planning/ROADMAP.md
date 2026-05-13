### Phase 35b: Pin 连接深度调试与修复
**目标**: 深入调试修复 pin linked_to_raw 为空的根因，恢复 execution_flows 和 data_flows
**依赖**: Phase 35
**成功标准**: linked_to_raw 非空 + execution_flows/data_flows 完整构建 + Phase 22 历史测试通过
**计划**: 35b-01 read_bool UE5 修复 → 35b-02 BitField 修复 → 35b-03 FText 修复 → 35b-04 二进制诊断工具 → 35b-05 集成测试
**Plans:** 5 plans

Plans:
- [ ] 35b-01-PLAN.md — read_bool_ue5() + PinType bool reads (1 byte for UE5)
- [ ] 35b-02-PLAN.md — BitField read u32 for UE5 (was incorrectly u8)
- [ ] 35b-03-PLAN.md — FText b_has_culture 1-byte bool for UE5
- [ ] 35b-04-PLAN.md — Binary trace diagnostic tool for field position verification
- [ ] 35b-05-PLAN.md — Integration tests: linked_to_raw, execution_flows, data_flows

### Phase 35c: 代码审查安全性与健壮性修复
**目标**: 修复代码审查发现的 8 个输入验证与资源管理问题（CR-01/02/04/05/16/17 + HIGH-01/03/07）
**依赖**: Phase 35b
**成功标准**: FString OOM 防护 + 文件描述符安全 + 负数计数验证 + is_success 标志正确 + 边界验证全覆盖
**计划**: 35c-01 FD 泄漏 → 35c-02 FString OOM → 35c-03a 计数验证 → 35c-03b 偏移验证 → 35c-03c object_resources → 35c-04 is_success+tolerant → 35c-05 CLI 安全 → 35c-06 属性计数验证
**Plans:** 8 plans

Plans:
- [x] 35c-01-PLAN.md — archive.py 文件描述符泄漏修复
- [ ] 35c-02-PLAN.md — archive.py + constants.py FString 长度验证（OOM 防护）
- [x] 35c-03a-PLAN.md — package_summary.py 计数验证（11 个字段）
- [ ] 35c-03b-PLAN.md — package_summary.py 偏移验证（14 个字段）
- [x] 35c-03c-PLAN.md — object_resources.py 计数与偏移验证
- [x] 35c-04-PLAN.md — parse_uasset.py is_success 标志 + 临时存档 tolerant 模式修复
- [x] 35c-05-PLAN.md — cli.py 文件类型检查 + 异常捕获
- [x] 35c-06-PLAN.md — property_types.py 属性条目计数验证

### Phase 35d: 代码审查逻辑与质量修复
**目标**: 修复全量代码审查发现的属性解析 bug、蓝图提取 bug、输出格式问题
**依赖**: Phase 35b
**成功标准**: 属性解析正确性修复 + 蓝图变量提取修复 + JSON/Markdown 输出修复 + 全部测试通过
**计划**: 35d-01 属性解析器 → 35d-02 变量提取+模型 → 35d-03 模型默认值 → 35d-04 格式化+变换 → 35d-05 流构建 → 35d-06 代码清理
**Plans:** 6 plans

Plans:
- [x] 35d-01-PLAN.md — property_types.py 数组大小/Map类型提取/条目计数验证 (CR-09, MED-01, 35c-06)
- [x] 35d-02-PLAN.md — variable_extractor.py 标志映射 + blueprint.py 去重 (CR-11, LOW-04)
- [x] 35d-03-PLAN.md — models/properties.py 模型字段默认值 (CR-13)
- [x] 35d-04-PLAN.md — json_formatter.py 递归序列化 + markdown 转义 + transform KeyError (CR-14/15, HIGH-17, HIGH-09)
- [x] 35d-05-PLAN.md — flow_builder.py 安全迭代 + node_guid 检查 (LOW-06/07)
- [x] 35d-06-PLAN.md — 重复常量/死代码/重复函数清理 (MED-14, HIGH-08)
  
### Phase 35e: Pin Offset 根因诊断与 UE5 C++ 参考验证  
**目标**: 通过 UE5 C++ 源码参考和二进制跟踪工具，精确定位并修复 UE5 pin 序列化的 4 字节偏移问题，使 linked_to_raw 正确读取  
**依赖**: Phase 35b (阻塞)  
**成功标准**: linked_to_raw 非空 + 4 字节偏移修复 + 集成测试全部通过  
**计划**: 35e-01 UE5 C++ 参考 → 35e-02 二进制跟踪 → 35e-03 Direction/FName 修复 → 35e-04 集成测试  
**Plans:** 4 plans  
  
Plans:  
- [ ] 35e-01-PLAN.md - UE5 EdGraphPin.cpp L1838-1964 字段边界分析  
- [ ] 35e-02-PLAN.md - 二进制跟踪工具增强与 pin body 精确映射  
- [ ] 35e-03-PLAN.md - Direction/FName 4 字节偏移修复（graph.py）  
- [ ] 35e-04-PLAN.md - 集成测试验证：linked_to_raw, execution_flows, data_flows 
