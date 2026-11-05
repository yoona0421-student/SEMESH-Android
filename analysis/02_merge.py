# -*- coding: utf-8 -*-
"""
02단계: 지역 이름 통일(주소 정규화) → 지역코드로 데이터 합치기

[문제]
  같은 지역이 파일마다 다르게 적혀 있다.
    보증사고 파일 : '서울 강서구'    '경기 수원장안구'   '세종 세종시'
    피해주택 파일 : '서울시 강서구'  '수원시 장안구'     '세종시'(시군구 칸 비어 있음)
  이름이 한 글자라도 다르면 컴퓨터는 다른 지역으로 본다. → 합치면 빈칸이 생긴다.

[해결 전략]
  1) 기준표 정하기: 보증사고 파일의 256개 시군구 + 5자리 지역코드를 '정답 목록'으로 쓴다.
     (지역코드는 국토부 실거래가 API, 지도 GeoJSON과도 같은 코드라서 이후 연결이 쉽다)
  2) 피해주택 파일의 이름을 규칙에 따라 기준표 모양으로 바꾼다.
  3) 바꾼 이름으로 지역코드를 찾아 붙이고, 지역코드를 열쇠(key)로 파일들을 합친다.
  4) 못 찾은 지역이 0개인지, 합치기 전후 피해주택 합계가 같은지 꼭 확인한다.

실행: analysis 폴더에서  python 02_merge.py   (01_load_data.py를 먼저 실행해야 함)
결과: data/processed/region_merged.csv  ← 03단계(위험등급)에서 사용
"""

from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
P = BASE / "data" / "processed"

# ── 정규화 규칙에 쓰는 표 ─────────────────────────────────────
# 광역시·특별시: 피해주택 파일은 '서울시', 기준표는 '서울'
METRO = {"서울시": "서울", "부산시": "부산", "대구시": "대구", "인천시": "인천",
         "광주시": "광주", "대전시": "대전", "울산시": "울산", "세종시": "세종"}

# 원본의 오타. 근거: '서북구'가 있는 시는 천안시뿐이다.
TYPO = {"선안시": "천안시"}

# 시군구 칸이 비어 있는 행 → 시 자체가 하나의 지역
WHOLE_CITY = {"세종시": ("세종", "세종시"), "제주시": ("제주", "제주시")}

# 기간 이름 정리. 01단계 확인 결과 '2025년(~25.3.)' 시트는 실제로 2025년 12월까지라서 이름을 바로잡는다.
PERIOD = {"2023년(23.7.~)": "2023", "2024년": "2024", "2025년(~25.3.)": "2025"}


def normalize(sido, sgg):
    """피해주택 파일의 (시도, 시군구) → 기준표 모양의 (시도, 시군구)

    예) ('서울시', '강서구')  → ('서울', '강서구')
        ('수원시', '장안구')  → (None, '수원장안구')   ← 도 이름은 모르므로 None, 나중에 이름으로 찾음
        ('세종시', NaN)      → ('세종', '세종시')
    """
    sido = TYPO.get(sido, sido)

    if pd.isna(sgg):                       # 시군구 칸이 빈 행
        return WHOLE_CITY[sido]

    if sido in METRO:                      # 광역시: '서울시' → '서울'
        return METRO[sido], sgg

    if sido.endswith("시"):                # '수원시 장안구'처럼 도 없이 시부터 적힌 행
        # 기준표는 일반구를 '수원장안구'처럼 '시'를 빼고 붙여 쓴다
        return None, sido[:-1] + sgg

    return sido, sgg                       # '경기 가평군'처럼 이미 맞는 행


def attach_code(df, master):
    """정규화한 이름에 지역코드를 붙인다.

    1순위: 시도 + 시군구가 둘 다 맞는 행
    2순위: 시군구 이름이 전국에 하나뿐이면 이름만으로 찾기
           (예: '수원장안구'는 전국에 하나 → 경기로 확정)
           → 원본의 시도가 틀린 행('강원 가평군', '전남 익산시' 등)도 여기서 바로잡힌다.
    '중구', '동구', '고성군'처럼 여러 시도에 있는 이름은 2순위로 찾지 않는다 (잘못 붙을 수 있으므로).
    """
    by_both = {(r.시도, r.시군구): r.지역코드 for r in master.itertuples()}
    name_count = master["시군구"].value_counts()
    by_name = {r.시군구: (r.지역코드, r.시도) for r in master.itertuples()
               if name_count[r.시군구] == 1}

    codes, fixed = [], []
    for r in df.itertuples():
        if (r.시도_정규, r.시군구_정규) in by_both:
            codes.append(by_both[(r.시도_정규, r.시군구_정규)])
        elif r.시군구_정규 in by_name:
            code, true_sido = by_name[r.시군구_정규]
            codes.append(code)
            if r.시도_정규 is not None:        # 원래 시도가 적혀 있었는데 틀린 경우만 기록
                fixed.append((r.시도_정규, r.시군구_정규, true_sido))
        else:
            codes.append(None)
    df["지역코드"] = codes
    return df, sorted(set(fixed))


