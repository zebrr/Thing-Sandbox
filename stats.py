#!/usr/bin/env python3
"""Project statistics collector for Thing' Sandbox."""

import re
import subprocess
from pathlib import Path


def count_lines(file_path: Path) -> int:
    """Count non-empty lines in a file."""
    try:
        return len(file_path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return 0


def collect_stats(base: Path, pattern: str) -> tuple[int, int, float]:
    """Collect file count, line count, and size in KB for a glob pattern."""
    files = [f for f in base.glob(pattern) if f.is_file()]
    total_lines = sum(count_lines(f) for f in files)
    total_size_kb = sum(f.stat().st_size for f in files) / 1024
    return len(files), total_lines, total_size_kb


def count_tests(path: str) -> int:
    """Count pytest tests using --collect-only."""
    result = subprocess.run(
        ["python", "-m", "pytest", path, "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
    )
    # Parse "N tests collected" from output
    match = re.search(r"(\d+) tests? collected", result.stdout)
    return int(match.group(1)) if match else 0


def main() -> None:
    """Collect and print project statistics."""
    root = Path(__file__).parent

    categories: dict[str, list[tuple[str, str, str]]] = {
        "CODE (src/)": [
            ("Core", "src/*.py", "src/*.py"),
            ("Phases", "src/phases/*.py", "src/phases/*.py"),
            ("Utils", "src/utils/*.py + adapters", "src/utils/*.py"),
            ("Adapters", "(included above)", "src/utils/llm_adapters/*.py"),
        ],
        "TESTS (tests/)": [
            ("Unit", "tests/unit/*.py", "tests/unit/*.py"),
            ("Integration", "tests/integration/*.py", "tests/integration/*.py"),
            ("Shared", "tests/conftest.py", "tests/conftest.py"),
        ],
        "DOCUMENTATION (docs/)": [
            ("Project", "docs/*.md", "docs/*.md"),
            ("Specs", "docs/specs/*.md", "docs/specs/*.md"),
            ("Tasks", "docs/tasks/*.md", "docs/tasks/*.md"),
        ],
        "PROMPTS (src/prompts/)": [
            ("Templates", "src/prompts/*.md", "src/prompts/*.md"),
        ],
    }

    print("=" * 60)
    print("THING' SANDBOX PROJECT STATISTICS")
    print("=" * 60)

    grand_files = 0
    grand_lines = 0
    grand_size = 0.0

    for category, items in categories.items():
        print(f"\n{category}")
        print("-" * 55)

        cat_files = 0
        cat_lines = 0
        cat_size = 0.0

        for name, display, pattern in items:
            files, lines, size_kb = collect_stats(root, pattern)
            cat_files += files
            cat_lines += lines
            cat_size += size_kb
            print(f"  {name:15} {files:4} files  {lines:6} lines  {size_kb:7.1f} KB")

        print(f"  {'SUBTOTAL':15} {cat_files:4} files  {cat_lines:6} lines  {cat_size:7.1f} KB")
        grand_files += cat_files
        grand_lines += cat_lines
        grand_size += cat_size

    # Test counts
    print("\nTEST CASES (pytest)")
    print("-" * 40)
    unit_tests = count_tests("tests/unit/")
    integration_tests = count_tests("tests/integration/")
    total_tests = unit_tests + integration_tests
    print(f"  {'Unit':15} {unit_tests:4} tests")
    print(f"  {'Integration':15} {integration_tests:4} tests")
    print(f"  {'TOTAL':15} {total_tests:4} tests")

    print("\n" + "=" * 60)
    print(
        f"GRAND TOTAL: {grand_files} files, {grand_lines} lines, "
        f"{grand_size:.1f} KB, {total_tests} tests"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
