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

import importlib
import json
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd

BASE = Path(__file__).resolve().parent
GEO_SRC = BASE / "data" / "raw" / "geo" / "HangJeongDong_ver20260401.geojson"
OUT = BASE / "output"

SIMPLIFY_M = 300            # 단순화 허용 오차(미터). 클수록 파일이 작아지지만 경계가 거칠어진다
SIMPLIFY_DONG_M = 30        # 서울 동은 작아서 더 정밀하게 (300m로 하면 작은 동이 사라진다)
DONG_ZOOM = 11              # 이 확대 수준부터 서울 동 단위 색칠을 보여 준다
GRAY = "#BDBDBD"            # 전세 계약도 피해도 없어 판단할 수 없는 동
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


def build_seoul_dong():
    """서울 행정동 경계 → 05단계와 같은 '동 그룹'으로 합치고 등급 붙이기

    05단계에서 행정동을 법정동 기준 동 그룹으로 묶었으므로(화곡1~8동 → 화곡동),
    지도에서도 같은 함수(to_group)로 행정동 도형을 묶어야 색과 숫자가 맞는다.
    파일 이름이 숫자로 시작해서 'import 05_seoul_dong'은 문법 오류 → importlib로 불러온다."""
    to_group = importlib.import_module("05_seoul_dong").to_group

    dong = gpd.read_file(GEO_SRC)
    dong = dong[dong["sido"] == "11"].copy()
    dong["행정동"] = dong["adm_nm"].str.split().str[-1]          # '서울특별시 강서구 화곡1동' → '화곡1동'
    dong["동그룹"] = [to_group(g, d) for g, d in zip(dong["sggnm"], dong["행정동"])]
    grp = dong.dissolve(by=["sgg", "동그룹"], as_index=False)[["sgg", "sggnm", "동그룹", "geometry"]]

    grp = grp.to_crs(5179)
    grp["geometry"] = grp.simplify(SIMPLIFY_DONG_M, preserve_topology=True)
    grp = grp.to_crs(4326).rename(columns={"sgg": "지역코드"})

    risk = pd.read_csv(OUT / "seoul_dong.csv", dtype={"지역코드": str})
    grp = grp.merge(risk.drop(columns=["시군구"]), on=["지역코드", "동그룹"], how="left")

    # 경계는 있는데 05단계 표에 없는 동 = 전세 계약도 피해도 0건 (예: 중구 명동·소공동, 상업지역)
    no_data = grp["등급"].isna()
    print(f"서울 동 그룹 경계 {len(grp)}개, 그중 계약·피해 자료 없음 {no_data.sum()}개: "
          f"{', '.join(grp.loc[no_data, 'sggnm'] + ' ' + grp.loc[no_data, '동그룹'])}")
    grp["등급"] = grp["등급"].fillna("자료없음")

    grp["이름"] = grp["sggnm"] + " " + grp["동그룹"]
    grp["배수"] = grp["전국대비_배수"].map(lambda x: f"{x:.1f}배" if pd.notna(x) else "-")
    grp["비고"] = grp["자료부족"].map({True: "계약이 적어 구 평균으로 추정", False: ""}).fillna("자료 없음")
    grp["피해주택"] = grp["피해주택"].fillna(0).astype(int)
    grp["전세계약수"] = grp["전세계약수"].fillna(0).astype(int)
    keep = ["지역코드", "동그룹", "이름", "등급", "서울순위", "배수", "피해주택", "전세계약수", "비고", "geometry"]
    return grp[keep]


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

    # ── 서울 동 단위 레이어 ──────────────────────────────
    # 지도에 붙여 두되, 페이지가 열리면 아래 자바스크립트(updateDongLayer)가 바로 떼어 내고
    # 서울을 확대했을 때만 다시 붙인다. 전국을 볼 때 동 경계까지 그리면 너무 빽빽하고 휴대폰에서 느려지기 때문이다.
    dong = build_seoul_dong()
    dong.to_file(OUT / "seoul_dong.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    dong_colors = {**COLORS, "자료없음": GRAY}
    dong_layer = folium.GeoJson(
        json.loads((OUT / "seoul_dong.geojson").read_text(encoding="utf-8")),
        name="서울 동 단위",
        style_function=lambda f: {"fillColor": dong_colors[f["properties"]["등급"]],
                                  "color": "#ffffff", "weight": 0.8, "fillOpacity": 0.8},
        highlight_function=lambda f: {"weight": 2.5, "color": "#222222"},
        tooltip=folium.GeoJsonTooltip(
            fields=["이름", "등급", "배수", "서울순위", "피해주택", "전세계약수", "비고"],
            aliases=["동", "위험등급", "전국 평균 대비 피해율", "서울 순위", "피해주택(2023.7~2025)",
                     "전세 계약(같은 기간)", "참고"],
            sticky=False),
    ).add_to(m)

    # 범례 2개: 전국(시군구)용과 서울 동용. 기준이 다르니(전국 상위 % / 전국 평균의 몇 배) 따로 보여 준다.
    box = ("position:fixed;bottom:18px;left:12px;z-index:9999;background:#fff;padding:8px 10px;"
           "border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.3);font:13px sans-serif;line-height:1.6")
    legend = f"""
    <div id="legend-sgg" style="{box}">
      <b>전세사기 위험등급 (시군구)</b><br>
      <span style="color:#D64541">■</span> 고위험 (상위 20%)<br>
      <span style="color:#F2B134">■</span> 주의 (다음 30%)<br>
      <span style="color:#3FA66B">■</span> 안전 (나머지 50%)<br>
      <span style="font-size:11px;color:#666">'안전'은 상대적으로 위험이 낮다는 뜻입니다<br>서울을 확대하면 동 단위로 보입니다</span>
    </div>
    <div id="legend-dong" style="{box};display:none">
      <b>서울 동 단위 피해율</b><br>
      <span style="color:#D64541">■</span> 고위험 (전국 평균의 2배 이상)<br>
      <span style="color:#F2B134">■</span> 주의 (전국 평균의 1~2배)<br>
      <span style="color:#3FA66B">■</span> 안전 (전국 평균보다 낮음)<br>
      <span style="color:{GRAY}">■</span> 자료 없음<br>
      <span style="font-size:11px;color:#666">서울 밖은 시군구 등급입니다</span>
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

    // 확대 수준에 따라 서울 동 레이어 켜고 끄기 (+ 범례 바꾸기)
    var SEOUL = L.latLngBounds([37.41, 126.76], [37.72, 127.19]);
    function updateDongLayer() {{
        var map = {m.get_name()}, dong = {dong_layer.get_name()};
        var show = map.getZoom() >= {DONG_ZOOM} && map.getBounds().intersects(SEOUL);
        if (show && !map.hasLayer(dong)) dong.addTo(map);
        if (!show && map.hasLayer(dong)) map.removeLayer(dong);
        document.getElementById('legend-sgg').style.display = show ? 'none' : 'block';
        document.getElementById('legend-dong').style.display = show ? 'block' : 'none';
    }}
    // 앱에서 동 하나로 이동: focusDong('11500', '화곡동')
    function focusDong(code, name) {{
        var dong = {dong_layer.get_name()}, found = null;
        dong.getLayers().forEach(function(l) {{
            dong.resetStyle(l);
            var p = l.feature.properties;
            if (p['지역코드'] === code && p['동그룹'] === name) found = l;
        }});
        if (!found) return false;
        {m.get_name()}.fitBounds(found.getBounds(), {{maxZoom: 14}});
        updateDongLayer();
        found.setStyle({{weight: 3.5, color: '#111111'}});
        found.bringToFront();
        found.openTooltip();
        return true;
    }}
    document.addEventListener('DOMContentLoaded', function() {{
        {m.get_name()}.on('zoomend moveend', updateDongLayer);
        updateDongLayer();
    }});
    </script>"""
    m.get_root().html.add_child(folium.Element(js))

    m.save(OUT / "map.html")

    kb = lambda p: (OUT / p).stat().st_size / 1024
    print(f"경계 원본 {GEO_SRC.stat().st_size / 1024 / 1024:.1f}MB → sigungu.geojson {kb('sigungu.geojson'):,.0f}KB")
    print(f"map.html {kb('map.html'):,.0f}KB, 시군구 {len(geo)}곳, 등급 {geo['등급'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
