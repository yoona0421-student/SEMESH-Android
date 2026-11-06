# -*- coding: utf-8 -*-
"""
01b단계: 국토교통부 전월세 실거래가 수집 (전국 시군구, 2023.7 ~ 2025.12)

[왜 이 데이터가 필요한가?]
  피해주택 '건수'만 비교하면 전세 계약이 많은 서울·경기가 무조건 위험하게 나온다.
  그래서 "전세 계약 1,000건당 피해주택 몇 건"처럼 **비율**로 바꿔야 공정하게 비교할 수 있다.
  이때 분모(전세 계약 수)를 이 데이터에서 얻는다.

[수집 범위]
  - 지역: 01단계 보증사고 파일의 시군구 256곳 (지역코드 5자리 = API의 LAWD_CD와 같은 코드)
  - 기간: 2023년 7월 ~ 2025년 12월 (30개월) ← 피해주택 데이터의 기간과 맞춤
  - 주택유형: 연립다세대 · 단독다가구 · 오피스텔 · 아파트
    → 처음에는 아파트를 뺐다(피해가 빌라·다가구·오피스텔에 몰려 있고 데이터가 커서).
      그런데 분자인 HUG 보증사고·피해주택에는 아파트도 포함되어 있어서, 분모에서 아파트를 빼면
      아파트가 많은 도시(거제·사천·포항 등)의 비율이 부풀려졌다(1차 결과에서 확인). → 아파트도 분모에 넣는다.

[호출량]
  256곳 × 30개월 × 3종 ≈ 23,000번. API는 한 번에 한 지역·한 달만 줄 수 있어서 이렇게 많다.

[중간에 멈춰도 안전하게: '유형 × 월' 단위로 파일 하나씩 저장]
  처음 버전은 모든 결과를 큰 압축파일 하나에 계속 이어 붙였다. 그런데 실행 중 프로그램이 갑자기 꺼지자
  파일 끝이 깨지고, 어디까지 받았는지 기록과 실제 내용이 어긋났다(→ 다시 받으면 중복·누락 위험).
  그래서 방식을 바꿨다.
    1) 한 유형·한 달(256개 시군구)을 **전부 받은 뒤에야** 파일로 저장한다.
    2) 임시 이름(.tmp)으로 다 쓴 다음 진짜 이름으로 바꾼다. → 파일이 '있으면 완전한 것', '없으면 안 받은 것'
    3) 다시 실행하면 이미 있는 파일은 건너뛴다. → 같은 달을 두 번 저장할 일이 없어 **중복이 생기지 않는다**.
  꺼지는 순간 받고 있던 달 하나만 처음부터 다시 받으면 된다.

실행: analysis 폴더에서  python 01b_collect_rent.py
결과:
  data/raw/molit_rent/{유형}_{년월}.csv.gz  ← 계약 한 건 한 건(원본 행). 용량이 커서 GitHub에는 올리지 않음
  data/processed/rent_sigungu_2023_2025.csv ← 시군구별로 집계한 표 (이걸 분석에 사용)
"""

import os
import time
import xml.etree.ElementTree as ET            # API 응답(XML)을 읽는 표준 라이브러리
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")                     # .env 파일의 값을 환경변수로 불러옴
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "").strip()

CACHE = BASE / "data" / "raw" / "molit_rent"   # 원본 행 저장 폴더 (.gitignore 처리)
CACHE.mkdir(parents=True, exist_ok=True)
OUT = BASE / "data" / "processed" / "rent_sigungu_2023_2025.csv"

