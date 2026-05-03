# Domain Pitfalls

**Domain:** Python工具打包成Claude Code MCP Skill
**Researched:** 2026-05-02

## Critical Pitfalls

导致项目失败或重大重写的严重错误。

### Pitfall 1: stdio传输污染stdout

**What goes wrong:** 在MCP服务器中使用`print()`语句输出调试信息，污染了stdio传输通道，导致JSON-RPC消息损坏。

**Why it happens:**
- MCP使用stdio传输时，服务器通过stdout发送JSON-RPC消息
- 开发者习惯使用`print()`进行调试
- stdout被混用的调试信息污染后，Claude Code无法解析消息

**Consequences:**
- Claude Code无法与skill通信
- 错误消息难以理解（通常是JSON解析错误）
- 调试困难（因为不能使用print调试）

**Prevention:**
```python
# 错误 ❌
print(f"Debug: processing {filename}")

# 正确 ✓
import sys
print(f"Debug: processing {filename}", file=sys.stderr)

# 推荐 ✓
import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger(__name__)
logger.debug(f"Processing {filename}")
```

**Detection:**
- 在测试中使用MCP inspector工具验证
- 检查代码中所有`print()`调用
- 使用`grep -r "print(" --include="*.py"`扫描

**阶段建议:** Phase 15（skill封装）应在代码审查阶段专门检查此问题。

---

### Pitfall 2: 阻塞事件循环

**What goes wrong:** 在async工具处理器中调用同步阻塞代码（如文件I/O、CPU密集计算），阻塞整个事件循环，导致MCP服务器无响应。

**Why it happens:**
- MCP Python SDK要求工具处理器为async函数
- uasset_read.py使用同步I/O（`open()`, `struct.unpack()`）
- 大文件解析（mmap）可能耗时较长
- 开发者忘记将同步代码包装为异步

**Consequences:**
- MCP服务器冻结，无法处理其他请求
- Claude Code超时断开连接
- 用户体验极差（界面卡死）

**Prevention:**
```python
# 错误 ❌ - 直接调用同步解析
@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    result = parse_uasset(path)  # 阻塞！
    return result.asdict()

# 正确 ✓ - 使用线程池
import asyncio
from functools import partial

@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    # 在线程池中运行同步代码
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,  # 使用默认线程池
        partial(parse_uasset, path)
    )
    return result.asdict()

# 推荐 ✓ - 使用asyncio.to_thread（Python 3.9+）
@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    result = await asyncio.to_thread(parse_uasset, path)
    return result.asdict()
```

**Detection:**
- 性能测试：解析大型.uasset文件时监控响应时间
- 代码审查：检查async函数中的同步调用
- 使用`asyncio.all_tasks()`检查任务堆积

**阶段建议:** Phase 15应在集成测试中专门测试大文件解析性能。

---

### Pitfall 3: 类型提示缺失导致JSON Schema生成失败

**What goes wrong:** FastMCP/MCP工具参数缺少类型提示或类型提示错误，导致JSON Schema生成失败，工具无法注册。

**Why it happens:**
- FastMCP依赖类型提示生成JSON Schema
- Python允许无类型提示的函数，但MCP要求Schema
- 复杂类型（Union、Optional）处理不当
- docstring格式不规范

**Consequences:**
- 工具注册失败，Claude Code无法调用
- 运行时Schema验证错误
- 参数类型不匹配导致解析失败

**Prevention:**
```python
# 错误 ❌ - 缺少类型提示
@mcp.tool()
def parse_blueprint(path):  # 无类型提示
    """Parse blueprint."""
    return parse_uasset(path)

# 错误 ❌ - 复杂类型处理不当
@mcp.tool()
def parse_blueprint(path: str, options: dict) -> dict:  # dict太宽泛
    ...

# 正确 ✓ - 使用完整类型提示
from typing import Optional
from pydantic import BaseModel

class ParseOptions(BaseModel):
    extract_graphs: bool = True
    max_depth: int = 5

@mcp.tool()
async def parse_blueprint(
    path: str,
    options: Optional[ParseOptions] = None
) -> dict:
    """Parse Unreal Engine .uasset blueprint file.

    Args:
        path: Absolute path to .uasset file
        options: Parsing options (optional)

    Returns:
        Parsed blueprint data as dictionary
    """
    opts = options or ParseOptions()
    # ... 实现
```

