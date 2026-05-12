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
