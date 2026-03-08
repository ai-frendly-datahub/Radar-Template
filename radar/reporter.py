from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, cast

from jinja2 import Template

from .models import Article, CategoryConfig


class _TemplateRenderer(Protocol):
    def render(self, **context: object) -> str: ...


def generate_report(
    *,
    category: CategoryConfig,
    articles: Iterable[Article],
    output_path: Path,
    stats: dict[str, int],
    errors: list[str] | None = None,
) -> Path:
    """Render a simple HTML report for the collected articles."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    articles_list = list(articles)
    entity_counts = _count_entities(articles_list)

    template = cast(_TemplateRenderer, Template(_REPORT_TEMPLATE))
    rendered = template.render(
        category=category,
        articles=articles_list,
        generated_at=datetime.now(timezone.utc),
        stats=stats,
        entity_counts=entity_counts,
        errors=errors or [],
    )
    _ = output_path.write_text(rendered, encoding="utf-8")
    return output_path


def _count_entities(articles: Iterable[Article]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for article in articles:
        for entity_name, keywords in (article.matched_entities or {}).items():
            counter[entity_name] += len(keywords)
    return counter


def generate_index_html(report_dir: Path) -> Path:
    """Generate an index.html that lists all available report files."""
    report_dir.mkdir(parents=True, exist_ok=True)

    html_files = sorted(
        [f for f in report_dir.glob("*.html") if f.name != "index.html"],
        key=lambda p: p.name,
    )

    reports = []
    for html_file in html_files:
        name = html_file.stem
        display_name = name.replace("_report", "").replace("_", " ").title()
        reports.append({"filename": html_file.name, "display_name": display_name})

    template = cast(_TemplateRenderer, Template(_INDEX_TEMPLATE))
    rendered = template.render(
        reports=reports,
        generated_at=datetime.now(timezone.utc),
    )

    index_path = report_dir / "index.html"
    _ = index_path.write_text(rendered, encoding="utf-8")
    return index_path


_REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ category.display_name }} - Radar Report</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; padding: 24px; background: #f6f8fb; color: #0f172a; }
    h1 { margin: 0 0 8px 0; }
    h2 { margin: 24px 0 12px 0; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 12px 0 24px 0; }
    .card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    .muted { color: #475569; font-size: 13px; }
    .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #e0f2fe; color: #0369a1; font-size: 12px; margin-right: 6px; }
    .chip { display: inline-block; padding: 4px 8px; border-radius: 8px; background: #0ea5e9; color: white; font-size: 12px; margin: 4px 4px 0 0; }
    .articles { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
    a { color: #0f172a; text-decoration: none; }
    a:hover { text-decoration: underline; }
    footer { margin-top: 32px; color: #475569; font-size: 13px; }
    .errors { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; padding: 12px; border-radius: 10px; margin-top: 16px; }
  </style>
</head>
<body>
  <h1>{{ category.display_name }}</h1>
  <div class="muted">Generated at {{ generated_at.isoformat() }} (UTC)</div>

  <div class="summary">
    <div class="card"><div class="muted">Sources</div><strong>{{ stats.sources }}</strong></div>
    <div class="card"><div class="muted">Collected</div><strong>{{ stats.collected }}</strong></div>
    <div class="card"><div class="muted">With entity hits</div><strong>{{ stats.matched }}</strong></div>
    <div class="card"><div class="muted">Recent window (days)</div><strong>{{ stats.window_days }}</strong></div>
  </div>

  {% if errors %}
    <div class="errors">
      <strong>Collection errors</strong><br>
      {% for error in errors %}• {{ error }}<br>{% endfor %}
    </div>
  {% endif %}

  {% if entity_counts %}
  <h2>Entity hit counts</h2>
  <div class="card">
    {% for entity, count in entity_counts.most_common() %}
      <span class="pill">{{ entity }} · {{ count }}</span>
    {% endfor %}
  </div>
  {% endif %}

  <h2>Recent articles</h2>
  <div class="articles">
    {% for article in articles %}
    <div class="card">
      <a href="{{ article.link }}" target="_blank" rel="noopener noreferrer"><strong>{{ article.title }}</strong></a>
      <div class="muted">{{ article.source }}{% if article.published %} · {{ article.published.date().isoformat() }}{% endif %}</div>
      <div class="muted">{{ article.summary[:220] }}{% if article.summary|length > 220 %}...{% endif %}</div>
      {% if article.matched_entities %}
        <div style="margin-top:8px;">
          {% for entity, keywords in article.matched_entities.items() %}
            <span class="chip">{{ entity }}: {{ keywords | join(", ") }}</span>
          {% endfor %}
        </div>
      {% endif %}
    </div>
    {% endfor %}
    {% if articles|length == 0 %}
      <div class="card">No articles in the recent window.</div>
    {% endif %}
  </div>

  <footer>
    This is a lightweight template — extend collectors/analyzers as needed.
  </footer>
</body>
</html>
"""


_INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Radar Reports</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; padding: 24px; background: #f6f8fb; color: #0f172a; }
    h1 { margin: 0 0 8px 0; }
    .muted { color: #475569; font-size: 13px; margin-bottom: 24px; }
    .reports { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
    .card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); transition: box-shadow 0.2s; }
    .card:hover { box-shadow: 0 4px 6px rgba(0,0,0,0.08); }
    a { color: #0f172a; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .empty { text-align: center; color: #64748b; padding: 48px; }
  </style>
</head>
<body>
  <h1>Radar Reports</h1>
  <div class="muted">Generated at {{ generated_at.isoformat() }} (UTC)</div>

  {% if reports %}
  <div class="reports">
    {% for report in reports %}
    <div class="card">
      <a href="{{ report.filename }}"><strong>{{ report.display_name }}</strong></a>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="empty">No reports available yet.</div>
  {% endif %}
</body>
</html>
"""
