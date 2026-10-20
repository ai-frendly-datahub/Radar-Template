from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
import yaml

from main import ensure_collection_not_empty, run
from radar.collector import (
    RADAR_TEMPLATE_USER_AGENT,
    RSS_TIMEOUT_SECONDS,
    _create_session,
    collect_sources,
)
from radar.config_loader import filter_sources, load_category_config, load_settings
from radar.exceptions import ConfigError, EmptyCollectionError
from radar.models import Source
from radar.raw_logger import RawLogger

_FIXTURE = Path("tests/fixtures/challenge_feed.xml").read_bytes()


def test_coverage_config_uses_relative_paths() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    setup_cfg = Path("setup.cfg").read_text(encoding="utf-8")
    assert "relative_files = true" in pyproject
    assert "relative_files = True" in setup_cfg


def test_session_uses_identifying_user_agent_timeout_and_tls() -> None:
    session = _create_session()
    try:
        assert session.headers["User-Agent"] == RADAR_TEMPLATE_USER_AGENT
        assert session.headers["User-Agent"].startswith("Radar-Template/0.1")
        assert "Mozilla" not in session.headers["User-Agent"]
        assert session.verify is True
    finally:
        session.close()

    recorded: dict[str, object] = {}

    def _get(*_args: object, **kwargs: object) -> Mock:
        recorded.update(kwargs)
        response = Mock()
        response.raise_for_status.return_value = None
        response.content = _FIXTURE
        return response

    source = Source(name="Example News RSS", type="rss", url="https://example.com/feed.xml")
    with patch("radar.collector.requests.Session.get", side_effect=_get):
        articles, errors = collect_sources([source], category="template", max_workers=1)

    assert errors == []
    assert [article.title for article in articles] == ["Template release notes"]
    assert recorded["timeout"] == RSS_TIMEOUT_SECONDS == 45
    assert recorded["verify"] is True
    headers = recorded["headers"]
    assert isinstance(headers, dict)
    assert str(headers["User-Agent"]).startswith("Radar-Template/0.1")


def test_collector_failure_returns_empty_list_without_sample_data() -> None:
    source = Source(name="down", type="rss", url="https://example.com/feed.xml")
    with patch(
        "radar.collector.requests.Session.get",
        side_effect=requests.exceptions.ConnectionError("down"),
    ):
        articles, errors = collect_sources([source], category="template", max_workers=1)

    assert articles == []
    assert errors
    blob = " ".join(errors).lower()
    assert "sample" not in blob
    assert "fake" not in blob


def test_missing_secret_warns_once_and_records_names_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = Source(
        name="Keyed API",
        type="rss",
        url="https://example.com/feed.xml",
        config={"required_env": ["RADAR_TEMPLATE_TEST_TOKEN", "RADAR_TEMPLATE_TEST_SECRET"]},
    )
    logger = RawLogger(tmp_path)
    with patch.dict(
        os.environ,
        {
            "RADAR_TEMPLATE_TEST_TOKEN": "",
            "RADAR_TEMPLATE_TEST_SECRET": "",
            "DECOY_SECRET": "super-secret-value",
        },
        clear=False,
    ):
        articles, errors = collect_sources(
            [source],
            category="template",
            raw_logger=logger,
            max_workers=1,
        )

    assert articles == []
    assert any("skipped_missing_env RADAR_TEMPLATE_TEST_TOKEN" in error for error in errors)
    warning = capsys.readouterr().out
    assert warning.count("::warning title=Radar-Template missing secret::") == 1
    assert "RADAR_TEMPLATE_TEST_TOKEN" in warning
    assert "RADAR_TEMPLATE_TEST_SECRET" in warning
    assert "super-secret-value" not in warning
    skip_files = list(tmp_path.rglob("*.skip.json"))
    assert len(skip_files) == 1
    text = skip_files[0].read_text(encoding="utf-8")
    assert "RADAR_TEMPLATE_TEST_TOKEN" in text
    assert "RADAR_TEMPLATE_TEST_SECRET" in text
    assert "super-secret-value" not in text
    assert skip_files[0].name == "Keyed API.skip.json"


