from __future__ import annotations

from importlib import import_module


RadarStorage = import_module("radar.storage").RadarStorage
collect_sources = import_module("radar.collector").collect_sources
apply_entity_rules = import_module("radar.analyzer").apply_entity_rules

__all__ = ["RadarStorage", "collect_sources", "apply_entity_rules"]