**Detection:**
- 使用MCP inspector验证工具Schema
- 单元测试工具注册
- 类型检查器（mypy）验证

**阶段建议:** Phase 15开发期间使用mypy严格模式检查。

---

### Pitfall 4: 错误处理不兼容MCP协议

**What goes wrong:** 异常处理方式不符合MCP JSON-RPC 2.0规范，导致Claude Code收到无法理解的错误响应。

**Why it happens:**
- uasset_read.py有自己的异常体系（`UAssetError`, `ParseError`）
- MCP要求特定的JSON-RPC错误格式
- 开发者习惯raise Python异常，未转换为MCP错误
- 错误消息不够详细或过于详细

**Consequences:**
- Claude Code显示通用错误，用户无法定位问题
- 调试困难，错误信息丢失
- 可能导致Claude Code断开连接

**Prevention:**
```python
# 错误 ❌ - 直接抛出Python异常
@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    result = parse_uasset(path)  # 可能抛出UAssetError
    return result.asdict()  # 可能抛出AttributeError

# 正确 ✓ - 捕获并转换为结构化错误
from mcp import McpError

@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    try:
        result = parse_uasset(path)
        return {
            "success": True,
            "data": result.asdict()
        }
    except FileNotFoundError:
        raise McpError(
            code=-32602,  # Invalid params
            message=f"File not found: {path}"
        )
    except UAssetError as e:
        raise McpError(
            code=-32603,  # Internal error
            message=f"Failed to parse .uasset: {str(e)}",
            data={"error_type": type(e).__name__}
        )
    except Exception as e:
        # 捕获意外错误，记录日志
        logger.exception("Unexpected error parsing {path}")
        raise McpError(
            code=-32603,
            message="Internal server error"
        )

# 推荐 ✓ - 使用错误码和详细信息
class UAssetMcpError:
    """uasset_read专用错误码"""
    FILE_NOT_FOUND = -32001
    PARSE_ERROR = -32002
    VERSION_ERROR = -32003
    BOUNDARY_ERROR = -32004
```

**Detection:**
- 测试所有错误路径
- 使用MCP inspector验证错误格式
- 集成测试：故意触发错误检查响应

**阶段建议:** Phase 15需要编写错误处理专门测试用例。

---

### Pitfall 5: 零依赖特性被破坏

**What goes wrong:** 在MCP封装中引入不必要的依赖，破坏uasset_read.py的零依赖特性，增加安装复杂度和环境问题。

**Why it happens:**
- MCP Python SDK需要安装（`mcp`包）
- 开发者可能添加`pydantic`、`aiofiles`等便利库
- 虚拟环境配置不一致
- 依赖版本冲突

**Consequences:**
- 安装失败或依赖地狱
- 跨平台兼容性问题
- 用户抵触使用（安装门槛高）
- 与uasset_read.py原有零依赖目标冲突

**Prevention:**
```python
# 策略1：最小化MCP依赖
# pyproject.toml
[project]
dependencies = [
    "mcp>=0.9.0",  # 仅必需依赖
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "mypy>=1.0",
]

# 策略2：保持核心解析器零依赖
# uasset_read.py保持不变（仅标准库）
# uasset_mcp_server.py引入MCP（独立模块）

# 策略3：使用uv或pipx隔离安装
# Claude Code可以使用uvx直接运行
# uvx uasset-mcp-server
```

**Detection:**
- 检查`pyproject.toml`的dependencies列表
- 测试全新环境安装
- 使用`pipdeptree`检查依赖树

**阶段建议:** Phase 15应明确区分核心解析器和MCP封装层依赖。

---

### Pitfall 6: 大文件内存问题

**What goes wrong:** MCP工具未正确处理大文件解析，导致内存溢出或超时，特别是在处理大型蓝图资产时。

**Why it happens:**
- uasset_read.py使用mmap处理大文件（>50MB）
- MCP工具可能在内存中缓存整个结果
- JSON序列化大型ParseResult可能非常巨大
- 未设置合理的文件大小限制

