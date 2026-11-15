# -*- coding: utf-8 -*-
"""
05단계: 서울 동(洞) 단위 전세사기 피해율

[왜 이 단계가 필요한가?]
  전세 계약은 '서울 강서구'가 아니라 '강서구 화곡동'처럼 동 단위로 한다.
  03단계의 시군구 등급만으로는 "서울 안에서도 정확히 어디가 위험한가?",
  "서울이라서 무조건 위험한 건가?"에 답할 수 없다. → 서울만이라도 동 단위로 내려가 본다.
  (HUG가 동 단위 피해 데이터를 공개한 곳은 서울뿐이라, 다른 지역은 할 수 없다)

[가장 큰 문제: 두 데이터의 '동'이 다르다]
  - HUG 피해주택 : 행정동  (화곡2동, 화곡8동, 보라매동 …)  ← 주민센터 기준
  - 국토부 전월세 : 법정동  (화곡동, 봉천동 …)            ← 계약서·등기부에 적히는 주소
  행정동 여러 개가 법정동 하나에 들어가거나(화곡1~8동 → 화곡동),
  이름이 완전히 다르다(관악구 보라매동 → 봉천동).
  → 행정동을 법정동 기준 '동 그룹'으로 묶어서 두 데이터를 맞춘다.
  법정동 기준으로 묶는 것이 오히려 사용자에게 맞다. 계약서에 적히는 주소가 법정동이기 때문이다.

[계산]
  ① 동 그룹별 피해주택 수(2023.7~2025.12)와 전세 계약 수(같은 기간)를 센다.
  ② 피해율 = 피해주택 ÷ 전세 계약 1,000건
  ③ 작은 표본 보정: 03단계와 같은 경험적 베이즈인데, 당기는 방향이 '전국 평균'이 아니라
     '그 동이 속한 구의 평균'이다. 계약이 적은 동은 "잘 모르니 같은 구의 다른 동과 비슷하다고 보자".
  ④ 서울 안에서 순위를 매기고, 등급은 전국 평균과 비교한 배수로 나눈다
     (고위험: 2배 이상, 주의: 1~2배, 안전: 전국 평균보다 낮음).
     → "서울이 위험한가?"를 '서울 전체'가 아니라 '어느 동이 전국 평균보다 몇 배인가'로 답한다.

  ※ 보증사고 데이터는 시군구까지만 있어서, 동 단위는 피해율 하나로만 본다.

실행: analysis 폴더에서  python 05_seoul_dong.py   (03_risk_grade.py를 먼저 실행)
결과:
  data/processed/seoul_dong_risk.csv ← 계산 과정이 다 들어 있는 표
  output/seoul_dong.csv              ← 앱에 넣을 표
"""

import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
P = BASE / "data" / "processed"
OUT_APP = BASE / "output" / "seoul_dong.csv"

SEOUL_FILE = RAW / "HUG_서울_행정동별_경공매지원_피해주택_20261029.csv"
PERIOD = (202307, 202512)       # 전월세 수집 기간과 맞춘다 (03단계와 같은 30개월)
NATIONAL_RATE = None            # 전국 평균 피해율은 03단계 결과에서 읽어 온다

