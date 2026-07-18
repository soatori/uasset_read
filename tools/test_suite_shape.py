from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
MAX_TEST_FILES = 100
MAX_CORE_BENCHMARK_FILES = 10
CORE_BENCHMARK_DIR = TESTS / "integration"


def test_files() -> list[Path]:
    return sorted(TESTS.rglob("test_*.py"))


def core_benchmark_files() -> list[Path]:
    return sorted(CORE_BENCHMARK_DIR.glob("test_*.py"))


def main() -> int:
    files = test_files()
    benchmark_files = core_benchmark_files()
    print(f"test_files={len(files)} max={MAX_TEST_FILES}")
    print(f"core_benchmark_files={len(benchmark_files)} max={MAX_CORE_BENCHMARK_FILES}")
    if len(files) > MAX_TEST_FILES:
        return 1
    if len(benchmark_files) > MAX_CORE_BENCHMARK_FILES:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
