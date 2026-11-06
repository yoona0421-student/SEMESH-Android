# -*- coding: utf-8 -*-
"""
04단계: 시군구 위험등급 지도(map.html) 만들기 → 안드로이드 앱 WebView에 넣을 파일

[하는 일]
  1) 행정동 경계(3,558개)를 시군구 단위(255개)로 합친다 (dissolve)
  2) 경계선을 단순화해서 파일 크기를 줄인다 → 휴대폰에서 빨리 열리도록
  3) 03단계 결과(output/region.csv)의 등급으로 색칠한 Folium 지도를 만든다
     - 지역에 손가락을 대면(터치) 이름·등급·순위·피해 건수가 뜬다
  4) 앱(Kotlin)에서 부를 수 있는 자바스크립트 함수를 지도 안에 넣어 둔다
     - focusRegion('11500')        : 그 시군구로 이동하고 테두리 강조
     - showMyLocation(37.55, 126.85): 내 위치에 마커 표시
     → 안드로이드에서 webView.evaluateJavascript("focusRegion('11500')", null) 처럼 호출

[경계 데이터 출처 — CC BY 4.0, 출처 표시 필수]
  통계청 SGIS 행정동 경계(공공누리 제1유형) 가공본, vuski/admdongkor ver20260401
  https://github.com/vuski/admdongkor
  ver20260401을 쓴 이유: 화성시 4개 구 분리(2026.2) 이후 + 인천·광주·전남 개편(2026.7) 이전이라
  HUG 데이터의 지역코드(255개)와 정확히 일치한다.

실행: analysis 폴더에서  python 04_make_map.py
결과: output/sigungu.geojson (단순화된 경계), output/map.html (앱에 넣을 지도)
"""

import json
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd

BASE = Path(__file__).resolve().parent
GEO_SRC = BASE / "data" / "raw" / "geo" / "HangJeongDong_ver20260401.geojson"
OUT = BASE / "output"

SIMPLIFY_M = 300            # 단순화 허용 오차(미터). 클수록 파일이 작아지지만 경계가 거칠어진다
COLORS = {"고위험": "#D64541", "주의": "#F2B134", "안전": "#3FA66B"}
ATTR = ('경계: 통계청 SGIS(공공누리 1유형) 가공 '
        '<a href="https://github.com/vuski/admdongkor">vuski/admdongkor</a> · '
        '데이터: HUG, 국토교통부')


def build_boundaries():
    """행정동 → 시군구로 합치고 단순화"""
    dong = gpd.read_file(GEO_SRC)
    # 같은 시군구코드(sgg)를 가진 행정동들을 하나의 도형으로 합친다
    sgg = dong.dissolve(by="sgg", as_index=False)[["sgg", "geometry"]]

    # 단순화는 '미터' 단위로 해야 하므로, 위경도(EPSG:4326)를 한국 미터 좌표계(EPSG:5179)로 바꿨다가 되돌린다
    sgg = sgg.to_crs(5179)
    sgg["geometry"] = sgg.simplify(SIMPLIFY_M, preserve_topology=True)
    sgg = sgg.to_crs(4326)
    return sgg.rename(columns={"sgg": "지역코드"})


def main():
    region = pd.read_csv(OUT / "region.csv", dtype={"지역코드": str})
    geo = build_boundaries().merge(region, on="지역코드", how="left")

    missing = geo["등급"].isna().sum()
    assert missing == 0, f"등급이 없는 경계 {missing}개 — 지역코드 매칭 확인 필요"

    # 앱에서 보여 줄 값만 남기고, 소수점을 줄여 용량을 아낀다
    geo["이름"] = geo["시도"] + " " + geo["시군구"]
    geo["피해율"] = geo["피해율_보정"].round(2)
    geo["사고율표시"] = geo["사고율"].round(1)
    keep = ["지역코드", "이름", "등급", "순위", "종합점수", "피해주택_누적", "피해율", "사고건수", "사고율표시", "geometry"]
    geo = geo[keep]
    geo.to_file(OUT / "sigungu.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)

    # ── Folium 지도 ─────────────────────────────────────
    # 배경 지도: 처음엔 CartoDB를 썼는데 'API KEY REQUIRED' 워터마크가 떠서 키가 필요 없는 OpenStreetMap으로 변경
    m = folium.Map(location=[36.3, 127.8], zoom_start=7, tiles=None, control_scale=True, prefer_canvas=True)
    folium.TileLayer("OpenStreetMap", attr="© OpenStreetMap contributors · " + ATTR).add_to(m)

    layer = folium.GeoJson(
        json.loads((OUT / "sigungu.geojson").read_text(encoding="utf-8")),
        name="전세사기 위험등급",
        style_function=lambda f: {"fillColor": COLORS[f["properties"]["등급"]],
                                  "color": "#ffffff", "weight": 0.6, "fillOpacity": 0.75},
        highlight_function=lambda f: {"weight": 2.5, "color": "#222222"},
        tooltip=folium.GeoJsonTooltip(
            fields=["이름", "등급", "순위", "피해주택_누적", "사고건수"],
            aliases=["지역", "위험등급", "전국 순위(255곳 중)", "피해주택(2023.7~2025)", "보증사고(월평균, 2026.8)"],
            sticky=False),
    ).add_to(m)

    # 범례 (화면 왼쪽 아래 고정)
    legend = """
    <div style="position:fixed;bottom:18px;left:12px;z-index:9999;background:#fff;padding:8px 10px;
                border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.3);font:13px sans-serif;line-height:1.6">
      <b>전세사기 위험등급</b><br>
      <span style="color:#D64541">■</span> 고위험 (상위 20%)<br>
      <span style="color:#F2B134">■</span> 주의 (다음 30%)<br>
      <span style="color:#3FA66B">■</span> 안전 (나머지 50%)<br>
      <span style="font-size:11px;color:#666">'안전'은 상대적으로 위험이 낮다는 뜻입니다</span>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))

    # 앱(Kotlin)에서 호출할 함수. Folium이 붙인 변수 이름(layer.get_name())으로 지도·레이어에 접근한다
    js = f"""
    <script>
    var myMarker = null;
    function _layers() {{ return {layer.get_name()}.getLayers(); }}
    function focusRegion(code) {{
        var found = null;
        _layers().forEach(function(l) {{
            {layer.get_name()}.resetStyle(l);
            if (l.feature.properties['지역코드'] === code) found = l;
        }});
        if (!found) return false;
        found.setStyle({{weight: 3.5, color: '#111111'}});
        found.bringToFront();
        {m.get_name()}.fitBounds(found.getBounds(), {{maxZoom: 11}});
        found.openTooltip();
        return true;
    }}
    function showMyLocation(lat, lng) {{
        if (myMarker) {{ {m.get_name()}.removeLayer(myMarker); }}
        myMarker = L.marker([lat, lng]).addTo({m.get_name()}).bindPopup('내 위치').openPopup();
    }}
    </script>"""
    m.get_root().html.add_child(folium.Element(js))

    m.save(OUT / "map.html")

    kb = lambda p: (OUT / p).stat().st_size / 1024
    print(f"경계 원본 {GEO_SRC.stat().st_size / 1024 / 1024:.1f}MB → sigungu.geojson {kb('sigungu.geojson'):,.0f}KB")
    print(f"map.html {kb('map.html'):,.0f}KB, 시군구 {len(geo)}곳, 등급 {geo['등급'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