# 주택유형별 API 주소. 응답 항목 이름이 유형마다 조금씩 달라서 면적 항목 이름도 같이 적어둔다.
APIS = {
    "연립다세대": ("RTMSDataSvcRHRent/getRTMSDataSvcRHRent", "excluUseAr"),   # 전용면적
    "단독다가구": ("RTMSDataSvcSHRent/getRTMSDataSvcSHRent", "totalFloorAr"), # 연면적
    "오피스텔": ("RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent", "excluUseAr"),
    "아파트": ("RTMSDataSvcAptRent/getRTMSDataSvcAptRent", "excluUseAr"),
}
URL = "https://apis.data.go.kr/1613000/"
ROWS_PER_PAGE = 5000                           # 한 번에 받을 최대 행 수. 처음엔 1000 → 5000도 된다는 걸 확인해 호출 수를 줄임
WORKERS = 8                                    # 동시에 보내는 요청 수 (더 늘리면 서버에 부담)

# 2023-07 ~ 2025-12 → ['202307', '202308', ..., '202512']
MONTHS = [d.strftime("%Y%m") for d in pd.date_range("2023-07-01", "2025-12-01", freq="MS")]

# ── 2026년 7월 행정구역 개편 대응 ────────────────────────────
# HUG 파일(보증사고·피해주택)은 '옛 지역코드'를 쓰는데, 국토부 API는 과거 거래도 '새 지역코드'로만 준다.
# 그래서 옛 코드로 요청하면 0건이 나온다. → 새 코드로 받은 뒤, 지역코드를 옛 코드로 되돌려 적는다.
#   - 광주광역시(29xxx)·전라남도(46xxx) → 전남광주통합특별시(12xxx): 이름이 같은 지역끼리 1:1
#   - 인천 서구(28260)  → 서해구(28275) + 검단구(28290)        : 둘을 합치면 옛 서구
#   - 인천 중구(28110)  → 영종구(28155) 전체 + 제물포구(28125) 일부
#   - 인천 동구(28140)  → 제물포구(28125) 일부                   : 제물포구는 '동 이름'으로 옛 중구/동구를 나눈다
# 근거: 국토교통부 법정동코드(data/raw/국토교통부_법정동코드_20260929.csv)
OLD_DONGGU_DONGS = {"만석동", "화수동", "송현동", "화평동", "창영동", "금곡동", "송림동"}  # 옛 인천 동구의 법정동
INCHEON_ALIAS = {"28110": ["28155", "28125"], "28140": ["28125"], "28260": ["28275", "28290"]}
EMPTY_CODES = {"41590"}   # 경기 화성시: 2026년 구 4개로 나뉘어 거래는 구 코드로만 나옴 → 시 코드 자체는 요청하지 않음


def build_alias():
    """옛 코드 → [새 코드들] 대응표. 광주·전남은 법정동코드 표에서 이름으로 자동 매칭"""
    table = pd.read_csv(BASE / "data" / "raw" / "국토교통부_법정동코드_20260929.csv",
                        encoding="cp949", dtype=str)
    sgg = table[table["법정동코드"].str[5:] == "00000"].copy()
    sgg["코드5"] = sgg["법정동코드"].str[:5]
    sgg["이름"] = sgg["법정동명"].str.split(" ", n=1).str[1]           # '광주광역시 동구' → '동구'
    new = sgg[sgg["법정동명"].str.startswith("전남광주통합특별시 ")].set_index("이름")["코드5"]
    old = sgg[sgg["법정동명"].str.match(r"^(광주광역시|전라남도) ") & (sgg["폐지여부"] == "폐지")]

    alias = dict(INCHEON_ALIAS)
    for r in old.itertuples():
        if r.이름 in new.index:
            alias[r.코드5] = [new[r.이름]]
    return alias


ALIAS = build_alias()


def fetch_alias(kind, old_code, ym):
    """개편 지역: 새 코드로 받아서 지역코드를 옛 코드로 바꿔 돌려준다."""
    rows = []
    for new_code in ALIAS[old_code]:
        for row in fetch(kind, new_code, ym):
            if new_code == "28125":          # 제물포구는 옛 중구와 옛 동구가 섞여 있음 → 동 이름으로 나눔
                belongs_to = "28140" if row["법정동"] in OLD_DONGGU_DONGS else "28110"
                if belongs_to != old_code:
                    continue
            row["지역코드"] = old_code
            rows.append(row)
    return rows


