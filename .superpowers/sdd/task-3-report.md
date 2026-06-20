# Task 3: Register new handlers in AssetTypeHandler

## Status
DONE

## Summary
注册 AnimDataModel handler 到可选解析器列表，并清理 `__all__` 中的冗余导出。

## Files Modified
- `src/uasset_read/parsers/asset_types/__init__.py` — 添加 AnimDataModel 到 `_optional` 列表，移除 `parse_sound_attenuation` 从 `__all__`
- `tests/test_anim_data_model.py` — 新增 handler 注册验证测试

## Changes
1. **`__all__` 清理**：移除 `"parse_sound_attenuation"` — 可选解析器无需在 `__all__` 中导出（与 texture_cube、anim_sequence、sound_wave 保持一致）
2. **AnimDataModel 注册**：在 `_optional` 列表末尾添加条目 `("anim_data_model", "parse_anim_data_model", ["AnimationDataModel"], "AnimDataModelHandler")`
3. **测试补充**：新增 `test_anim_data_model_handler_registered()` 验证 handler 可通过 `registry.find_handler("AnimationDataModel")` 查找到，且 `handler_name == "AnimDataModelHandler"`

## Test Results
```
tests/test_sound_attenuation.py::test_parse_sound_attenuation_returns_dict PASSED
tests/test_anim_data_model.py::test_parse_anim_data_model_returns_dict PASSED
tests/test_anim_data_model.py::test_anim_data_model_handler_registered PASSED
3 passed in 0.57s
```

## Concerns
无。