**Consequences:**
- 内存溢出（OOM）
- Claude Code响应超时
- 用户体验差，系统变慢

**Prevention:**
```python
# 错误 ❌ - 无限制解析
@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    result = parse_uasset(path)  # 可能解析超大文件
    return result.asdict()  # 可能生成巨大JSON

# 正确 ✓ - 添加大小限制和流式处理
import os

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB限制
MAX_RESULT_SIZE = 10 * 1024 * 1024  # 10MB JSON限制

@mcp.tool()
async def parse_blueprint(
    path: str,
    summary_only: bool = False
) -> dict:
    # 检查文件大小
    file_size = os.path.getsize(path)
    if file_size > MAX_FILE_SIZE:
        raise McpError(
            code=-32004,
            message=f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})"
        )

    # 解析
    result = await asyncio.to_thread(parse_uasset, path)

    # 选择性输出
    if summary_only or file_size > LARGE_FILE_THRESHOLD:
        return result.to_summary_dict()  # 仅摘要
    else:
        return result.asdict()

# 推荐 ✓ - 提供选项控制输出粒度
@mcp.tool()
async def parse_blueprint(
    path: str,
    include_graphs: bool = True,
    include_properties: bool = True,
    max_depth: int = 5
) -> dict:
    """Parse .uasset with output control."""
    # ... 根据参数控制输出大小
```

**Detection:**
- 压力测试：解析超大.uasset文件
- 内存分析：使用`memory_profiler`
- 性能监控：响应时间和内存使用

**阶段建议:** Phase 15应进行大文件压力测试。

---

## Moderate Pitfalls

会导致性能问题或使用困难，但不会导致完全失败。

### Pitfall 7: 参数验证不足

**What goes wrong:** 工具参数未充分验证，导致运行时错误或安全漏洞。

**Prevention:**
```python
from pathlib import Path
import os

@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    # 验证路径
    if not path:
        raise McpError(code=-32602, message="Path is required")

    # 验证路径存在
    file_path = Path(path)
    if not file_path.exists():
        raise McpError(code=-32602, message=f"File not found: {path}")

    # 验证文件扩展名
    if file_path.suffix.lower() != '.uasset':
        raise McpError(code=-32602, message="File must be .uasset")

    # 验证可读性
    if not os.access(path, os.R_OK):
        raise McpError(code=-32602, message=f"File not readable: {path}")

    # 安全检查：避免路径遍历
    try:
        resolved = file_path.resolve()
        # 可选：限制访问特定目录
        # allowed_root = Path("/safe/directory")
        # if not resolved.is_relative_to(allowed_root):
        #     raise McpError(...)
    except (OSError, ValueError) as e:
        raise McpError(code=-32602, message=f"Invalid path: {path}")

    # ... 解析逻辑
```

**阶段建议:** Phase 15应在所有工具入口添加参数验证。

---

### Pitfall 8: JSON序列化问题

**What goes wrong:** ParseResult包含不可JSON序列化的类型（如bytes、datetime、自定义类），导致序列化失败。

**Why it happens:**
- uasset_read.py使用dataclass
- dataclass.asdict()通常可序列化
- 但某些字段可能包含bytes或其他不可序列化类型
- 默认JSON encoder不支持所有类型

**Prevention:**
```python
import json
from dataclasses import asdict
from typing import Any

class UAssetEncoder(json.JSONEncoder):
    """自定义JSON编码器处理特殊类型"""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, bytes):
            return obj.hex()  # 或 base64.b64encode(obj).decode()
        if hasattr(obj, 'asdict'):
            return obj.asdict()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    result = await asyncio.to_thread(parse_uasset, path)

    # 确保可序列化
    try:
        data = result.asdict()
        # 验证可序列化
        json.dumps(data, cls=UAssetEncoder)
        return data
    except (TypeError, ValueError) as e:
        logger.error(f"Serialization error: {e}")
        raise McpError(
            code=-32603,
            message="Failed to serialize result"
        )
```

**阶段建议:** Phase 15应在单元测试中验证所有类型的序列化。

---

### Pitfall 9: 配置管理不当

**What goes wrong:** API密钥、文件路径等配置硬编码或使用不当方式管理，导致安全和部署问题。