def test_invalid_required_env_is_not_written(tmp_path: Path) -> None:
    source = Source(
        name="bad-config",
        type="rss",
        url="https://example.com/feed.xml",
        config={"required_env": "actual-secret-value"},
    )
    logger = RawLogger(tmp_path)
    _articles, errors = collect_sources(
        [source],
        category="template",
        raw_logger=logger,
        max_workers=1,
    )
    assert errors
    assert "actual-secret-value" not in errors[0]
    assert "environment variable name" in errors[0]
    assert list(tmp_path.rglob("*.skip.json")) == []


def test_disabled_sources_are_not_active(tmp_path: Path) -> None:
    category_file = tmp_path / "template.yaml"
    category_file.write_text(
        yaml.safe_dump(
            {
                "category_name": "template",
                "display_name": "Template",
                "sources": [
                    {
                        "name": "Paused",
                        "type": "rss",
                        "url": "https://example.com/feed.xml",
                        "enabled": False,
                    }
                ],
                "entities": [],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_category_config("template", categories_dir=tmp_path)
    assert filter_sources(loaded.sources) == []
    with patch("radar.collector.requests.Session.get", side_effect=AssertionError("fetched")):
        articles, errors = collect_sources(loaded.sources, category="template", max_workers=1)
    assert articles == []
    assert errors == []


def test_ensure_collection_not_empty_rejects_zero_articles_when_policy_is_fail() -> None:
    with pytest.raises(EmptyCollectionError):
        ensure_collection_not_empty(
            collected_count=0,
            enabled_source_count=2,
            on_empty_collection="fail",
        )


def test_ensure_collection_not_empty_warns_and_skips_commit_by_default(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    output = tmp_path / "github_output.txt"
    output.write_text("", encoding="utf-8")
    with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}):
        skip_commit = ensure_collection_not_empty(collected_count=0, enabled_source_count=2)
    assert skip_commit is True
    warning = capsys.readouterr().out
    assert "::warning title=Radar-Template empty collection::" in warning
    assert "::error" not in warning
    text = output.read_text(encoding="utf-8")
    assert "collected=0" in text
    assert "skip_commit=true" in text


def test_ensure_collection_not_empty_can_warn_without_skipping_commit(
    tmp_path: Path,
) -> None:
    output = tmp_path / "github_output.txt"
    output.write_text("", encoding="utf-8")
    with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}):
        skip_commit = ensure_collection_not_empty(
            collected_count=0,
            enabled_source_count=2,
            on_empty_collection="warn",
            skip_commit_on_empty=False,
        )
    assert skip_commit is False
    assert "skip_commit=false" in output.read_text(encoding="utf-8")


def test_ensure_collection_not_empty_allows_items_or_no_enabled_sources(tmp_path: Path) -> None:
    output = tmp_path / "github_output.txt"
    output.write_text("", encoding="utf-8")
    with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}):
        assert ensure_collection_not_empty(collected_count=1, enabled_source_count=2) is False
        assert ensure_collection_not_empty(collected_count=0, enabled_source_count=0) is False
    text = output.read_text(encoding="utf-8")
    assert text.count("skip_commit=false") == 2
    assert "skip_commit=true" not in text


def _empty_run_paths(
    tmp_path: Path, *, policy: str | None, skip_commit: bool | None
) -> tuple[Path, Path]:
    config_path = tmp_path / "config.yaml"
    categories_dir = tmp_path / "categories"
    categories_dir.mkdir()
    settings: dict[str, object] = {
        "database_path": str(tmp_path / "data" / "radar_data.duckdb"),
        "report_dir": str(tmp_path / "reports"),
        "raw_data_dir": str(tmp_path / "data" / "raw"),
        "search_db_path": str(tmp_path / "data" / "search_index.db"),
    }
    if policy is not None:
        settings["on_empty_collection"] = policy
    if skip_commit is not None:
        settings["skip_commit_on_empty"] = skip_commit
    config_path.write_text(yaml.safe_dump(settings), encoding="utf-8")
    (categories_dir / "test_cat.yaml").write_text(
        yaml.safe_dump(
            {
                "category_name": "test_cat",
                "display_name": "Test",
                "sources": [
                    {"name": "Empty", "type": "rss", "url": "https://example.com/feed.xml"}
                ],
                "entities": [],
            }
        ),
        encoding="utf-8",
    )
    return config_path, categories_dir


