from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Ensure every test runs with its own isolated database instance to prevent test cross-contamination."""
    test_db_path = tmp_path / "test_aegis.db"
    monkeypatch.setenv("AEGIS_DB_PATH", str(test_db_path))
    yield test_db_path
