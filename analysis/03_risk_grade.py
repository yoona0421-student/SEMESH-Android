# -*- coding: utf-8 -*-
"""
03단계: 시군구 전세사기 위험등급 산출

방법 설명은 docs/03_위험등급_방법론.md 에 자세히 있다. 이 파일은 그 문서의 ①~④를 순서대로 코드로 옮긴 것이다.

  ① 지표 계산      피해율(과거 피해) + 보증사고율(최근 사고), 분모는 둘 다 전세 계약 수
  ② 작은 표본 보정  경험적 베이즈: 표본이 작은 지역의 값을 전국 평균 쪽으로 당김
  ③ 종합 점수      두 지표를 0~100 백분위로 바꿔 0.5 : 0.5 평균 (+ 가중치 민감도 분석)
  ④ 등급          상위 20% 고위험 · 다음 30% 주의 · 나머지 50% 안전

실행: analysis 폴더에서  python 03_risk_grade.py
      (01 → 01b → 02 를 먼저 실행해 region_merged.csv 에 전세계약수가 들어 있어야 함)
결과:
  data/processed/region_risk.csv  ← 모든 계산 과정이 들어 있는 전체 표 (분석·검증용)
  output/region.csv               ← 안드로이드 앱 SQLite(regionTBL)에 넣을 표
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
P = BASE / "data" / "processed"
OUT_APP = BASE / "output" / "region.csv"

MONTHS_DAMAGE = 30          # 피해주택·전세계약 집계 기간: 2023.7 ~ 2025.12 = 30개월
W_DAMAGE, W_ACCIDENT = 0.5, 0.5
GRADE_CUTS = [("고위험", 0.20), ("주의", 0.30), ("안전", 0.50)]   # 위에서부터 비율
GRADE_SCORE_R = {"고위험": 20, "주의": 10, "안전": 0}            # 앱 안전진단의 지역 점수 R


# ════════════════════════════════════════════════════════════
# ② 경험적 베이즈 보정 (가장 중요한 함수)
# ════════════════════════════════════════════════════════════
def empirical_bayes(events, exposure):
    """
    events   : 지역별 사건 수 (피해주택 수, 보증사고 수)
    exposure : 지역별 노출량 = 분모 (전세 계약 수)

    돌려주는 것: (보정된 비율, 전국 평균 p, 가상 계약 수 m)

    [계산 순서] — Marshall(1991)의 적률추정법
      1) 전국 평균 p = 전체 사건 ÷ 전체 계약
      2) 지역별 비율이 p에서 얼마나 퍼져 있는지(분산 s2)를 계약 수로 가중해서 구한다.
      3) 그중 '표본이 작아서 우연히 생기는 퍼짐'(= p ÷ 평균 계약 수)을 뺀다.
         → 남은 것 A가 '진짜 지역 차이'의 크기
      4) 가상 계약 수 m = p ÷ A
         진짜 지역 차이(A)가 클수록 m이 작아져서 각 지역 값을 더 믿는다.
      5) 보정 비율 = (사건 + m × p) ÷ (계약 + m)
    """
    x = events.astype(float)
    n = exposure.astype(float)
    has = n > 0                                  # 계약이 0건인 지역은 비율을 계산할 수 없음

    p = x[has].sum() / n[has].sum()                          # 1) 전국 평균
    rate = (x / n).where(has)
    s2 = (n[has] * (rate[has] - p) ** 2).sum() / n[has].sum()  # 2) 계약 수로 가중한 분산
    A = s2 - p / n[has].mean()                               # 3) 우연한 퍼짐 빼기
    A = max(A, 1e-12)                            # 음수면 '진짜 차이가 거의 없음' → 아주 작은 양수로
    m = p / A                                                # 4) 가상 계약 수

    eb = (x + m * p) / (n + m)                               # 5) 보정
    # 계약이 0건인 지역은 비율을 판단할 근거가 없으므로 전국 평균으로 둔다.
    # (이렇게 하지 않으면 분모 0 + 사건 몇 건 때문에 값이 크게 튀어 1위가 되는 오류가 생긴다)
    eb = eb.where(has, p)
    return eb, p, m


def percentile(series):
    """값이 클수록 높은 0~100 백분위. 같은 값은 같은 점수(평균 순위)"""
    return series.rank(pct=True, method="average") * 100


def grade_by_quantile(score):
    """종합점수 순위로 상위 20% 고위험, 다음 30% 주의, 나머지 안전"""
    order = score.rank(ascending=False, method="first")      # 1등 = 가장 위험
    n = len(score)
    high_end = round(n * GRADE_CUTS[0][1])
    mid_end = high_end + round(n * GRADE_CUTS[1][1])
    return pd.Series(np.select([order <= high_end, order <= mid_end], ["고위험", "주의"], "안전"),
                     index=score.index)


def compute(df, w_damage=W_DAMAGE, w_accident=W_ACCIDENT):
    """region_merged 표를 받아 지표·보정·점수·등급 열을 붙여 돌려준다."""
    df = df.copy()

    # ── ① 지표 ────────────────────────────────────────────
    # 피해율: 30개월 누적 피해주택 ÷ 30개월 누적 전세계약 × 1,000
    df["피해율_원값"] = (df["피해주택_누적"] / df["전세계약수"] * 1000).where(df["전세계약수"] > 0)
    # 보증사고율: 월평균 보증사고(최근 3개월 평균) ÷ 월평균 전세계약 × 1,000
    df["월평균_전세계약"] = df["전세계약수"] / MONTHS_DAMAGE
    df["보증사고율_원값"] = (df["사고건수"] / df["월평균_전세계약"] * 1000).where(df["전세계약수"] > 0)

    # ── ② 보정 ────────────────────────────────────────────
    eb_d, p_d, m_d = empirical_bayes(df["피해주택_누적"], df["전세계약수"])
    eb_a, p_a, m_a = empirical_bayes(df["사고건수"], df["월평균_전세계약"])
    df["피해율_보정"] = eb_d * 1000
    df["보증사고율_보정"] = eb_a * 1000
    params = {"피해율": (p_d * 1000, m_d), "보증사고율": (p_a * 1000, m_a)}

    # ── ③ 종합 점수 ───────────────────────────────────────
    df["피해율_백분위"] = percentile(df["피해율_보정"])
    df["보증사고율_백분위"] = percentile(df["보증사고율_보정"])
    df["종합점수"] = w_damage * df["피해율_백분위"] + w_accident * df["보증사고율_백분위"]

    # ── ④ 등급 ────────────────────────────────────────────
    df["등급"] = grade_by_quantile(df["종합점수"])
    df["순위"] = df["종합점수"].rank(ascending=False, method="min").astype(int)
    return df, params


def sensitivity(df):
    """가중치를 바꿔도 고위험 지역이 비슷하게 나오는가?"""
    base, _ = compute(df)
    base_high = set(base.loc[base["등급"] == "고위험", "지역코드"])
    rows = []
    for wd, wa in [(0.7, 0.3), (0.3, 0.7)]:
        alt, _ = compute(df, wd, wa)
        alt_high = set(alt.loc[alt["등급"] == "고위험", "지역코드"])
        rows.append({"가중치(피해:사고)": f"{wd}:{wa}",
                     "고위험 겹침": f"{len(base_high & alt_high)}/{len(base_high)}",
                     "종합점수 순위상관": round(base["종합점수"].corr(alt["종합점수"], method="spearman"), 3)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # 테스트용으로 다른 입력 파일을 줄 수 있게 함:  python 03_risk_grade.py 다른파일.csv
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else P / "region_merged.csv"
    df = pd.read_csv(src, dtype={"지역코드": str})
    if "전세계약수" not in df.columns:
        raise SystemExit("region_merged.csv에 전세계약수가 없습니다. 01b 수집을 마치고 02_merge.py를 다시 실행하세요.")

    risk, params = compute(df)

    # ── 결과 확인 ─────────────────────────────────────────
    for name, (p, m) in params.items():
        print(f"[② 보정] {name}: 전국 평균 {p:.3f} (1,000건당), 가상 계약 수 m = {m:,.0f}")

    print("\n[② 보정 효과] 원값 기준 상위 5개 → 보정 후")
    top_raw = risk.sort_values("보증사고율_원값", ascending=False).head(5)
    print(top_raw[["시도", "시군구", "사고건수", "월평균_전세계약", "보증사고율_원값", "보증사고율_보정"]]
          .round(2).to_string(index=False))

    print("\n[④ 등급] 지역 수:", risk["등급"].value_counts().reindex(["고위험", "주의", "안전"]).to_dict())
    print("\n[종합 상위 15]")
    print(risk.sort_values("순위").head(15)[["순위", "시도", "시군구", "피해주택_누적", "전세계약수",
                                            "피해율_보정", "보증사고율_보정", "종합점수", "등급"]]
          .round(2).to_string(index=False))

    print("\n[③ 민감도 분석]")
    print(sensitivity(df).to_string(index=False))

    rho = risk["피해율_보정"].corr(risk["보증사고율_보정"], method="spearman")
    print(f"\n[⑤-3] 피해율 vs 보증사고율 순위상관: {rho:.3f}")

    # ── 저장 ─────────────────────────────────────────────
    if src == P / "region_merged.csv":
        risk.to_csv(P / "region_risk.csv", index=False, encoding="utf-8-sig")
        OUT_APP.parent.mkdir(exist_ok=True)
        app = risk[["지역코드", "시도", "시군구", "등급", "순위", "종합점수",
                    "피해주택_누적", "피해율_보정", "사고건수", "사고율", "보증사고율_보정"]].copy()
        app["지역점수R"] = app["등급"].map(GRADE_SCORE_R)
        app.round(3).to_csv(OUT_APP, index=False, encoding="utf-8-sig")
        print(f"\n저장 → {P / 'region_risk.csv'}, {OUT_APP}")
    else:
        print("\n(테스트 입력이라 결과 파일은 저장하지 않음)")