FIELDS = ["유형", "지역코드", "계약년월", "법정동", "보증금", "월세", "면적", "건축년도", "계약구분"]


class DailyLimitError(Exception):
    """하루 호출 한도를 넘었을 때 → 오늘은 그만 받고 내일 다시 실행"""


def to_number(text):
    """'15,900' 같은 문자열을 숫자 15900으로. 빈칸이면 None"""
    text = (text or "").replace(",", "").strip()
    return float(text) if text else None


def fetch(kind, code, ym):
    """한 유형·한 지역·한 달치 계약을 모두 받아 리스트로 돌려준다 (여러 페이지면 끝까지)."""
    path, area_tag = APIS[kind]
    rows, page = [], 1
    while True:
        params = {"serviceKey": API_KEY, "LAWD_CD": code, "DEAL_YMD": ym,
                  "numOfRows": ROWS_PER_PAGE, "pageNo": page}
        # 네트워크가 잠깐 끊기거나 서버가 오류(5xx)를 주면 기다렸다가 다시 시도한다.
        # 처음엔 3번(2·4·6초)만 시도했더니 서버가 잠시 느려진 순간에 수집 전체가 멈췄다 → 6번, 최대 약 1분까지 기다림
        for attempt in range(6):
            try:
                r = requests.get(URL + path, params=params, timeout=30)
                if r.status_code >= 500:
                    raise requests.RequestException(f"서버 오류 {r.status_code}")
                break
            except requests.RequestException:
                time.sleep(min(2 ** attempt * 2, 60))   # 2, 4, 8, 16, 32, 60초
        else:
            raise RuntimeError(f"{kind} {code} {ym}: 네트워크 오류 6회")

        text = r.content.decode("utf-8", "replace")
        if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in text or "<resultCode>22</resultCode>" in text:
            raise DailyLimitError()
        root = ET.fromstring(text)
        result_code = root.findtext(".//resultCode")
        if result_code not in ("000", "00"):
            raise RuntimeError(f"{kind} {code} {ym}: {result_code} {root.findtext('.//resultMsg')} "
                               f"{root.findtext('.//errMsg')}")

        for item in root.iter("item"):
            rows.append({
                "유형": kind,
                "지역코드": code,
                "계약년월": ym,
                "법정동": (item.findtext("umdNm") or "").strip(),
                "보증금": to_number(item.findtext("deposit")),       # 단위: 만원
                "월세": to_number(item.findtext("monthlyRent")),     # 단위: 만원, 0이면 전세
                "면적": to_number(item.findtext(area_tag)),
                "건축년도": (item.findtext("buildYear") or "").strip(),
                "계약구분": (item.findtext("contractType") or "").strip(),  # 신규/갱신
            })

        total = int(root.findtext(".//totalCount") or 0)
        if page * ROWS_PER_PAGE >= total:      # 마지막 페이지까지 받았으면 끝
            return rows
        page += 1


def month_file(kind, ym, part=""):
    """part='' → 일반 지역 파일, part='alias' → 행정구역 개편 지역(새 코드로 받은 것) 파일"""
    return CACHE / (f"{kind}_{ym}.csv.gz" if not part else f"{kind}_{ym}_{part}.csv.gz")


