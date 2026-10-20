"""Load DuckDB compaction from the radar-core distribution pinned at git main.

This repository vendors a small ``radar_core`` package for models and the Korean
analyzer. That directory is earlier on ``sys.path`` than site-packages, so
``compact_duckdb_file`` is loaded from the installed ``radar-core`` distribution
instead of being reimplemented here.

The installed module uses ``from .logger import get_logger``. Loading the file
with no package parent raises ``ImportError: attempted relative import with no
known parent package``. The loader below registers a private package whose
``__path__`` is the installed distribution, so that relative import resolves to
the installed ``logger.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from types import ModuleType

_INSTALLED_PACKAGE_ALIAS = "_radar_core_installed"


def load_module_from_package(
    package_dir: Path,
    module_name: str,
    *,
    package_alias: str,
) -> ModuleType:
    """Load ``package_dir / module_name.py`` with a real package parent.

    Relative imports inside the loaded module resolve against ``package_dir``,
    not against the vendored ``radar_core`` package already on ``sys.path``.
    """
    package_dir = package_dir.resolve()
    module_path = package_dir / f"{module_name}.py"
    if not module_path.is_file():
        raise ImportError(f"{module_path} is not a file")

    package = sys.modules.get(package_alias)
    if package is None:
        package = ModuleType(package_alias)
        package.__path__ = [str(package_dir)]
        package.__package__ = package_alias
        package.__file__ = str(package_dir / "__init__.py")
        sys.modules[package_alias] = package
    else:
        search = [str(entry) for entry in package.__path__]
        location = str(package_dir)
        if location not in search:
            package.__path__ = [*search, location]

    full_name = f"{package_alias}.{module_name}"
    spec = importlib.util.spec_from_file_location(full_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package_alias
    sys.modules[full_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(full_name, None)
        raise
    return module


def _installed_module() -> ModuleType:
    try:
        dist = distribution("radar-core")
    except PackageNotFoundError as exc:
        raise ImportError("radar-core is not installed") from exc
    package_dir = Path(str(dist.locate_file("radar_core")))
    located = package_dir / "db_compact.py"
    if not located.is_file() or located.resolve() == Path(__file__).resolve():
        raise ImportError("installed radar-core has no db_compact.py")
    module = load_module_from_package(
        package_dir,
        "db_compact",
        package_alias=_INSTALLED_PACKAGE_ALIAS,
    )
    if not callable(getattr(module, "compact_duckdb_file", None)):
        raise ImportError("installed radar-core db_compact has no compact_duckdb_file")
    return module


compact_duckdb_file: Callable[..., dict[str, object]] = _installed_module().compact_duckdb_file
