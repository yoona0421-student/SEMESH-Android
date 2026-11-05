# -*- coding: utf-8 -*-
"""
01단계: 원본 데이터 불러오기 → 분석하기 쉬운 표로 정리해서 저장

[이 단계에서 하는 일]
  raw/ 의 HUG 파일 3개는 엑셀 제목줄, 합계(소계) 행, 시트 여러 개가 섞여 있어서
  바로 분석하기 어렵다. 그래서 "한 행 = 한 지역" 모양의 깔끔한 표로 바꿔
  processed/ 폴더에 CSV로 저장한다.

[왜 단계를 나누나?]
  불러오기(01) → 합치기·계산(02) → 등급 매기기(03) 처럼 나눠두면
  중간 결과를 눈으로 확인할 수 있고, 틀린 곳이 생겨도 그 단계만 다시 고치면 된다.

실행: analysis 폴더에서  python 01_load_data.py
"""

from pathlib import Path   # 운영체제(Windows/Mac) 상관없이 파일 경로를 다루는 도구
import pandas as pd        # 표(DataFrame) 형태 데이터를 다루는 라이브러리

# ── 경로 설정 ───────────────────────────────────────────────
# __file__ = 지금 이 파이썬 파일의 위치. 여기를 기준으로 경로를 잡으면
# 어느 폴더에서 실행하든 같은 파일을 찾는다.
BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
OUT = BASE / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)   # 폴더가 없으면 만들기

ACCIDENT_FILE = RAW / "HUG_지역별_전세금반환보증_사고현황_20260831.xlsx"
SEOUL_FILE = RAW / "HUG_서울_행정동별_경공매지원_피해주택_20261029.csv"
DAMAGE_FILE = RAW / "HUG_경공매지원_피해주택_소재지_시군구_20251231.xlsx"


# ════════════════════════════════════════════════════════════
# 1) 지역별 전세금반환보증 사고현황 (2026.8 기준, 최근 3개월 평균)
# ════════════════════════════════════════════════════════════
def load_accident():
    # 엑셀 위쪽 5줄은 제목·병합된 머리글이라 데이터가 아니다 → skiprows=5 로 건너뜀
    # 머리글이 여러 줄로 쪼개져 있어서 header=None 으로 읽고, 열 이름은 직접 붙인다.
    df = pd.read_excel(ACCIDENT_FILE, skiprows=5, header=None)
    df.columns = ["지역코드", "시도", "시군구", "사고건수", "사고금액", "사고율"]

    # '소계' 행은 전국·수도권·시도 단위 합계라서 시군구 분석에 섞이면 안 된다.
    # (예: '서울 소계 183건'이 강서구와 같은 줄에 있으면 서울 전체가 한 지역처럼 계산됨)
    df = df[df["시군구"] != "소계"].copy()

    # 지역코드: 엑셀에서 숫자(11110.0)로 읽히므로 5자리 문자열('11110')로 바꾼다.
    # 코드는 계산하는 값이 아니라 '이름표'라서 문자열이 맞다. 나중에 지도(GeoJSON)와 연결할 때 쓴다.
    df["지역코드"] = df["지역코드"].astype(int).astype(str).str.zfill(5)

    # 숫자 열은 확실히 숫자형으로 (혹시 빈칸이 있으면 0으로)
    for col in ["사고건수", "사고금액", "사고율"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df.reset_index(drop=True)


# ════════════════════════════════════════════════════════════
# 2) 서울 행정동별 경공매지원 피해주택 (2023.7 ~ 2026.10, 월별)
# ════════════════════════════════════════════════════════════
def load_seoul():
    # 파일이 'UTF-8 BOM' 형식이라 encoding='utf-8-sig' 로 읽어야
    # 첫 번째 열 이름 앞에 이상한 글자(﻿)가 붙지 않는다.
    df = pd.read_csv(SEOUL_FILE, encoding="utf-8-sig")
    df = df.rename(columns={"연": "연도", "읍면동": "행정동", "경공매지원건수": "피해건수"})
    return df


# ════════════════════════════════════════════════════════════
# 3) 시군구별 경공매지원 피해주택 소재지 (2023.7 ~ 2025.3, 시트 3개)
# ════════════════════════════════════════════════════════════
def load_damage():
    # sheet_name=None → 모든 시트를 {시트이름: 표} 딕셔너리로 한 번에 읽는다.
    sheets = pd.read_excel(DAMAGE_FILE, sheet_name=None)

    frames = []
    for sheet_name, df in sheets.items():
        df.columns = ["지역", "피해주택수"]
        df["기간"] = sheet_name          # 어느 시트(연도)에서 왔는지 표시해 둔다
        frames.append(df)

    # 시트 3개를 위아래로 이어 붙여 하나의 표로 만든다.
    df = pd.concat(frames, ignore_index=True)

    # '서울 강서구', '경기 수원시 장안구' 처럼 시도와 시군구가 한 칸에 있다.
    # 첫 단어만 시도, 나머지는 시군구로 나눈다. (n=1 → 첫 공백에서 한 번만 자름)
    df[["시도", "시군구"]] = df["지역"].str.split(" ", n=1, expand=True)
    df["피해주택수"] = pd.to_numeric(df["피해주택수"], errors="coerce").fillna(0).astype(int)
    return df[["기간", "시도", "시군구", "피해주택수"]]


# ════════════════════════════════════════════════════════════
# 실행 부분: 세 데이터를 불러와서 확인하고 저장
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    accident = load_accident()
    seoul = load_seoul()
    damage = load_damage()

    # 저장: utf-8-sig 로 저장하면 엑셀에서 열어도 한글이 깨지지 않는다.
    accident.to_csv(OUT / "accident_2026_08.csv", index=False, encoding="utf-8-sig")
    seoul.to_csv(OUT / "seoul_dong_monthly.csv", index=False, encoding="utf-8-sig")
    damage.to_csv(OUT / "damage_sigungu_by_period.csv", index=False, encoding="utf-8-sig")

    # ── 눈으로 확인하기 ──
    # 데이터는 '불러왔다'로 끝내지 말고 행 수·합계·이상한 값을 꼭 확인한다.
    print("[1] 보증사고 현황 (2026.8)")
    print(f"  시군구 수: {len(accident)}개, 전국 사고건수 합: {accident['사고건수'].sum():.0f}건")
    print(f"  사고건수 0건인 지역: {(accident['사고건수'] == 0).sum()}개")
    print(f"  사고 1~2건뿐인데 사고율 10% 이상인 지역: "
          f"{((accident['사고건수'] <= 2) & (accident['사고율'] >= 10)).sum()}개  ← 표본이 작아 생기는 착시")

    print("\n[2] 서울 행정동 피해주택 (월별)")
    print(f"  {seoul['연도'].min()}.{seoul.loc[seoul['연도'].idxmin(), '월']} ~ "
          f"{seoul['연도'].max()}.{seoul[seoul['연도'] == seoul['연도'].max()]['월'].max()}, "
          f"구 {seoul['시군구'].nunique()}개 · 동 {seoul['행정동'].nunique()}개, 총 {seoul['피해건수'].sum()}건")

    print("\n[3] 시군구 피해주택 (기간별)")
    print(damage.groupby("기간")["피해주택수"].agg(["count", "sum"]).rename(columns={"count": "지역수", "sum": "피해주택합"}))

    print(f"\n저장 완료 → {OUT}")
