from __future__ import annotations

import argparse
from pathlib import Path

from radar.analyzer import apply_entity_rules
from radar.collector import collect_sources
from radar.config_loader import load_category_config, load_settings
from radar.reporter import generate_report
from radar.storage import RadarStorage


def run(
    *,
    category: str,
    config_path: Path | None = None,
    categories_dir: Path | None = None,
    per_source_limit: int = 30,
    recent_days: int = 7,
    timeout: int = 15,
    keep_days: int = 90,
) -> Path:
    """Execute the lightweight collect -> analyze -> report pipeline."""
    settings = load_settings(config_path)
    category_cfg = load_category_config(category, categories_dir=categories_dir)

    print(f"[Radar] Collecting '{category_cfg.display_name}' from {len(category_cfg.sources)} sources...")
    collected, errors = collect_sources(
        category_cfg.sources,
        category=category_cfg.category_name,
        limit_per_source=per_source_limit,
        timeout=timeout,
    )
    analyzed = apply_entity_rules(collected, category_cfg.entities)

    storage = RadarStorage(settings.database_path)
    storage.upsert_articles(analyzed)
    storage.delete_older_than(keep_days)
    recent_articles = storage.recent_articles(category_cfg.category_name, days=recent_days)
    storage.close()

    stats = {
        "sources": len(category_cfg.sources),
        "collected": len(collected),
        "matched": sum(1 for a in collected if a.matched_entities),
        "window_days": recent_days,
    }

    output_path = settings.report_dir / f"{category_cfg.category_name}_report.html"
    generate_report(
        category=category_cfg,
        articles=recent_articles,
        output_path=output_path,
        stats=stats,
        errors=errors,
    )
    print(f"[Radar] Report generated at {output_path}")
    if errors:
        print(f"[Radar] {len(errors)} source(s) had issues. See report for details.")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lightweight Radar template runner")
    parser.add_argument("--category", required=True, help="Category name matching a YAML in config/categories/")
    parser.add_argument("--config", type=Path, default=None, help="Path to config/config.yaml (optional)")
    parser.add_argument("--categories-dir", type=Path, default=None, help="Custom directory for category YAML files")
    parser.add_argument("--per-source-limit", type=int, default=30, help="Max items to pull from each source")
    parser.add_argument("--recent-days", type=int, default=7, help="Window (days) to show in the report")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout per request (seconds)")
    parser.add_argument("--keep-days", type=int, default=90, help="Retention window for stored items")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        category=args.category,
        config_path=args.config,
        categories_dir=args.categories_dir,
        per_source_limit=args.per_source_limit,
        recent_days=args.recent_days,
        timeout=args.timeout,
        keep_days=args.keep_days,
    )
