# AI-FRIENDLY DATAHUB WORKSPACE

16개 Radar 저장소로 구성된 다중 도메인 뉴스/트렌드 수집 플랫폼. RSS/API 수집 → 키워드 엔티티 태깅 → DuckDB 저장 → HTML 리포트 → GitHub Pages 배포.

## REPO TIERS

| Tier | Repos | 특징 |
|------|-------|------|
| **Template** | Radar-Template | 모든 레이더의 원본 템플릿 |
| **Standard** | Benefit, Blog, Event, Game, Mobility, Paper, Paperwork, Policy, Queue, Refund, Subscription, Trust | 템플릿 기반 단일 패키지 구조 |
| **Advanced** | Home, Wine, Trend, Price | 모듈화 구조, graph DB, 전용 collectors |

## QUICK REFERENCE

| Repo | Package | Branch | Schedule (UTC) | 고유 기능 |
|------|---------|--------|----------------|-----------|
| Radar-Template | `radar/` | main | 00:00 daily | 캐노니컬 템플릿 |
| BenefitRadar | `benefitradar/` | master | 08:00, 20:00 | bokjiro (복지로) API |
| EventRadar | `eventradar/` | main | 6h마다 | — |
| GameRadar | `radar/` | master | 01:00 daily | — |
| MobilityRadar | `mobilityradar/` | main | 08:00, 20:00 | CityBikes API |
| PaperRadar | `paperradar/` | main | 6h마다 | 7개 학술 API (arXiv/Semantic Scholar/PubMed/bioRxiv/SSRN/OpenAlex/CrossRef) |
| PaperworkRadar | `paperworkradar/` | main | 07:00 daily | 정부24 API |
| PolicyRadar | `policyradar/` | main | 03:00 daily | — |
| QueueRadar | `queueradar/` | main | 6h마다 | queue_times API |
| RefundRadar | `refundradar/` | main | 05:00 daily | — |
| SubscriptionRadar | `subscriptionradar/` | main | 02:00 daily | — |
| TrustRadar | `trustradar/` | main | 04:00, 16:00 | — |
| HomeRadar | `collectors/analyzers/...` | main | 00:00 daily | graph DB, MOLIT API |
| WineRadar | `collectors/analyzers/...` | main | 23:00 daily | vector index, quality checks |
| TrendRadar | `collectors/analyzers/...` | main | 22:00 daily | 7개 외부 API (Google/Naver/Reddit/YouTube/Wikipedia) |
| PriceRadar | `priceradar/` (sub-packages) | main | 09:00 daily | scoring, pipeline, enuri/fallcent |
| BlogRadar | `blogradar/` | main | 06:00 daily | 53개 RSS 소스 (국내+글로벌 기술블로그) |

## TEMPLATE PATTERN (Standard Tier)

```
{Repo}/
├── main.py                      # CLI: python main.py --category <name> --recent-days 7 --keep-days 90
├── {name}radar/                  # 또는 radar/ (GameRadar, Radar-Template)
│   ├── collector.py              # collect_sources() — RSS/API 수집
│   ├── analyzer.py               # apply_entity_rules() — 키워드 매칭
│   ├── reporter.py               # generate_report() — Jinja2 HTML
│   ├── storage.py                # RadarStorage — DuckDB upsert/query/retention
│   ├── models.py                 # Source, Article, EntityDefinition, CategoryConfig
│   ├── config_loader.py          # YAML 로딩
│   ├── raw_logger.py             # JSONL 원시 데이터 로깅
│   ├── search_index.py           # SQLite FTS5 전문 검색
│   ├── nl_query.py               # 자연어 쿼리 파서
│   ├── logger.py                 # structlog 구조화 로깅
│   ├── notifier.py               # Email/Webhook 알림
│   ├── common/                   # 공유 유틸리티
│   └── mcp_server/               # MCP 서버 (server.py + tools.py)
├── config/
│   ├── config.yaml               # database_path, report_dir, raw_data_dir, search_db_path
│   └── categories/{domain}.yaml  # 소스 + 엔티티 정의
├── data/                         # DuckDB, search_index.db, raw/ JSONL
├── reports/                      # 생성된 HTML 리포트
├── tests/unit/                   # pytest 단위 테스트
└── .github/workflows/radar-crawler.yml
```

## ADVANCED PATTERN (Home, Wine, Trend, Price)

템플릿과 다른 점만:
- **분리된 모듈**: `collectors/`, `analyzers/`, `reporters/` 최상위 디렉토리
- **Graph DB**: `graph/graph_store.py` — DuckDB 기반 노드/엣지 관계 저장
- **추가 도구**: pyproject.toml, pytest.ini, setup.cfg, requirements-dev.txt, .editorconfig
- **테스트 마커**: `@pytest.mark.unit`, `integration`, `e2e`, `network`
- **PriceRadar만**: 단일 패키지 `priceradar/` 안에 sub-packages (collectors/, analyzers/ 등)

