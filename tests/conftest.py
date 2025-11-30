"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def schemas_dir(project_root: Path) -> Path:
    """Return the schemas directory."""
    return project_root / "src" / "schemas"
