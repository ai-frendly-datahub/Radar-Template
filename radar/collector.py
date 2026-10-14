from __future__ import annotations

import html
import os
import re
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import requests

from .common.validators import is_challenge_or_error_page
from .exceptions import NetworkError, ParseError, SourceError
from .models import Article, Source
from .raw_logger import RawLogger
from .resilience import get_circuit_breaker_manager

# Identifying client name. Some public feeds reject the default python-requests
# agent. This is a fixed product name, not a browser impersonation list.
RADAR_TEMPLATE_USER_AGENT = (
    "Radar-Template/0.1 (+https://github.com/ai-frendly-datahub/Radar-Template; public-rss)"
)
RSS_TIMEOUT_SECONDS = 45
_ENV_VAR_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": RADAR_TEMPLATE_USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}


class RateLimiter:
    def __init__(self, min_interval: float = 0.5):
        self._min_interval = min_interval
        self._last_request = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()


def _resolve_max_workers(max_workers: int | None = None) -> int:
    if max_workers is None:
        try:
            parsed = int(os.environ.get("RADAR_MAX_WORKERS", "5"))
        except ValueError:
            parsed = 5
    else:
        parsed = max_workers
    return max(1, min(parsed, 10))


def _create_session() -> requests.Session:
    session = requests.Session()
    session.verify = True
    session.headers.update(dict(_DEFAULT_HEADERS))
    return session


def _env_var_names(value: object) -> list[str]:
    raw_names: list[str] = []
    if isinstance(value, str):
        raw_names = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        raw_names = [str(item) for item in value]
    names: list[str] = []
    for item in raw_names:
        candidate = item.strip()
        if not candidate:
            continue
        if _ENV_VAR_NAME.fullmatch(candidate) is None:
            raise ValueError("required_env must be an environment variable name")
        names.append(candidate)
    return names


def missing_required_env(source: Source) -> list[str]:
    """Return required env var names that are unset. Values are never returned."""
    configured = source.config.get("required_env", source.config.get("required_env_vars"))
    missing: list[str] = []
    for name in _env_var_names(configured):
        if not os.environ.get(name, "").strip():
            missing.append(name)
    return missing


def emit_missing_secret_warning(source_name: str, env_names: str | Sequence[str]) -> None:
    """Warn once that a source was skipped. Prints env var names, never values."""
    names = _env_var_names(env_names if isinstance(env_names, str) else list(env_names))
    if not names:
        raise ValueError("required_env must be an environment variable name")
    message = f"{source_name} skipped; required env {', '.join(names)}"
    print(f"::warning title=Radar-Template missing secret::{message}", flush=True)


def _fetch_url_with_retry(
    url: str,
    *,
    timeout: int,
    session: requests.Session | None = None,
    max_attempts: int = 3,
    headers: Mapping[str, str] | None = None,
) -> requests.Response:
    merged = dict(_DEFAULT_HEADERS)
    if headers:
        for key, value in headers.items():
            if key.lower() == "user-agent":
                continue
            merged[key] = value
    merged["User-Agent"] = RADAR_TEMPLATE_USER_AGENT
    last_error: requests.exceptions.RequestException | None = None
    for attempt in range(max_attempts):
        try:
            if session is not None:
                response = session.get(url, timeout=timeout, headers=merged, verify=True)
            else:
                response = requests.get(url, timeout=timeout, headers=merged, verify=True)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt == max_attempts - 1:
                raise
    raise RuntimeError(f"Retry loop exited unexpectedly: {last_error}")


