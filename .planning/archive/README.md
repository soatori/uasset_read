# Archive

已完成的里程碑归档在此。完整历史文件可通过 git 恢复。

## 结构

```
archive/
├── README.md
├── v1-v7-SUMMARY.md      # v1.0–v7.0 压缩摘要（原 541 文件）
├── v8.0/                  # BP-to-CPP JSON 可翻译性 (P47-51)
│   ├── v8.0-MILESTONE.md
│   ├── v8.0-ROADMAP.md
│   ├── v8.0-REQUIREMENTS.md
│   └── phases/            # 47, 49, 50, 51
├── v9.0/                  # 函数调用链解析 (P52-55)
│   ├── v9.0-MILESTONE.md
│   ├── v9.0-ROADMAP.md
│   ├── v9.0-REQUIREMENTS.md
│   └── phases/            # 52, 53, 54, 55
└── v10.0/                 # Blueprint-to-C++ 代码生成参考 (P56-60)
    ├── v10.0-MILESTONE.md
    └── phases/            # 56, 57, 58, 59, 60
```

## 恢复历史文件

```bash
# 查看某个 phase 的完整历史
git log --all -- .planning/archive/v8.0/phases/47-pin-linkedto-fix/

# 恢复已删除的 archive 目录
git checkout <commit> -- .planning/archive/v6.0-refactor/
```

---

*Archived: 2026-05-18 — v10.0 发布后深度清理*
