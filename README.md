# Radar Project Template

WineRadar에서 가져온 경량 레이더 템플릿입니다. 카테고리 YAML만 만들고 `python main.py --category <name>`를 실행하면 RSS 수집 → 키워드 태깅 → DuckDB 저장 → HTML 리포트 생성까지 한 번에 처리합니다.

## 빠른 시작
1. `config/categories/_template.yaml`을 복사해 새 YAML을 만들고 소스/키워드를 채웁니다. (예시: `coffee.yaml`)
2. 가상환경을 만들고 의존성을 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```
3. 실행:
   ```bash
   cd Radar-Template
   python main.py --category coffee --recent-days 7
   # 리포트: reports/coffee_report.html
   ```
   주요 옵션: `--per-source-limit 20`, `--recent-days 5`, `--keep-days 60`, `--timeout 20`, `--config path/to/config.yaml`, `--categories-dir path/to/yamls`.

## GitHub Actions & GitHub Pages
- 워크플로: `.github/workflows/radar-crawler.yml`
  - 스케줄: 매일 00:00 UTC (KST 09:00), 수동 실행도 지원.
  - 환경 변수 `RADAR_CATEGORY`를 프로젝트에 맞게 수정하세요.
  - 리포트 배포 디렉터리: `reports` → `gh-pages` 브랜치로 배포.
  - DuckDB 경로: `data/radar_data.duckdb` (Pages에 올라가지 않음). 아티팩트로 7일 보관.
- 설정 방법:
  1) 저장소 Settings → Pages에서 `gh-pages` 브랜치를 선택해 활성화  
  2) Actions 권한을 기본값으로 두거나 외부 PR에서도 실행되도록 설정  
  3) 워크플로 파일의 `RADAR_CATEGORY`를 원하는 YAML 이름으로 변경

## 동작 방식
- **수집**: 카테고리 YAML에 정의된 RSS만 지원합니다. 실행 시 DuckDB에 적재하고 보존 기간(`keep_days`)을 적용합니다.  
- **분석**: 엔티티별 키워드 단순 매칭. 매칭된 키워드를 리포트에 칩으로 표시합니다.  
- **리포트**: `reports/<category>_report.html`을 생성하며, 최근 N일(기본 7일) 기사와 엔티티 히트 카운트, 수집 오류를 표시합니다.

## 기본 경로
- DB: `data/radar_data.duckdb`
- 리포트 출력: `reports/`

## 디렉터리 구성
```
Radar-Template/
  main.py                 # CLI 엔트리포인트
  requirements.txt        # 의존성 (DuckDB 포함)
  config/
    config.yaml           # DB/리포트 경로 설정
    categories/           # 카테고리 정의
      _template.yaml      # 새 토픽 템플릿
      coffee.yaml         # 커피 예시
  radar/
    collector.py          # RSS 수집
    analyzer.py           # 키워드 태깅
    reporter.py           # HTML 렌더링
    storage.py            # DuckDB 저장/정리
    config_loader.py      # YAML 로더
    models.py             # 데이터 클래스
  .github/workflows/      # GitHub Actions (crawler + Pages 배포)
```

## 새 레이더 만들기
1. `_template.yaml`을 복사해 `mytopic.yaml`을 만들고 피드/키워드를 채웁니다.  
2. `python main.py --category mytopic` 실행.  
3. `reports/mytopic_report.html`을 열어 확인하고 키워드를 다듬어 보완합니다.

필요하면 collector/analyzer를 확장해 API 연동이나 NLP를 추가하세요.