# ── 이름 규칙으로 안 맞는 행정동 → 법정동 그룹 (직접 만든 대응표) ──────────────
# 근거: 서울시 각 구청 '행정동·법정동 현황'. 행정동 하나가 법정동 여러 개에 걸치면
#      주민 대부분이 속한 법정동으로 보낸다.
ADM_TO_GROUP = {
    ("종로구", "청운효자동"): "청운동",
    ("중구", "다산동"): "신당동", ("중구", "약수동"): "신당동",
    ("중구", "청구동"): "신당동", ("중구", "동화동"): "신당동",
    ("성동구", "왕십리2동"): "왕십리동", ("성동구", "왕십리도선동"): "왕십리동",
    ("성북구", "월곡1동"): "월곡동", ("성북구", "월곡2동"): "월곡동",
    ("강북구", "삼양동"): "미아동", ("강북구", "송중동"): "미아동",
    ("강북구", "송천동"): "미아동", ("강북구", "삼각산동"): "미아동",
    ("강북구", "인수동"): "수유동",
    ("서대문구", "충현동"): "충정로동",
    ("마포구", "서강동"): "창전동",
    ("강서구", "발산1동"): "내발산동", ("강서구", "우장산동"): "화곡동",
    ("구로구", "수궁동"): "궁동",
    ("영등포구", "여의동"): "여의도동",
    ("송파구", "오륜동"): "방이동", ("송파구", "위례동"): "장지동",
    # 관악구는 2008년에 행정동 이름을 모두 바꿨다. 법정동은 봉천동·신림동·남현동 3개뿐.
    **{("관악구", d): "봉천동" for d in
       ["보라매동", "청림동", "성현동", "행운동", "낙성대동", "청룡동", "은천동", "중앙동", "인헌동"]},
    **{("관악구", d): "신림동" for d in
       ["서원동", "신원동", "서림동", "신사동", "신림동", "난향동", "조원동", "대학동", "삼성동", "미성동", "난곡동"]},
}

# 법정동 쪽에서도 하나로 묶어야 하는 것 (행정동 하나가 여러 법정동에 걸쳐 있는 경우)
LEG_TO_GROUP = {
    ("성동구", "상왕십리동"): "왕십리동", ("성동구", "하왕십리동"): "왕십리동",
    ("성동구", "도선동"): "왕십리동", ("성동구", "홍익동"): "왕십리동",
    ("성북구", "상월곡동"): "월곡동", ("성북구", "하월곡동"): "월곡동",
    ("구로구", "온수동"): "궁동",
}


def adm_root(name):
    """행정동 이름 → 법정동 기준 이름 (규칙)
    화곡2동 → 화곡동, 화곡본동 → 화곡동, 면목3·8동 → 면목동,
    금호1가동 → 금호동, 성수2가3동 → 성수동, 종로1·2·3·4가동 → 종로동"""
    name = re.sub(r"[\d·]+가\d*동$", "동", name)   # '○가동', '○가○동'
    name = re.sub(r"[\d·]+동$", "동", name)        # 숫자 붙은 동
    name = re.sub(r"본동$", "동", name)            # 본동
    return name


def leg_root(name):
    """법정동 이름 → 같은 기준 이름 (규칙)
    성수동1가 → 성수동, 종로5가 → 종로동, 명륜2가 → 명륜동"""
    name = re.sub(r"\d+가$", "", name)
    return name if name.endswith("동") else name + "동"


def to_group(gu, name):
    """행정동이든 법정동이든 → 동 그룹 이름 하나로.
    HUG 파일에도 '하월곡동', '영등포동2가'처럼 법정동 이름이 섞여 있어서(실행해 보고 발견)
    두 데이터 모두 이 함수 하나로 처리한다.
      1) 직접 만든 대응표에 있으면 그것을 쓰고
      2) 없으면 규칙(adm_root → leg_root)으로 바꾼 뒤
      3) 바꾼 이름이 법정동 묶음 표에 있으면 한 번 더 묶는다"""
    if (gu, name) in ADM_TO_GROUP:
        return ADM_TO_GROUP[(gu, name)]
    if (gu, name) in LEG_TO_GROUP:
        return LEG_TO_GROUP[(gu, name)]
    root = leg_root(adm_root(name))
    return LEG_TO_GROUP.get((gu, root), root)


def empirical_bayes_toward(events, exposure, prior):
    """03단계의 경험적 베이즈와 같은 식. 다른 점은 당기는 목표가 지역마다 다르다는 것(prior = 구 평균).
       보정 비율 = (사건 + m × 구 평균) ÷ (계약 + m)"""
    x, n, pr = events.astype(float), exposure.astype(float), prior.astype(float)
    has = n > 0
    rate = (x / n).where(has)
    # 구 평균에서 얼마나 벗어나 있나(분산) − 표본이 작아서 우연히 생기는 퍼짐 = 진짜 동네 차이
    p_bar = (n[has] * pr[has]).sum() / n[has].sum()
    s2 = (n[has] * (rate[has] - pr[has]) ** 2).sum() / n[has].sum()
    A = max(s2 - p_bar / n[has].mean(), 1e-12)
    m = p_bar / A
    eb = ((x + m * pr) / (n + m)).where(has, pr)    # 계약 0건인 동은 구 평균으로
    return eb, m


