# uasset_read

`uasset_read` is a read-only Python parser for Unreal Engine `.uasset` and `.umap` packages. It reads asset metadata, Blueprint graphs, and Kismet bytecode offline, without launching the Unreal Editor.

- Inspect exports, dependencies, properties, and supported asset types.
- Read Blueprint nodes, pins, connections, declarations, and Kismet instructions with their control-flow graphs.
- Use the structured output as a reference for manual or agent-assisted translation of Blueprint logic to C++.

## Installation

**Requirements:** Python 3.10 or newer and Git for cloning. The default installation has no runtime dependencies. The distribution name is `uasset-read` and the Python import name is `uasset_read`.

Clone the repository:

```sh
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
```

Create and activate a virtual environment.

**Windows PowerShell**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux or macOS**

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Install the package from the checkout and verify the CLI:

```sh
python -m pip install .
python -m uasset_read --version
```

For development, use `python -m pip install -e ".[test]"`. If your `.usmap` file uses Brotli or Zstandard compression, install the optional dependencies with `python -m pip install ".[compression]"`.

## Quick start

### Command line

Run these commands from the checkout to try a tracked sample. For your own asset, replace the sample path with the path to your `.uasset` or `.umap`.

```sh
python -m uasset_read tests/samples/Helm_BP.uasset -o helm.json
python -m uasset_read tests/samples/Helm_BP.uasset --debug -o helm-debug.json
python -m uasset_read --help
```

Omit `-o` to write JSON to stdout. Use `--mappings path/to/types.usmap` when a package needs an external property map.

### Python

```python
from uasset_read import parse_package_document, project_document

document = parse_package_document("tests/samples/Helm_BP.uasset")
package = project_document(document)

print(package["format_version"])  # 4.0
print(len(package["objects"]))    # 47
```

## Output and support

The CLI and Python API produce one v4 JSON document per package, with all exports addressable under `objects`. Normal mode includes decoded values, static analysis, and diagnostics. Debug mode adds evidence such as source ranges and byte accounting.

Blueprint graph coverage is strongest for loose, editor-saved packages. Cooked files can lack graph data, and decoding unversioned properties can require a matching `.usmap`. Zen/IoStore package-body decoding and automatic C++ generation are outside the supported scope.

See the [Wiki](https://github.com/soatori/uasset_read/wiki) for the full CLI and Python API references, format coverage, and Agent examples. See [Releases](https://github.com/soatori/uasset_read/releases) for version history and [Issues](https://github.com/soatori/uasset_read/issues) to report a problem.