def collect_sources(
    sources: list[Source],
    *,
    category: str,
    limit_per_source: int = 30,
    timeout: int = RSS_TIMEOUT_SECONDS,
    min_interval_per_host: float = 0.5,
    max_workers: int | None = None,
    raw_logger: RawLogger | None = None,
) -> tuple[list[Article], list[str]]:
    """Fetch configured sources.

    Failures return an empty article list for that source. This function never
    invents sample or fake items.
    """
    enabled_sources = [source for source in sources if source.enabled]
    if not enabled_sources:
        return [], []

    workers = _resolve_max_workers(max_workers)
    manager = get_circuit_breaker_manager()
    session = _create_session()
    source_hosts = {
        source.name: (urlparse(source.url).netloc.lower() or source.name)
        for source in enabled_sources
    }
    rate_limiters = {
        host: RateLimiter(min_interval=min_interval_per_host) for host in set(source_hosts.values())
    }

    def _collect_for_source(source: Source) -> tuple[list[Article], list[str]]:
        try:
            missing_env = missing_required_env(source)
        except ValueError:
            return [], [f"{source.name}: required_env must be an environment variable name"]
        if missing_env:
            emit_missing_secret_warning(source.name, missing_env)
            if raw_logger is not None:
                raw_logger.log_skip(source_name=source.name, required_env=missing_env)
            return [], [f"{source.name}: skipped_missing_env {', '.join(missing_env)}"]

        rate_limiters[source_hosts[source.name]].acquire()
        try:
            breaker = manager.get_breaker(source.name)
            articles = breaker.call(
                _collect_single,
                source,
                category=category,
                limit=limit_per_source,
                timeout=timeout,
                session=session,
            )
            return articles, []
        except (SourceError, ParseError) as exc:
            return [], [str(exc)]
        except NetworkError as exc:
            return [], [f"{source.name}: {exc}"]
        except Exception as exc:
            return [], [f"{source.name}: Unexpected error - {type(exc).__name__}: {exc}"]

    try:
        articles: list[Article] = []
        errors: list[str] = []

        if workers == 1:
            for source in enabled_sources:
                source_articles, source_errors = _collect_for_source(source)
                articles.extend(source_articles)
                errors.extend(source_errors)
            return articles, errors

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures: list[Future[tuple[list[Article], list[str]]]] = [
                executor.submit(_collect_for_source, source) for source in enabled_sources
            ]
            for future in futures:
                source_articles, source_errors = future.result()
                articles.extend(source_articles)
                errors.extend(source_errors)
        return articles, errors
    finally:
        session.close()


def _collect_single(
    source: Source,
    *,
    category: str,
    limit: int,
    timeout: int,
    session: requests.Session | None = None,
) -> list[Article]:
    if source.type.lower() != "rss":
        raise SourceError(source.name, f"Unsupported source type '{source.type}'")

    try:
        response = _fetch_url_with_retry(
            source.url,
            timeout=timeout,
            session=session,
            headers=source.headers,
        )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        raise NetworkError(f"Network error fetching {source.name}: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise SourceError(source.name, f"Request failed: {exc}") from exc

    try:
        body = response.content if isinstance(response.content, bytes) else bytes(response.content)
        feed = feedparser.parse(body)
        articles: list[Article] = []
        dropped_challenge = 0
        for entry in feed.entries[:limit]:
            title = html.unescape(_entry_text(entry, "title").strip())
            link = _entry_text(entry, "link").strip()
            if not title or not link:
                continue
            summary = html.unescape(
                (_entry_text(entry, "summary") or _entry_text(entry, "description")).strip()
            )
            if is_challenge_or_error_page(title, summary):
                dropped_challenge += 1
                continue
            articles.append(
                Article(
                    title=title,
                    link=link,
                    summary=summary,
                    published=_extract_datetime(entry),
                    source=source.name,
                    category=category,
                )
            )
        if articles:
            return articles
        if dropped_challenge:
            raise ParseError(
                f"Feed from {source.name} was a challenge, Cloudflare, or cookie-wall page"
            )
        raise ParseError(f"Feed from {source.name} contained no usable entries")
    except ParseError:
        raise
    except Exception as exc:
        raise SourceError(source.name, f"Failed to parse feed: {exc}") from exc


def _extract_datetime(entry: Mapping[str, object]) -> datetime | None:
    for key in ("published", "updated", "date"):
        raw = entry.get(key)
        if raw:
            try:
                parsed = parsedate_to_datetime(str(raw))
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC)
            except Exception:
                continue
    return None


def _entry_text(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key)
    return value if isinstance(value, str) else ""