**Why it happens:**
- 开发时方便硬编码测试值
- 未使用环境变量
- 配置文件格式不规范
- Claude Code配置集成不当

**Prevention:**
```python
import os
from typing import Optional

# 错误 ❌ - 硬编码配置
ALLOWED_PATH = "/home/user/unreal_projects"

# 正确 ✓ - 环境变量 + 默认值
ALLOWED_PATHS = os.getenv(
    "UASSET_ALLOWED_PATHS",
    ""
).split(":") if os.getenv("UASSET_ALLOWED_PATHS") else None

MAX_FILE_SIZE = int(os.getenv("UASSET_MAX_FILE_SIZE", "524288000"))  # 500MB

# 推荐 ✓ - Pydantic配置类
from pydantic import BaseSettings

class Settings(BaseSettings):
    allowed_paths: list[str] = []
    max_file_size: int = 500 * 1024 * 1024
    debug: bool = False

    class Config:
        env_prefix = "UASSET_"

settings = Settings()

# Claude Code配置集成
# claude_desktop_config.json:
{
  "mcpServers": {
    "uasset-read": {
      "command": "uvx",
      "args": ["uasset-mcp-server"],
      "env": {
        "UASSET_ALLOWED_PATHS": "/path/to/unreal:/path/to/projects",
        "UASSET_MAX_FILE_SIZE": "524288000"
      }
    }
  }
}
```

**阶段建议:** Phase 15应文档化所有配置项和环境变量。

---

### Pitfall 10: 缺乏测试和调试支持

**What goes wrong:** MCP skill难以测试和调试，开发效率低，问题定位困难。

**Why it happens:**
- MCP依赖stdio，难以直接调试
- 未提供独立测试模式
- 缺少详细日志
- 未使用MCP inspector

**Prevention:**
```python
# 策略1：添加测试模式
import sys

if __name__ == "__main__":
    if "--test" in sys.argv:
        # 直接测试，不启动MCP服务器
        result = parse_uasset(sys.argv[sys.argv.index("--test") + 1])
        print(json.dumps(result.asdict(), indent=2))
    else:
        # 正常启动MCP服务器
        mcp.run()

# 策略2：详细日志
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr  # 重要：使用stderr
)

# 策略3：使用MCP inspector测试
# npx @anthropic-ai/mcp-inspector uasset-mcp-server

# 策略4：单元测试MCP工具
import pytest
from unittest.mock import patch

@pytest.mark.asyncio
async def test_parse_blueprint_tool():
    """测试MCP工具独立于服务器"""
    # 直接导入工具函数测试
    from uasset_mcp_server import parse_blueprint

    result = await parse_blueprint("test.uasset")
    assert result["success"]
    assert "data" in result
```

**阶段建议:** Phase 15应建立MCP测试基础设施。

---

### Pitfall 11: 文档不足或误导

**What goes wrong:** 工具文档（docstring）不清晰或不准确，导致Claude Code误用或无法理解工具功能。

**Why it happens:**
- docstring过于简短
- 未说明参数约束
- 未提供使用示例
- 未说明返回格式

**Prevention:**
```python
@mcp.tool()
async def parse_blueprint(
    path: str,
    include_graphs: bool = True,
    include_properties: bool = True,
    max_depth: int = 5
) -> dict:
    """Parse Unreal Engine .uasset blueprint file and extract metadata.

    This tool parses .uasset files to extract blueprint information including
    class hierarchy, variables, functions, and optionally the full graph structure.

    Args:
        path: Absolute path to the .uasset file. Must be an existing,
              readable .uasset file (not cooked).
        include_graphs: Whether to extract blueprint graph nodes and pins.
                       Set to False for faster parsing of metadata only.
                       Default: True
        include_properties: Whether to parse detailed property values.
                           Set to False for faster parsing.
                           Default: True
        max_depth: Maximum recursion depth for nested property parsing.
                  Range: 1-10. Default: 5

    Returns:
        A dictionary containing:
        - success: bool - Whether parsing succeeded
        - data: dict - Parsed blueprint data (if success)
        - error: str - Error message (if failed)

        The data dictionary includes:
        - name_map: List of names referenced in the file
        - imports: List of imported packages
        - exports: List of exported objects
        - blueprint: Blueprint metadata (parent class, variables)
        - graphs: Graph structure (if include_graphs=True)

    Raises:
        McpError: If file not found, invalid format, or parsing fails

    Example:
        # Parse full blueprint with graphs
        result = await parse_blueprint("/path/to/BP_Character.uasset")

        # Fast metadata-only parse
        result = await parse_blueprint(
            "/path/to/BP_Character.uasset",
            include_graphs=False,
            include_properties=False
        )
    """
    # ... 实现
```

