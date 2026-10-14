"""Load DuckDB compaction from the radar-core distribution pinned at git main.

This repository vendors a small ``radar_core`` package for models and the Korean
analyzer. That directory is earlier on ``sys.path`` than site-packages, so
``compact_duckdb_file`` is loaded from the installed ``radar-core`` distribution
instead of being reimplemented here.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from types import ModuleType


def _installed_module() -> ModuleType:
    try:
        dist = distribution("radar-core")
    except PackageNotFoundError as exc:
        raise ImportError("radar-core is not installed") from exc
    located = Path(str(dist.locate_file("radar_core/db_compact.py")))
    if not located.is_file() or located.resolve() == Path(__file__).resolve():
        raise ImportError("installed radar-core has no db_compact.py")
    spec = importlib.util.spec_from_file_location("_radar_core_installed_db_compact", located)
    if spec is None or spec.loader is None:
        raise ImportError("installed radar-core db_compact could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "compact_duckdb_file", None)):
        raise ImportError("installed radar-core db_compact has no compact_duckdb_file")
    return module


compact_duckdb_file: Callable[..., dict[str, object]] = _installed_module().compact_duckdb_file