def load_damage():
    """HUG 서울 행정동 피해주택 → 기간 맞추고 동 그룹으로 묶기"""
    s = pd.read_csv(SEOUL_FILE, encoding="utf-8-sig")
    ym = s["연"] * 100 + s["월"]
    s = s[(ym >= PERIOD[0]) & (ym <= PERIOD[1])]
    d = s.groupby(["시군구", "읍면동"], as_index=False)["경공매지원건수"].sum()
    d["동그룹"] = [to_group(g, a) for g, a in zip(d["시군구"], d["읍면동"])]
    return d


def load_contracts(gu_codes):
    """국토부 전월세(서울) → 전세(월세 0원)만, 법정동을 동 그룹으로 묶어 건수 세기"""
    files = [f for f in glob.glob(str(RAW / "molit_rent" / "*.csv.gz")) if "alias" not in f]
    r = pd.concat([pd.read_csv(f, dtype={"지역코드": str}, usecols=["지역코드", "법정동", "월세"])
                   for f in files])
    r = r[r["지역코드"].isin(gu_codes) & (r["월세"] == 0)]
    r["시군구"] = r["지역코드"].map(gu_codes)
    r["동그룹"] = [to_group(g, l) for g, l in zip(r["시군구"], r["법정동"])]
    return r.groupby(["지역코드", "시군구", "동그룹"]).size().rename("전세계약수").reset_index()


