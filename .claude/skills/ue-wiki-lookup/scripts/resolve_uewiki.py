#!/usr/bin/env python3
"""发现本地/远程 ue_wiki 配置，输出 JSON 格式的路径和命令信息。

用法: python resolve_uewiki.py [--config <path>]
输出: JSON 格式的配置信息
"""

import json
import os
import sys
from pathlib import Path


def find_uewiki_root():
    """按优先级搜索 uewiki 项目根目录。"""
    candidates = []

    # 1. 环境变量
    env_root = os.environ.get("UEWIKI_ROOT")
    if env_root:
        candidates.append(Path(env_root))

    # 2. 当前项目 .claude/uewiki.config.json 中的路径
    project_config = Path.cwd() / ".claude" / "uewiki.config.json"
    if project_config.exists():
        try:
            with open(project_config, encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("uewiki_root"):
                candidates.append(Path(cfg["uewiki_root"]))
        except (json.JSONDecodeError, OSError):
            pass

    # 3. 用户全局配置
    global_config = Path.home() / ".claude" / "uewiki.config.json"
    if global_config.exists():
        try:
            with open(global_config, encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("uewiki_root"):
                candidates.append(Path(cfg["uewiki_root"]))
        except (json.JSONDecodeError, OSError):
            pass

    # 4. 常见位置
    candidates.append(Path("E:/Develop/ue_wiki"))
    candidates.append(Path.home() / "ue_wiki")

    for candidate in candidates:
        if candidate.exists() and (candidate / "wiki").is_dir():
            return str(candidate.resolve())

    return None


def load_config(uewiki_root, explicit_config=None):
    """加载 uewiki 配置。"""
    config_paths = []

    if explicit_config:
        config_paths.append(Path(explicit_config))

    if uewiki_root:
        config_paths.append(Path(uewiki_root) / "uewiki.config.local.json")
        config_paths.append(Path(uewiki_root) / "uewiki.config.example.json")

    for p in config_paths:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

    return {}


def resolve(explicit_config=None):
    """解析配置并输出 JSON。"""
    uewiki_root = find_uewiki_root()

    if not uewiki_root:
        return {
            "mode": "not_found",
            "error": "未找到 ue_wiki 项目。请设置 UEWIKI_ROOT 环境变量或在 .claude/uewiki.config.json 中配置 uewiki_root。",
            "remote": os.environ.get("UEWIKI_REMOTE", "https://github.com/<owner>/ue_wiki.git"),
        }

    config = load_config(uewiki_root, explicit_config)

    # 推断路径
    wiki_root = config.get("wiki_root") or str(Path(uewiki_root) / "wiki")
    ue_source_root = config.get("ue_source_root")
    codegraph_project_path = config.get("codegraph_project_path")

    # CLI 命令路径
    uewiki_cli = str(Path(uewiki_root) / "tools" / "uewiki" / "uewiki.py")

    return {
        "mode": "local",
        "uewiki_root": uewiki_root,
        "wiki_root": wiki_root,
        "ue_source_root": ue_source_root,
        "codegraph_project_path": codegraph_project_path,
        "codegraph_projects": config.get("codegraph_projects", {
            "default": codegraph_project_path,
        }),
        "codegraph_project_rules": config.get("codegraph_project_rules", {}),
        "ue_version": config.get("ue_version", "5.7"),
        "pack_command": ["python", "-m", "tools.uewiki.uewiki", "pack"],
        "query_command": ["python", "-m", "tools.uewiki.uewiki", "query"],
        "validate_command": ["python", "-m", "tools.uewiki.uewiki", "validate"],
        "index_command": ["python", "-m", "tools.uewiki.uewiki", "index"],
        "codegraph_policy": {
            "max_calls": 3,
            "default_level": "safe",
            "allow_expensive": False,
            "levels": {
                "L0": "不用 CodeGraph（架构解释、模块说明）",
                "L1": "codegraph_search, codegraph_node(includeCode=false)",
                "L2": "codegraph_callers(limit<=20), codegraph_callees(limit<=20)",
                "L3": "codegraph_context, codegraph_trace, codegraph_impact（默认禁用）",
            },
        },
    }


def main():
    explicit_config = None
    if len(sys.argv) > 2 and sys.argv[1] == "--config":
        explicit_config = sys.argv[2]

    result = resolve(explicit_config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