if __name__ == "__main__":
    # ── 1) 기준표: 보증사고 파일 ─────────────────────────────
    acc = pd.read_csv(P / "accident_2026_08.csv", dtype={"지역코드": str})
    # 경기 화성시(41590)는 2026년 만세·효행·병점·동탄 4개 구로 나뉘었다. 보증사고 파일에는 '화성시' 행이
    # 0건으로 남아 있지만 실제 사고·피해·거래는 모두 구 코드에 있으므로, 빈 껍데기인 시 행은 뺀다.
    acc = acc[acc["지역코드"] != "41590"]
    master = acc[["지역코드", "시도", "시군구"]]
    print(f"[기준표] 시군구 {len(master)}곳")

    # ── 2) 피해주택 파일 이름 정규화 ─────────────────────────
    dmg = pd.read_csv(P / "damage_sigungu_by_period.csv")
    total_before = dmg["피해주택수"].sum()

    dmg[["시도_정규", "시군구_정규"]] = [normalize(s, g) for s, g in zip(dmg["시도"], dmg["시군구"])]
    dmg, fixed = attach_code(dmg, master)

    unmatched = dmg[dmg["지역코드"].isna()]
    print(f"[피해주택] {len(dmg)}행 → 지역코드 못 찾은 행: {len(unmatched)}개")
    if len(unmatched):
        print(unmatched[["기간", "시도", "시군구", "시도_정규", "시군구_정규"]].to_string())
    print("[원본 시도 오류를 이름으로 바로잡은 행]")
    for wrong, name, right in fixed:
        print(f"   {wrong} {name}  →  {right} {name}")

    # ── 3) 지역별·기간별 합계 (한 지역 = 한 행) ─────────────
    dmg["연도"] = dmg["기간"].map(PERIOD)
    damage_wide = (dmg.pivot_table(index="지역코드", columns="연도", values="피해주택수",
                                   aggfunc="sum", fill_value=0)
                      .add_prefix("피해주택_"))
    damage_wide["피해주택_누적"] = damage_wide.sum(axis=1)

    # 확인: 정규화 전후로 피해주택 합계가 같아야 한다 (행이 빠지거나 두 번 세지지 않았는지)
    total_after = damage_wide["피해주택_누적"].sum()
    assert total_before == total_after, f"합계 불일치 {total_before} vs {total_after}"
    print(f"[확인] 피해주택 합계 {total_before}건 = {total_after}건 ✔")

    # ── 4) 지역코드로 합치기 ─────────────────────────────────
    # how='left' → 기준표 256곳은 모두 남기고, 피해 기록이 없는 지역은 0건으로 채운다
    merged = master.merge(acc[["지역코드", "사고건수", "사고금액", "사고율"]], on="지역코드")
    merged = merged.merge(damage_wide.reset_index(), on="지역코드", how="left")
    dmg_cols = [c for c in merged.columns if c.startswith("피해주택_")]
    merged[dmg_cols] = merged[dmg_cols].fillna(0).astype(int)

    # 전월세 실거래가(01b) 집계가 있으면 함께 합친다. 수집이 끝나기 전이면 건너뜀
    rent_file = P / "rent_sigungu_2023_2025.csv"
    if rent_file.exists():
        rent = pd.read_csv(rent_file, dtype={"지역코드": str})
        merged = merged.merge(rent, on="지역코드", how="left")
        print(f"[전월세] 합침 — 전세 계약 정보 없는 지역: {merged['전세계약수'].isna().sum()}곳")
    else:
        print("[전월세] 아직 집계 파일이 없어 건너뜀 (01b 수집 완료 후 이 스크립트를 다시 실행)")

    merged.to_csv(P / "region_merged.csv", index=False, encoding="utf-8-sig")
    print(f"[저장] region_merged.csv — {len(merged)}행 × {merged.shape[1]}열")
    print(f"   피해 기록 있는 시군구 {(merged['피해주택_누적'] > 0).sum()}곳 / "
          f"보증사고 있는 시군구 {(merged['사고건수'] > 0).sum()}곳")

    # ── 5) 서울 행정동 데이터에도 지역코드 붙이기 ────────────
    seoul = pd.read_csv(P / "seoul_dong_monthly.csv")
    seoul_codes = master[master["시도"] == "서울"].set_index("시군구")["지역코드"]
    seoul["지역코드"] = seoul["시군구"].map(seoul_codes)
    assert seoul["지역코드"].notna().all(), "서울 구 이름 매칭 실패"
    seoul.to_csv(P / "seoul_dong_monthly.csv", index=False, encoding="utf-8-sig")

    # 교차 검증: 같은 기간(2023.7~2025.12) 서울 구별 합계가 두 파일에서 비슷한가?
    s_dong = seoul[seoul["연도"] <= 2025].groupby("지역코드")["피해건수"].sum()
    s_sgg = merged.set_index("지역코드").loc[s_dong.index, "피해주택_누적"]
    corr = s_dong.corr(s_sgg)
    print(f"[교차검증] 서울 구별 합계 — 행정동 파일 {s_dong.sum()}건 / 시군구 파일 {s_sgg.sum()}건, "
          f"상관계수 {corr:.3f}")
