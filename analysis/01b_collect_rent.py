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
  - 주택유형: 연립다세대 · 단독다가구 · 오피스텔 (아파트는 전세사기 피해가 적고 데이터가 매우 커서 제외)
    → 전세사기 피해주택의 대부분이 빌라(연립다세대)·다가구·오피스텔이라는 점이 근거 (논문에 출처와 함께 쓸 것)

[호출량]
  256곳 × 30개월 × 3종 ≈ 23,000번. API는 한 번에 한 지역·한 달만 줄 수 있어서 이렇게 많다.
  개발계정은 하루 호출 수 제한이 있어서, 중간에 멈춰도 **다시 실행하면 이어서** 받도록 만들었다.

실행: analysis 폴더에서  python 01b_collect_rent.py
결과:
  data/raw/molit_rent/  ← 계약 한 건 한 건(원본 행). 용량이 커서 GitHub에는 올리지 않음
  data/processed/rent_sigungu_2023_2025.csv ← 시군구별로 집계한 표 (이걸 분석에 사용)
"""

import os
import time
import csv
import gzip
import xml.etree.ElementTree as ET            # API 응답(XML)을 읽는 표준 라이브러리
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")                     # .env 파일의 값을 환경변수로 불러옴
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "").strip()

CACHE = BASE / "data" / "raw" / "molit_rent"   # 원본 행 저장 폴더 (.gitignore 처리)
CACHE.mkdir(parents=True, exist_ok=True)
DONE_LOG = CACHE / "_done.csv"                 # 어떤 (유형, 지역, 월)을 이미 받았는지 기록 → 이어받기용
OUT = BASE / "data" / "processed" / "rent_sigungu_2023_2025.csv"

# 주택유형별 API 주소. 응답 항목 이름이 유형마다 조금씩 달라서 면적 항목 이름도 같이 적어둔다.
APIS = {
    "연립다세대": ("RTMSDataSvcRHRent/getRTMSDataSvcRHRent", "excluUseAr"),   # 전용면적
    "단독다가구": ("RTMSDataSvcSHRent/getRTMSDataSvcSHRent", "totalFloorAr"), # 연면적
    "오피스텔": ("RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent", "excluUseAr"),
}
URL = "https://apis.data.go.kr/1613000/"
ROWS_PER_PAGE = 1000                           # 한 번에 받을 최대 행 수 (많을수록 호출 수가 줄어듦)
WORKERS = 4                                    # 동시에 보내는 요청 수. 너무 많으면 서버에 부담 → 4개로 제한

# 2023-07 ~ 2025-12 → ['202307', '202308', ..., '202512']
MONTHS = [d.strftime("%Y%m") for d in pd.date_range("2023-07-01", "2025-12-01", freq="MS")]

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
        for attempt in range(3):               # 네트워크가 잠깐 끊겨도 3번까지 다시 시도
            try:
                r = requests.get(URL + path, params=params, timeout=30)
                break
            except requests.RequestException:
                time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"{kind} {code} {ym}: 네트워크 오류 3회")

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


def load_done():
    if not DONE_LOG.exists():
        return set()
    done = pd.read_csv(DONE_LOG, dtype=str)
    return set(zip(done["유형"], done["지역코드"], done["계약년월"]))


def collect():
    if not API_KEY:
        raise SystemExit(".env 파일에 DATA_GO_KR_API_KEY가 없습니다. (.env.example 참고)")

    codes = pd.read_csv(BASE / "data" / "processed" / "accident_2026_08.csv",
                        dtype={"지역코드": str})["지역코드"].tolist()
    done = load_done()
    todo = [(k, c, m) for k in APIS for c in codes for m in MONTHS if (k, c, m) not in done]
    print(f"전체 {len(APIS) * len(codes) * len(MONTHS)}건 중 남은 작업 {len(todo)}건")
    if not todo:
        return True

    new_log = not DONE_LOG.exists()
    with open(DONE_LOG, "a", newline="", encoding="utf-8") as log_f:
        log = csv.writer(log_f)
        if new_log:
            log.writerow(["유형", "지역코드", "계약년월", "행수"])
        # 유형별로 gzip(압축) 파일 하나에 계속 이어 붙인다. 원본 행이 수백만 개라 압축해야 용량이 줄어듦
        files = {k: gzip.open(CACHE / f"{k}.csv.gz", "at", newline="", encoding="utf-8") for k in APIS}
        writers = {k: csv.DictWriter(f, fieldnames=FIELDS) for k, f in files.items()}
        for k, f in files.items():
            if f.tell() == 0:
                writers[k].writeheader()

        finished = 0
        try:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                futures = {pool.submit(fetch, *job): job for job in todo}
                for fut in as_completed(futures):
                    kind, code, ym = futures[fut]
                    rows = fut.result()            # 여기서 오류가 나면 아래 except로
                    writers[kind].writerows(rows)  # 파일 쓰기는 한 곳(메인)에서만 → 내용이 섞이지 않음
                    log.writerow([kind, code, ym, len(rows)])
                    finished += 1
                    if finished % 500 == 0:
                        log_f.flush()
                        print(f"  {finished}/{len(todo)} 완료")
        except DailyLimitError:
            print("하루 호출 한도에 도달했습니다. 내일 다시 실행하면 이어서 받습니다.")
            for f in futures:
                f.cancel()
            return False
        finally:
            for f in files.values():
                f.close()
    return True


def summarize():
    """원본 행 → 시군구별 집계표. 전세 = 월세가 0인 계약"""
    df = pd.concat([pd.read_csv(CACHE / f"{k}.csv.gz", dtype={"지역코드": str}) for k in APIS],
                   ignore_index=True)
    df = df.drop_duplicates()                  # 이어받기 중 같은 행이 두 번 들어갔을 경우 대비
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
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"집계 저장 → {OUT}  (시군구 {len(out)}곳, 전세 계약 {int(out['전세계약수'].sum()):,}건)")


if __name__ == "__main__":
    start = time.time()
    if collect():
        summarize()
    print(f"걸린 시간: {(time.time() - start) / 60:.1f}분")
