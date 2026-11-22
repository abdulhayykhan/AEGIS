import re
from pathlib import Path

REQUIRED_TABLES = [
    "instruments",
    "bars",
    "news_items",
    "runs",
    "signals",
    "proposals",
    "gate_decisions",
    "orders",
    "fills",
    "positions",
    "equity_snapshots",
    "approvals",
    "reconciliations",
    "incidents"
]


def test_migration_001_contains_all_prd_tables():
    """Verify that migration 001 defines all 14 required tables from PRD Section 8."""
    migration_file = Path("src/migrations/001_initial_schema.sql")
    assert migration_file.exists(), "Migration 001 must exist"
    
    content = migration_file.read_text(encoding="utf-8")
    
    # Check for CREATE TABLE statements
    created_tables = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", content, re.IGNORECASE)
    created_tables_set = {t.lower() for t in created_tables}

    
    for table in REQUIRED_TABLES:
        assert table in created_tables_set, f"Required table '{table}' missing in migration 001"


def test_migration_stores_money_as_numeric_never_float():
    """Verify that all monetary/price/size fields use NUMERIC, never REAL or FLOAT."""
    migration_file = Path("src/migrations/001_initial_schema.sql")
    content = migration_file.read_text(encoding="utf-8")
    
    # Find any FLOAT or REAL data types
    float_matches = re.findall(r"\b(FLOAT|REAL|DOUBLE\s+PRECISION)\b", content, re.IGNORECASE)
    assert len(float_matches) == 0, f"Found forbidden floating point types in migration: {float_matches}"


def test_database_tracks_schema_migrations(tmp_path: Path) -> None:
    """Verify that Database initializes and records applied migrations in schema_migrations table."""
    from src.storage.db import Database

    db = Database(db_path=tmp_path / "test_mig.db")
    migrations = db.get_applied_migrations()
    assert len(migrations) >= 1
    assert migrations[0]["version"] == 1
    assert "Initial AEGIS" in migrations[0]["description"]

