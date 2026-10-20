from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import duckdb

from radar_core.db_compact import compact_duckdb_file, load_module_from_package


def test_relative_import_resolves_inside_the_loaded_package(tmp_path: Path) -> None:
    package_dir = tmp_path / "installed_radar_core"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "logger.py").write_text(
        "def get_logger(name):\n    return name\n",
        encoding="utf-8",
    )
    (package_dir / "db_compact.py").write_text(
        "from .logger import get_logger\n"
        "def compact_duckdb_file(path):\n"
        "    return {'logger': get_logger('compact')}\n",
        encoding="utf-8",
    )

    module = load_module_from_package(
        package_dir,
        "db_compact",
        package_alias="_radar_core_relative_import_test",
    )
    loaded = cast(Any, module)
    result = loaded.compact_duckdb_file(package_dir / "unused.duckdb")
    assert result == {"logger": "compact"}


def test_installed_compactor_does_not_fail_on_relative_import(tmp_path: Path) -> None:
    database = tmp_path / "radar_data.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create table articles (title varchar, collected_at timestamp)")
        connection.execute("insert into articles values ('live', current_timestamp)")
    finally:
        connection.close()

    result = compact_duckdb_file(database)
    error = str(result.get("error") or "")
    assert "relative import" not in error
    assert result.get("reason") == "within_limit"
    assert result.get("compacted") is False