def test_run_fails_when_active_sources_collect_nothing_and_policy_is_fail(tmp_path: Path) -> None:
    config_path, categories_dir = _empty_run_paths(tmp_path, policy="fail", skip_commit=True)
    empty_feed = (
        b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>"""
    )
    response = Mock()
    response.raise_for_status.return_value = None
    response.content = empty_feed
    with (
        patch("radar.collector.requests.Session.get", return_value=response),
        pytest.raises(EmptyCollectionError),
    ):
        run(
            category="test_cat",
            config_path=config_path,
            categories_dir=categories_dir,
            per_source_limit=5,
            recent_days=7,
            timeout=5,
        )


def test_run_warns_when_active_sources_collect_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path, categories_dir = _empty_run_paths(tmp_path, policy=None, skip_commit=None)
    loaded = load_settings(config_path)
    assert loaded.on_empty_collection == "warn"
    assert loaded.skip_commit_on_empty is True
    empty_feed = (
        b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>"""
    )
    response = Mock()
    response.raise_for_status.return_value = None
    response.content = empty_feed
    output = tmp_path / "github_output.txt"
    output.write_text("", encoding="utf-8")
    with (
        patch("radar.collector.requests.Session.get", return_value=response),
        patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}),
    ):
        report = run(
            category="test_cat",
            config_path=config_path,
            categories_dir=categories_dir,
            per_source_limit=5,
            recent_days=7,
            timeout=5,
        )
    assert report.exists()
    captured = capsys.readouterr().out
    assert "::warning title=Radar-Template empty collection::" in captured
    assert "Collected 0 article(s)" in captured
    assert "skip_commit=true" in output.read_text(encoding="utf-8")


def test_template_config_documents_warn_and_skip_commit_defaults() -> None:
    settings = load_settings(Path("config/config.yaml"))
    assert settings.on_empty_collection == "warn"
    assert settings.skip_commit_on_empty is True
    text = Path("config/config.yaml").read_text(encoding="utf-8")
    assert "템플릿" in text
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "on_empty_collection: warn" in readme
    assert "skip_commit_on_empty: true" in readme


def test_invalid_empty_collection_policy_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "database_path: data/radar_data.duckdb\n"
        "report_dir: reports\n"
        "raw_data_dir: data/raw\n"
        "search_db_path: data/search_index.db\n"
        "on_empty_collection: explode\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_settings(config_path)


def test_template_example_feed_is_a_live_public_rss() -> None:
    for relative in ("config/categories/template.yaml", "config/categories/_template.yaml"):
        raw = yaml.safe_load(Path(relative).read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        sources = raw.get("sources")
        assert isinstance(sources, list) and sources
        first = sources[0]
        assert isinstance(first, dict)
        url = str(first.get("url"))
        assert url == "https://www.nasa.gov/feed/"
        assert "example.com" not in url
        assert "sample" not in url


def test_crawler_workflow_skips_commit_when_collection_is_empty() -> None:
    text = Path(".github/workflows/radar-crawler.yml").read_text(encoding="utf-8")
    assert "id: radar" in text
    assert text.count("steps.radar.outputs.skip_commit != 'true'") >= 2
    auto_commit = text.split("Auto-commit data updates", maxsplit=1)[1].split(
        "Deploy to GitHub Pages", maxsplit=1
    )[0]
    assert "continue-on-error" not in auto_commit
    assert "skip_commit != 'true'" in auto_commit
