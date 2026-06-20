# Task 4 Report: Remove SoundAttenuation and AnimationDataModel from skip lists

## Status: DONE

## Summary
从 `SKIP_CLASS_PREFIXES` 和 `SKIP_CLASS_NAMES` 中移除了 `AnimationDataModel` 和 `SoundAttenuation`，使它们不再被 tolerant parsing 跳过。

## Files Modified

| File | Change |
|---|---|
| `src/uasset_read/parsers/class_specific_skip.py` | 注释掉 `AnimationDataModel`（SKIP_CLASS_PREFIXES）和 `SoundAttenuation`（SKIP_CLASS_NAMES） |
| `tests/test_sound_attenuation.py` | 新增 `test_sound_attenuation_not_skipped` 测试 |
| `tests/test_anim_data_model.py` | 新增 `test_anim_data_model_not_skipped` 测试 |

## Test Results

```
tests/test_sound_attenuation.py::test_parse_sound_attenuation_returns_dict PASSED
tests/test_sound_attenuation.py::test_sound_attenuation_not_skipped PASSED
tests/test_anim_data_model.py::test_parse_anim_data_model_returns_dict PASSED
tests/test_anim_data_model.py::test_anim_data_model_handler_registered PASSED
tests/test_anim_data_model.py::test_anim_data_model_not_skipped PASSED

5 passed in 0.46s
```

## Commit

`e1d4218` — `fix: 从 skip 列表移除 SoundAttenuation 和 AnimationDataModel（#166）`

## Concerns

无。两个 class 在 Tasks 1-3 中已注册到 opaque 白名单（class registry handler），移除 skip 列表后 `should_skip_export_for_tolerant_parsing` 会先检查 registry handler 的 fallback_policy，再检查 skip list 作为 fallback。逻辑顺序不受影响。
