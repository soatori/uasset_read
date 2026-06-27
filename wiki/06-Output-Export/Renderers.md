---
title: Renderer System
section: renderers
---

# Renderer System

Renderers are a new output system introduced in 0.4.1, replacing the previous Exporter architecture. Renderers receive `PackageIR` (Intermediate Representation) without directly accessing `ParseResult`, achieving complete decoupling between parsing and output.

## Architecture Overview

```
ParseResult → build_package_ir() → PackageIR → Renderer → Output String
                                          ↓
                                  RENDERER_REGISTRY
                                  ├── json
                                  └── markdown
```

## Core Classes

<!-- data-api="IRenderer" -->
```python
class IRenderer(ABC):
    @abstractmethod
    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        """Render PackageIR to a string."""
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        """The format name handled by this renderer."""
        ...
```

<!-- data-api="RenderOptions" -->
```python
@dataclass
class RenderOptions:
    verbose: bool = False
    include_schema: bool = False
    include_function_graphs: bool = False
    linker_result: LinkerParseResult | None = None
```

<!-- data-api="RENDERER_REGISTRY" -->
```python
RENDERER_REGISTRY: dict[str, type[IRenderer]] = {}

def register_renderer(format_name: str, renderer_class: type[IRenderer]) -> None:
    """Register a renderer."""

def get_renderer(format_name: str) -> IRenderer:
    """Get a renderer instance."""

def list_formats() -> list[str]:
    """Return all registered format names."""
```

## Registered Renderers

| Format Name | Renderer Class | File | Description |
|-------------|----------------|------|-------------|
| `json` | `JSONRenderer` | `json_renderer.py` | Structured JSON output (C++ translation reference) |
| `markdown` | `MarkdownRenderer` | `markdown_renderer.py` | Markdown + Mermaid documentation |

## Usage

### Via Core API (Recommended)

```python
from uasset_read import parse_single, list_formats

# Render directly as JSON
output = parse_single("MyBlueprint.uasset", format="json")

# View all available formats
print(list_formats())
```

### Direct Renderer Usage

```python
from uasset_read.renderers import get_renderer, list_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.ir_builder import build_package_ir
from uasset_read import parse_uasset

# Parse
result = parse_uasset("MyBlueprint.uasset")

# Build IR
ir = build_package_ir(result)

# Get renderer and render
renderer = get_renderer("markdown")
options = RenderOptions(verbose=True, include_schema=False)
output = renderer.render(ir, options)
```

## Auto-Registration Mechanism

Renderers are automatically registered upon module import:

```python
# src/uasset_read/renderers/__init__.py
from . import json_renderer        # Auto-registers "json"
from . import markdown_renderer    # Auto-registers "markdown"
```

## File Locations

| File | Path |
|------|------|
| Module root | `src/uasset_read/renderers/` |
| Base class | `renderers/base.py` |
| JSON renderer | `renderers/json_renderer.py` |
| Markdown renderer | `renderers/markdown_renderer.py` |

**Related sections**: [[IR Intermediate Representation]] · [[CLI Interface]]
