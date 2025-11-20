# Radar Project Template

WineRadar에서 뽑아온 경량 스타터 킷입니다. 카테고리 YAML만 만들고 `python main.py --category <name>`를 실행하면 RSS 수집 → 키워드 태깅 → DuckDB 저장 → HTML 리포트까지 한 번에 생성됩니다.

## 빠른 시작
1) `config/categories/`에 새 YAML을 만듭니다. `_template.yaml`을 복사해 소스/키워드를 채우세요. 샘플: `coffee.yaml`.  
2) (가상환경 권장) 의존성 설치: `pip install -r requirements.txt`  
3) 실행:
```bash
cd Radar-Template
python main.py --category coffee --recent-days 7
# 리포트: reports/coffee_report.html
```
주요 옵션: `--per-source-limit 20`, `--recent-days 5`, `--keep-days 60`, `--timeout 20`, `--config path/to/config.yaml`, `--categories-dir path/to/yamls`.

## 동작 방식
- **수집**: 카테고리 YAML에 정의된 RSS만 지원합니다. 실행 시 DuckDB에 적재하며 보존 기간(`keep_days`)을 적용합니다.  
- **분석**: 엔티티별 키워드 단순 매칭. 히트된 키워드를 리포트에 칩으로 표시합니다.  
- **리포트**: `reports/<category>_report.html`을 생성하며, 최근 N일(기본 7일) 기사와 엔티티 히트 카운트, 수집 오류를 표시합니다.

## 구성
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
```

## 새 레이더 만들기
1) `_template.yaml`을 복사해 `mytopic.yaml`을 만들고 피드/키워드를 채웁니다.  
2) `python main.py --category mytopic` 실행.  
3) `reports/mytopic_report.html`을 열어 확인하고 키워드를 다듬어 보완합니다.

필요하면 collector/analyzer를 확장해 API 연동이나 NLP를 추가하세요.
