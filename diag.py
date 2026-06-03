#!/usr/bin/env python
"""快捷诊断入口：python diag.py <path.uasset> [--format FORMAT]"""
import sys
from uasset_read.core import parse_single

if len(sys.argv) < 2:
    print("用法: python diag.py <path.uasset> [--format FORMAT]")
    sys.exit(1)

path = sys.argv[1]
fmt = "text"
if len(sys.argv) >= 4 and sys.argv[2] == "--format":
    fmt = sys.argv[3]

try:
    print(parse_single(path, format=fmt))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)