**阶段建议:** Phase 15应为每个MCP工具编写详细docstring。

---

## Minor Pitfalls

会导致不便，但易于修复。

### Pitfall 12: 未提供工具列表或使用指南

**What goes wrong:** MCP服务器未提供清晰的工具列表和使用指南，用户不知道有哪些功能。

**Prevention:**
```python
# MCP自动从装饰器提取工具信息
# 但应提供README或文档

# README.md示例
"""
# uasset-read MCP Server

MCP server for parsing Unreal Engine .uasset files.

## Available Tools

### parse_blueprint
Parse .uasset blueprint file and extract metadata.

**Parameters:**
- `path` (required): Absolute path to .uasset file
- `include_graphs` (optional): Extract graph structure (default: true)
- `include_properties` (optional): Parse property values (default: true)
- `max_depth` (optional): Recursion depth limit (default: 5)

**Returns:** Parsed blueprint data as JSON

## Installation

```bash
pip install uasset-mcp-server
```

## Usage with Claude Code

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "uasset-read": {
      "command": "uvx",
      "args": ["uasset-mcp-server"]
    }
  }
}
```
"""
```

---

### Pitfall 13: 版本管理和更新不当

**What goes wrong:** 未正确管理MCP服务器版本，导致兼容性问题或功能漂移。

**Prevention:**
```python
# pyproject.toml
[project]
name = "uasset-mcp-server"
version = "1.0.0"
description = "MCP server for parsing Unreal Engine .uasset files"
requires-python = ">=3.10"

[project.dependencies]
mcp = ">=0.9.0,<1.0.0"

# 工具中报告版本
@mcp.tool()
async def get_version() -> dict:
    """Get MCP server version information."""
    return {
        "version": "1.0.0",
        "uasset_read_version": "2.0.0",
        "mcp_sdk_version": "0.9.0"
    }
```

---

### Pitfall 14: 未处理并发请求

**What goes wrong:** MCP服务器可能同时收到多个请求，未正确处理并发导致竞态条件或资源冲突。

**Prevention:**
```python
# FastMCP自动处理并发
# 但需确保共享状态安全

# 错误 ❌ - 全局可变状态
cache = {}

@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    cache[path] = result  # 竞态条件！
    return result

# 正确 ✓ - 无状态或线程安全
from threading import Lock

cache_lock = Lock()
cache = {}

@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    result = await asyncio.to_thread(parse_uasset, path)

    with cache_lock:
        cache[path] = result

    return result

# 推荐 ✓ - 完全无状态（最佳）
@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    # 每次调用独立，无共享状态
    result = await asyncio.to_thread(parse_uasset, path)
    return result.asdict()
```

---

### Pitfall 15: 日志配置不当

**What goes wrong:** 日志配置不正确，导致调试信息丢失或污染stdout。

**Prevention:**
```python
import logging
import sys

# 配置日志到stderr（绝不使用stdout）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr,  # 重要：使用stderr
    handlers=[
        logging.StreamHandler(stream=sys.stderr)
    ]
)

logger = logging.getLogger("uasset_mcp")

# 提供日志级别控制
LOG_LEVEL = os.getenv("UASSET_LOG_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
```

---

## Phase-Specific Warnings

针对v3.0里程碑各阶段的特定陷阱警告。

| 阶段 | 可能陷阱 | 缓解策略 |
|------|---------|---------|
| Phase 11: ExportMap属性值提取 | JSON序列化问题（复杂属性类型） | 扩展UAssetEncoder支持所有属性类型 |
| Phase 12: BlueprintVariables提取 | 输出数据结构过大 | 提供摘要模式，分页输出 |
| Phase 13: 组件变换属性解析 | 数值精度问题（浮点数） | 使用float精度控制，舍入策略 |
| Phase 14: 输出格式优化 | 格式变更破坏兼容性 | 版本化输出格式，保持向后兼容 |
| Phase 15: Claude Code skill封装 | 所有Critical Pitfalls (1-6) | 逐个检查和测试 |

---

## uasset_read特定陷阱

针对本项目特性的陷阱。

### Pitfall U1: ParseResult序列化兼容性

**What goes wrong:** ParseResult的某些字段可能包含不可序列化数据。

**Prevention:**
- 在Phase 15前审计ParseResult所有字段类型
- 为bytes、自定义类型添加序列化器
- 单元测试验证所有字段序列化

### Pitfall U2: 版本依赖冲突

**What goes wrong:** uasset_read.py支持的UE版本范围可能与MCP用户资产版本不匹配。

**Prevention:**
- 在工具文档中明确支持的UE版本
- 提供版本检查工具
- 优雅处理版本不兼容错误

### Pitfall U3: mmap文件句柄泄漏

**What goes wrong:** 使用mmap后未正确关闭文件句柄，导致资源泄漏。

**Prevention:**
```python
# uasset_read.py应使用context manager
with mmap.mmap(...) as mm:
    # 使用mm
    pass  # 自动关闭

# MCP工具应确保清理
@mcp.tool()
async def parse_blueprint(path: str) -> dict:
    try:
        result = await asyncio.to_thread(parse_uasset, path)
        return result.asdict()
    finally:
        # 确保资源清理
        pass  # parse_uasset内部应处理清理
```

---

## 预防策略总结

### 开发阶段

1. **类型提示强制**: 使用mypy strict模式，所有函数必须有类型提示
2. **文档先行**: 编写详细docstring，说明参数、返回值、错误
3. **错误处理规范**: 统一使用McpError，定义错误码常量
4. **日志到stderr**: 所有日志输出到stderr，绝不使用stdout

### 测试阶段

1. **单元测试**: 每个MCP工具独立测试，不依赖服务器
2. **集成测试**: 使用MCP inspector验证完整流程
3. **压力测试**: 测试大文件、并发请求、错误路径
4. **序列化验证**: 验证所有返回数据可JSON序列化

### 部署阶段

1. **依赖最小化**: 仅必需依赖，核心解析器保持零依赖
2. **配置文档化**: 文档化所有环境变量和配置项
3. **版本管理**: 语义化版本，提供版本查询工具
4. **安装简便**: 支持uvx/pipx一键安装

### 运行阶段

1. **监控日志**: 记录关键操作和错误
2. **资源限制**: 文件大小、超时时间、内存限制
3. **优雅降级**: 大文件提供摘要模式，错误提供清晰提示

---

## Sources

### 官方文档

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/) — MCP协议规范和Python SDK指南 (HIGH confidence)
- [Claude Code Documentation](https://docs.anthropic.com/claude/docs/claude-code) — Claude Code skill集成指南 (HIGH confidence)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — 官方Python SDK仓库 (HIGH confidence)
- [FastMCP](https://github.com/jlowin/fastmcp) — 简化MCP开发的高级库 (HIGH confidence)

### 技术文章

- [Python Asyncio Best Practices](https://docs.python.org/3/library/asyncio.html) — 异步编程最佳实践 (HIGH confidence)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification) — JSON-RPC错误码规范 (HIGH confidence)
- [Python Packaging Guide](https://packaging.python.org/en/latest/) — Python打包和分发指南 (HIGH confidence)

### 社区资源

- [MCP GitHub Issues](https://github.com/modelcontextprotocol/python-sdk/issues) — 常见问题和解决方案 (MEDIUM confidence)
- [Claude Code MCP Examples](https://github.com/anthropics/anthropic-cookbook/tree/main/misc/mcp) — 官方示例 (MEDIUM confidence)

---

**Confidence:** HIGH

基于官方文档、MCP Python SDK源码、FastMCP库文档、社区issue讨论、以及Python异步编程最佳实践的综合研究。所有关键陷阱均有官方文档或社区issue支持，预防策略基于实际代码示例。

**Last Updated:** 2026-05-02