def collect():
    if not API_KEY:
        raise SystemExit(".env 파일에 DATA_GO_KR_API_KEY가 없습니다. (.env.example 참고)")

    all_codes = pd.read_csv(BASE / "data" / "processed" / "accident_2026_08.csv",
                            dtype={"지역코드": str})["지역코드"].tolist()
    # 일반 지역과 개편 지역을 나눠서 받는다. 개편 지역은 따로 '_alias' 파일에 저장
    # (일반 파일은 개편 지역을 옛 코드로 요청해 0건이었으므로, 두 파일을 합쳐도 같은 지역이 두 번 들어가지 않음)
    plain = [c for c in all_codes if c not in ALIAS and c not in EMPTY_CODES]
    alias_codes = [c for c in all_codes if c in ALIAS]

    jobs = ([(k, m, "", plain) for k in APIS for m in MONTHS] +
            [(k, m, "alias", alias_codes) for k in APIS for m in MONTHS])
    # 이미 파일이 있는 (유형, 월)은 건너뛴다 → 이어받기 + 중복 방지
    todo = [j for j in jobs if not month_file(j[0], j[1], j[2]).exists()]
    print(f"전체 {len(jobs)}개 중 남은 것 {len(todo)}개 "
          f"(일반 지역 {len(plain)}곳, 개편 지역 {len(alias_codes)}곳)")

    # 하루 호출 한도는 API(주택유형)마다 따로 있다.
    # 한 유형이 한도에 걸려도 다른 유형은 계속 받을 수 있도록, 한도에 걸린 유형만 기록해 두고 건너뛴다.
    limited = set()

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i, (kind, ym, part, codes) in enumerate(todo, 1):
            if kind in limited:
                continue
            t = time.time()
            get = fetch_alias if part == "alias" else fetch
            try:
                # 한 달치 시군구들을 8개씩 동시에 요청. map은 결과를 요청한 순서대로 돌려준다
                results = list(pool.map(lambda c: get(kind, c, ym), codes))
            except DailyLimitError:
                print(f"  {kind}: 오늘 호출 한도 도달 → 이 유형은 내일 이어서 받음")
                limited.add(kind)
                continue

            df = pd.DataFrame([row for rows in results for row in rows], columns=FIELDS)
            target = month_file(kind, ym, part)
            tmp = target.with_suffix(".tmp")
            df.to_csv(tmp, index=False, encoding="utf-8", compression="gzip")
            tmp.replace(target)                # 다 쓴 뒤에 이름 바꾸기 → 반쯤 쓰인 파일이 남지 않음
            print(f"  [{i}/{len(todo)}] {kind} {ym}{' (개편지역)' if part else ''}: "
                  f"{len(df):,}건 ({time.time() - t:.0f}초)")

    if limited:
        print(f"한도 때문에 남은 유형: {', '.join(limited)} → 내일 다시 실행하면 이어서 받습니다.")
        return False
    return True


def summarize():
    """원본 행 → 시군구별 집계표. 전세 = 월세가 0인 계약"""
    df = pd.concat([pd.read_csv(month_file(k, m, part), dtype={"지역코드": str})
                    for k in APIS for m in MONTHS for part in ("", "alias")], ignore_index=True)
    df["전세"] = df["월세"].fillna(0) == 0

    jeonse = df[df["전세"]]
    g_all = df.groupby("지역코드").size().rename("임대차계약수")
    g_j = jeonse.groupby("지역코드").agg(
        전세계약수=("보증금", "size"),
        전세보증금_중앙값=("보증금", "median"),            # 평균보다 극단값(아주 비싼 집)에 덜 흔들림
        전세_2억이하_비율=("보증금", lambda s: (s <= 20000).mean()),  # 지난 학기 '보증금 2억 이하' 기준 이어받기
    )
    g_type = jeonse.pivot_table(index="지역코드", columns="유형", values="보증금",
                                aggfunc="size", fill_value=0).add_prefix("전세_")
    out = pd.concat([g_all, g_j, g_type], axis=1).fillna(0).reset_index()
    out["전세비율"] = out["전세계약수"] / out["임대차계약수"]
    # 참고용: 아파트를 뺀 전세 계약 수 (1차 결과와 비교할 때 사용)
    out["전세계약수_비아파트"] = out["전세계약수"] - out.get("전세_아파트", 0)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"집계 저장 → {OUT}  (시군구 {len(out)}곳, 전세 계약 {int(out['전세계약수'].sum()):,}건)")


if __name__ == "__main__":
    start = time.time()
    if collect():
        summarize()
    print(f"걸린 시간: {(time.time() - start) / 60:.1f}분")