→ 각 Advanced 레포의 `AGENTS.md` 참조

## PIPELINE

```
main.py → load_settings() → load_category_config()
  → collect_sources(RSS/API, limit=30, timeout=15)
  → RawLogger.log(JSONL)
  → apply_entity_rules(keyword matching)
  → RadarStorage.upsert_articles(DuckDB)
  → SearchIndex.upsert(SQLite FTS5)
  → generate_report(Jinja2 HTML)
  → _send_notifications() [optional]
```

## CI/CD

- **Workflow**: `.github/workflows/radar-crawler.yml`
- **Triggers**: cron (스케줄 분산) + workflow_dispatch (수동)
- **Steps**: checkout → Python 3.11 → pip install → main.py 실행 → gh-pages 배포 → DuckDB artifact 백업
- **Deploy**: `peaceiris/actions-gh-pages@v3` → `gh-pages` 브랜치
- **Auto-commit**: `stefanzweifel/git-auto-commit-action@v5` — DuckDB 파일 커밋
- **TZ**: Asia/Seoul, concurrency group 단일 실행
- **Health Check**: `.github/workflows/health-check.yml` — 매주 일요일 03:00 UTC, 전체 15개 프로젝트 lint/type-check 일괄 점검 (Template 제외)
- **PR Checks**: 각 레포 `.github/workflows/pr-checks.yml` — `pip install -e .` 검증 step 포함

### publish_dir 경로 차이

| Tier | Workflow | publish_dir | 비고 |
|------|----------|-------------|------|
| **Template/Standard** | `radar-crawler.yml` | `./reports` | 캐노니컬 기본값 |
| **Advanced** (Home, Wine, Price) | `deploy-pages.yml` | `./docs/reports` | 별도 배포 워크플로우 |
| **Advanced** (Home, Wine, Price) | `radar-crawler.yml` | `./reports` | 레거시 (비활성화 중) |
| **TrendRadar** | `daily_trends.yml` | `./docs` | docs 루트 전체 배포 |
| **TrendRadar** | `spike_analysis.yml` | `./docs/reports` | 스파이크 분석 전용 |

> ⚠️ Advanced Tier는 활성 워크플로우의 `publish_dir`이 `./docs/reports`이므로, 리포트 생성 경로도 `docs/reports/`를 사용해야 함.

## CONVENTIONS

- Python 3.11+, `from __future__ import annotations`
- Black (line-length=100) + Ruff (E,W,F,I,N,UP,B,C4,DTZ) + MyPy strict
- 타입 힌트 필수, `as any` / `type: ignore` 금지
- dataclass 기반 모델 (Pydantic은 PriceRadar만)
- DuckDB upsert 패턴: link 기준 중복 제거
- 모든 HTTP 요청에 timeout + tenacity 재시도
- JSONL 원시 데이터는 `data/raw/{YYYY-MM-DD}/{source}.jsonl`

### config/ 명명 차이

대부분의 레포는 `config/config.yaml` + `config/categories/{domain}.yaml` 패턴을 따르지만, 일부 예외 존재:

| Repo | 주 설정 파일 | 추가 설정 | 비고 |
|------|-------------|----------|------|
| **Standard 11개** | `config/config.yaml` | `config/categories/{domain}.yaml` | 캐노니컬 패턴 |
| **TrendRadar** | `config/keyword_sets.yaml` | `config/notifications.yaml` | categories 대신 keyword_sets 사용 |
| **HomeRadar** | `config/config.yaml` | `config/notifications.yaml` | 알림 설정 분리 |
| **BenefitRadar** | `config/config.yaml` | `config/notifications.yaml` | 알림 설정 분리 |
| **PriceRadar** | `config/config.yaml` | `config/notifications.yaml` | 알림 설정 분리 |

> `notifications.yaml`은 알림 기능이 있는 4개 레포(Home, Benefit, Trend, Price)에만 존재.

## ANTI-PATTERNS

- DuckDB 파일을 reports/ 안에 두지 말 것 (data/ 사용)
- .env 파일 커밋 금지 (.env.example만)
- collector에서 하드코딩 URL 금지 (categories YAML 사용)
- 블로킹 I/O 없이 timeout 필수
- 테스트 삭제로 통과시키지 말 것

## COMMANDS

```bash
# Standard repos
python main.py --category <name> --recent-days 7 --keep-days 90

# Advanced repos (HomeRadar, WineRadar, PriceRadar)
python main.py --mode once --report
python main.py --mode once --generate-report

# Tests (Advanced repos only)
pytest tests/unit -m unit
pytest tests/ -m "not network"
```
