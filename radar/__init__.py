"""Radar-Template - 레이더 템플릿"""

import sys
from importlib import import_module


__version__ = "0.2.0"

from radar.storage import RadarStorage


for _module_name in (
    "collector",
    "exceptions",
    "nl_query",
    "raw_logger",
    "search_index",
):
    sys.modules[f"{__name__}.{_module_name}"] = import_module(f"radar_core.{_module_name}")


__all__ = ["RadarStorage", "__version__"]
