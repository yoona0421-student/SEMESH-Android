# SEMESH for Android

내 위치의 전세사기 위험을 지도로 확인하는 앱
(백석대학교 첨단IT학부 · 안드로이드 프로그래밍 · 20234150 정윤아)

2026년 1학기 빅데이터 프로젝트에서 만든 웹 플랫폼 **SEMESH**를
HUG 최신 데이터로 다시 분석하고 Android(Kotlin) 앱으로 옮긴 프로젝트입니다.

## 폴더 구성

| 폴더 | 내용 |
|---|---|
| `analysis/` | Python 데이터 분석 (HUG 데이터 → 시군구 위험등급 → `region.csv`, `map.html`) |
| `analysis/notebooks/` | 같은 분석을 셀 단위로 나눠 중간 결과·그래프를 보는 Jupyter 노트북 (VS Code에서 열기) |
| `analysis/data/raw/` | 내려받은 원본 데이터 (수정하지 않음) |
| `analysis/data/processed/` | 전처리 결과 |
| `analysis/output/` | 앱에 넣을 결과물 (`region.csv`, `map.html`, 그래프) |
| `android/` | Android Studio 프로젝트 (Empty Views Activity, Kotlin) |
| `paper/` | 논문 원고와 그림 |
| `docs/` | 발표자료, 진행 기록, [위험등급 방법론](docs/03_위험등급_방법론.md) |

## 앱 구성

- **MainActivity**: GPS로 내 지역 위험도 카드, 메뉴 3개
- **MapActivity**: 시군구 위험등급 지도(WebView + Folium), 지역 터치 시 피해 건수 표시
- **DiagnosisActivity**: 안전 진단 4단계 (기본 정보 → 자가진단 → 계약서 체크 → 결과)
- **GuideActivity**: 전세사기 유형, 계약 전 4단계 점검, 법률·정부 지원

## 데이터 출처

- 주택도시보증공사(HUG), 경공매지원서비스 신청자의 전세사기피해주택 소재지(시군구), 공공데이터포털
  - 주의: 전체 피해자가 아니라 경공매 지원을 **신청한** 피해자의 주택 소재지 데이터입니다.
- 주택도시보증공사(HUG), 지역별 전세금반환보증 사고현황(2026.8), 공공데이터포털
- 국토교통부, 아파트·연립다세대·단독다가구·오피스텔 전월세 실거래가 API (2023.7~2025.12)
- 시군구 경계: 통계청 SGIS 행정동 경계(공공누리 제1유형) 가공본 [vuski/admdongkor](https://github.com/vuski/admdongkor) ver20260401, CC BY 4.0
- 배경 지도: © OpenStreetMap contributors

## 일정 (2026.11.5 ~ 12.1, 최종 마감 12/2)

> 2026-11-15 변경: 최종 마감이 12월 2일로 정해져 모든 작업을 **12월 1일까지** 끝내도록 일정을 앞당김.

| 기간 | 할 일 | 상태 |
|---|---|---|
| 11/5 ~ 11/15 | 최신 HUG 데이터 수집, 전처리, 위험등급 산출, 지도(map.html)·region.csv 생성, 앱 화면 4개 틀, 가이드 | 완료 |
| 11/16 ~ 11/20 | 완성된 map.html을 앱에 넣기, region.csv → SQLite(regionTBL) 적재, WebView 연결 | |
| 11/21 ~ 11/25 | GPS로 내 시군구 찾기 → 카드·지도 표시, 안전 진단 판정 기준 확정 | |
| 11/26 ~ 11/29 | 디자인 다듬기, 에뮬레이터·실기기 테스트, 가이드 정보 재확인 | |
| 11/30 ~ 12/1 | 최종 점검, 발표·전시 준비 | |
