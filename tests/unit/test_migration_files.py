"""Migration file discovery (no database): naming, ordering, duplicates, gaps."""

from __future__ import annotations

from pathlib import Path

import pytest

from voiceos.infrastructure.postgres.migrations import MigrationError, discover, verify


def _files(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_text(f"-- {name}\n")


def test_repository_migrations_are_valid_and_start_with_the_phase0_foundation() -> None:
    migrations = discover()
    assert [m.version for m in migrations] == list(range(1, len(migrations) + 1))
    assert migrations[0].filename == "0001_foundation.sql"
    assert migrations[1].filename == "0002_product_foundation.sql"


def test_order_is_by_version_not_by_creation(tmp_path: Path) -> None:
    _files(tmp_path, "0002_b.sql", "0001_a.sql", "0003_c.sql")
    assert [m.filename for m in discover(tmp_path)] == ["0001_a.sql", "0002_b.sql", "0003_c.sql"]


@pytest.mark.parametrize(
    ("names", "message"),
    [
        (("0001_a.sql", "0001_b.sql"), "duplicate"),
        (("0001_a.sql", "0003_c.sql"), "gaps"),
        (("0002_b.sql",), "gaps"),
        (("1_a.sql",), "invalid"),
        (("0001_A.sql",), "invalid"),
        (("0001-a.sql",), "invalid"),
    ],
)
def test_irregular_files_are_errors(tmp_path: Path, names: tuple[str, ...], message: str) -> None:
    _files(tmp_path, *names)
    with pytest.raises(MigrationError, match=message):
        discover(tmp_path)


def test_verify_requires_an_unchanged_prefix(tmp_path: Path) -> None:
    _files(tmp_path, "0001_a.sql", "0002_b.sql")
    migrations = discover(tmp_path)
    first = migrations[0]
    assert verify(migrations, {}) == migrations
    assert verify(migrations, {1: (first.name, first.checksum)}) == migrations[1:]
    with pytest.raises(MigrationError, match="modified"):
        verify(migrations, {1: (first.name, "0" * 64)})
    with pytest.raises(MigrationError, match="modified"):
        verify(migrations, {1: ("renamed", first.checksum)})
    with pytest.raises(MigrationError, match="has no file"):
        verify(migrations, {1: (first.name, first.checksum), 3: ("c", "0" * 64)})