if __name__ == "__main__":
    region = pd.read_csv(P / "region_risk.csv", dtype={"지역코드": str})
    seoul = region[region["시도"] == "서울"]
    gu_codes = dict(zip(seoul["지역코드"], seoul["시군구"]))     # '11500' → '강서구'
    national = region["피해주택_누적"].sum() / region["전세계약수"].sum() * 1000

    dmg = load_damage()
    con = load_contracts(gu_codes)

    # ── 확인 1: 대응표로 묶은 동 그룹이 전월세 데이터에 모두 있나? ──────────────
    groups = dmg.groupby(["시군구", "동그룹"], as_index=False).agg(
        피해주택=("경공매지원건수", "sum"),
        포함_행정동=("읍면동", lambda x: "·".join(sorted(x))))
    df = con.merge(groups, on=["시군구", "동그룹"], how="outer")
    missing = df[df["전세계약수"].isna()]
    print(f"[확인] 피해는 있는데 전세 계약 데이터에 없는 동 그룹: {len(missing)}개")
    if len(missing):
        print(missing[["시군구", "동그룹", "포함_행정동", "피해주택"]].to_string(index=False))
    df["피해주택"] = df["피해주택"].fillna(0).astype(int)
    df["전세계약수"] = df["전세계약수"].fillna(0).astype(int)
    df["지역코드"] = df["시군구"].map({v: k for k, v in gu_codes.items()})
    df["포함_행정동"] = df["포함_행정동"].fillna("")

    # ── 확인 2: 묶는 과정에서 피해주택이 빠지지 않았나? ─────────────────────
    print(f"[확인] 피해주택 합계  원본 {dmg['경공매지원건수'].sum()}건  →  동 그룹 {df['피해주택'].sum()}건")

    # ── ① ② 피해율 ────────────────────────────────────────
    gu = df.groupby("시군구")[["피해주택", "전세계약수"]].sum()
    gu_rate = gu["피해주택"] / gu["전세계약수"]
    df["구_피해율"] = df["시군구"].map(gu_rate) * 1000
    df["피해율_원값"] = (df["피해주택"] / df["전세계약수"] * 1000).where(df["전세계약수"] > 0)

    # ── ③ 구 평균 쪽으로 보정 ──────────────────────────────
    eb, m = empirical_bayes_toward(df["피해주택"], df["전세계약수"], df["시군구"].map(gu_rate))
    df["피해율_보정"] = eb * 1000
    print(f"\n가상 계약 수 m = {m:.0f}건  (계약이 이보다 훨씬 적은 동은 구 평균 쪽으로 크게 당겨짐)")

    # ── ④ 순위·등급·전국 대비 ─────────────────────────────
    df["전국대비_배수"] = df["피해율_보정"] / national
    # 계약이 m보다 적은 동은 값의 절반 이상이 '구 평균'에서 온 것이다.
    # 예) 강서구 개화동: 피해 0건이지만 계약이 46건뿐이라 강서구 평균에 가깝게 나온다.
    #    앱에서는 "이 동은 자료가 적어 구 평균으로 추정"이라고 따로 표시한다.
    df["자료부족"] = df["전세계약수"] < m
    df["서울순위"] = df["피해율_보정"].rank(ascending=False, method="min").astype(int)
    # 등급 기준: 03단계(서울 안 상위 20%)와 다르게 '전국 평균의 몇 배인가'로 나눈다.
    #   서울 안에서 상위 20%로 자르면, 동의 63%가 피해 0건이라 전국 평균보다 낮은 동(예: 마곡동)까지
    #   '주의'가 되어 버린다. 동 단위 분석의 목적은 "서울이라서 위험한가?"에 근거를 대는 것이므로
    #   기준을 서울 바깥(전국 평균)에 둔다.
    #   고위험: 전국 평균의 2배 이상 / 주의: 1~2배 / 안전: 전국 평균보다 낮음
    k = len(df)
    df["등급"] = np.select([df["전국대비_배수"] >= 2, df["전국대비_배수"] >= 1], ["고위험", "주의"], "안전")
    df = df.sort_values("서울순위")

    # ── 결과 확인: 서울이 정말 위험한가? ──────────────────────
    seoul_rate = df["피해주택"].sum() / df["전세계약수"].sum() * 1000
    print(f"\n전국 평균 피해율 {national:.2f}  /  서울 전체 {seoul_rate:.2f}  (전세 1,000건당)")
    above = df[df["전국대비_배수"] >= 2]
    print(f"서울 동 그룹 {k}개 중 전국 평균의 2배 이상: {len(above)}개, "
          f"이 동들의 피해주택이 서울 전체의 {above['피해주택'].sum() / df['피해주택'].sum():.0%}")
    print("등급별 동 그룹 수:", df["등급"].value_counts().to_dict(),
          "/ 그중 자료부족:", df.loc[df["자료부족"], "등급"].value_counts().to_dict())
    zero = (df["피해주택"] == 0).sum()
    print(f"피해주택이 한 건도 없는 동 그룹: {zero}개 ({zero / k:.0%})")
    top10 = df.head(10)
    print(f"상위 10개 동 그룹이 서울 피해주택의 {top10['피해주택'].sum() / df['피해주택'].sum():.0%}를 차지")
    print("\n서울 동 그룹 위험 상위 15")
    print(df.head(15)[["서울순위", "시군구", "동그룹", "피해주택", "전세계약수",
                       "피해율_원값", "피해율_보정", "전국대비_배수", "자료부족"]].round(2).to_string(index=False))

    print("\n구별 요약: 같은 구 안에서도 동마다 얼마나 다른가 (보정 피해율 최고 / 최저)")
    spread = df[~df["자료부족"]].groupby("시군구")["피해율_보정"].agg(["max", "min", "count"])
    spread["구_피해율"] = gu_rate * 1000
    print(spread.sort_values("구_피해율", ascending=False).round(2).head(10).to_string())

    # ── 저장 ─────────────────────────────────────────────
    df.to_csv(P / "seoul_dong_risk.csv", index=False, encoding="utf-8-sig")
    app = df[["지역코드", "시군구", "동그룹", "포함_행정동", "등급", "서울순위", "피해주택",
              "전세계약수", "피해율_보정", "전국대비_배수", "자료부족"]].round(3)
    app.to_csv(OUT_APP, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: seoul_dong_risk.csv, output/seoul_dong.csv ({len(app)}개 동 그룹)")
