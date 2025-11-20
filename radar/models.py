from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Source:
    name: str
    type: str
    url: str


@dataclass
class EntityDefinition:
    name: str
    display_name: str
    keywords: List[str]


@dataclass
class Article:
    title: str
    link: str
    summary: str
    published: Optional[datetime]
    source: str
    category: str
    matched_entities: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class CategoryConfig:
    category_name: str
    display_name: str
    sources: List[Source]
    entities: List[EntityDefinition]


@dataclass
class RadarSettings:
    database_path: Path
    report_dir: Path
