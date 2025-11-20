from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from .models import CategoryConfig, EntityDefinition, RadarSettings, Source


def _resolve_path(path_value: str, *, project_root: Path) -> Path:
    """Resolve a path from config, treating relative paths as project-root relative."""
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def load_settings(config_path: Path | None = None) -> RadarSettings:
    """Load global radar settings such as database and report directories."""
    project_root = Path(__file__).resolve().parent.parent
    config_file = config_path or project_root / "config" / "config.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    db_path = _resolve_path(raw.get("database_path", "data/radar_data.duckdb"), project_root=project_root)
    report_dir = _resolve_path(raw.get("report_dir", "reports"), project_root=project_root)
    return RadarSettings(database_path=db_path, report_dir=report_dir)


def load_category_config(category_name: str, categories_dir: Path | None = None) -> CategoryConfig:
    """Load a category YAML and parse it into a CategoryConfig object."""
    project_root = Path(__file__).resolve().parent.parent
    base_dir = categories_dir or project_root / "config" / "categories"
    config_file = Path(base_dir) / f"{category_name}.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"Category config not found: {config_file}")

    raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    sources = [_parse_source(entry) for entry in raw.get("sources", [])]
    entities = [_parse_entity(entry) for entry in raw.get("entities", [])]

    display_name = raw.get("display_name") or raw.get("category_name") or category_name

    return CategoryConfig(
        category_name=raw.get("category_name") or category_name,
        display_name=display_name,
        sources=sources,
        entities=entities,
    )


def _parse_source(entry: dict) -> Source:
    if not entry:
        raise ValueError("Empty source entry in category config")
    return Source(
        name=entry.get("name", "Unnamed Source"),
        type=entry.get("type", "rss"),
        url=entry.get("url", ""),
    )


def _parse_entity(entry: dict) -> EntityDefinition:
    if not entry:
        raise ValueError("Empty entity entry in category config")
    name = entry.get("name", "").strip() or "entity"
    display_name = entry.get("display_name", "").strip() or name
    keywords: Iterable[str] = entry.get("keywords") or []
    keyword_list = [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
    return EntityDefinition(name=name, display_name=display_name, keywords=keyword_list)
