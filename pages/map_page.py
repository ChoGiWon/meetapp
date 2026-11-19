import asyncio
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
import flet as ft
import flet_webview as fwv

# config.py에서 발급받은 API 키 불러오기
try:
    from config import TMAP_APP_KEY, KAKAO_JS_KEY, NAVER_CLIENT_ID
except ImportError:
    TMAP_APP_KEY = ""
    KAKAO_JS_KEY = ""
    NAVER_CLIENT_ID = ""

# GitHub Pages에 배포된 지도 뷰어 HTTPS 주소
GITHUB_PAGES_MAP_URL = "https://chogiwon.github.io/meetapp/map.html"


# =====================================================================
# [1] 거리 계산 및 형식화 유틸리티 (현위치 우선 정렬용)
# =====================================================================
def _calc_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 좌표 간 직선 거리(km) 계산 (Haversine 공식)"""
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _format_distance(dist_km: float) -> str:
    if dist_km < 1.0:
        return f"{int(round(dist_km * 1000))}m"
    return f"{dist_km:.1f}km"


# =====================================================================
# [2] TMAP 장소 통합검색 (POI) 다건 조회 (현위치 기준 우선순위 지원)
# =====================================================================
def _fetch_tmap_pois(
    keyword: str,
    count: int = 12,
    center_lat: float | None = None,
    center_lon: float | None = None,
) -> tuple[list[dict], str]:
    """
    검색어로 TMAP POI API를 조회하여 (장소 리스트, 오류메시지) 반환.
    center_lat/center_lon이 전달되면 현위치 주변 결과를 최상단으로 우선 정렬.
    """
    if not TMAP_APP_KEY or "붙여넣기" in TMAP_APP_KEY:
        return [], "TMAP_APP_KEY가 설정되지 않았습니다."
    if not keyword.strip():
        return [], ""

    try:
        encoded_kw = urllib.parse.quote(keyword.strip())
        url = (
            f"https://apis.openapi.sk.com/tmap/pois"
            f"?version=1&searchKeyword={encoded_kw}&resCoordType=WGS84GEO&reqCoordType=WGS84GEO&count={count}"
        )
        if center_lat is not None and center_lon is not None:
            url += f"&centerLat={center_lat}&centerLon={center_lon}&searchtypCd=A"

        req = urllib.request.Request(
            url,
            headers={
                "appKey": TMAP_APP_KEY.strip(),
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_body = resp.read().decode("utf-8").strip()
            if not raw_body:
                return [], f"'{keyword}' 검색 결과가 없습니다."

            data = json.loads(raw_body)
            pois = data.get("searchPoiInfo", {}).get("pois", {}).get("poi", [])
            results = []
            for item in pois:
                lat_val = item.get("frontLat") or item.get("noorLat")
                lon_val = item.get("frontLon") or item.get("noorLon")
                if not lat_val or not lon_val:
                    continue

                lat_f = float(lat_val)
                lon_f = float(lon_val)

                # 도로명 주소 추출
                road_address = ""
                new_addr_list = item.get("newAddressList", {}).get("newAddress", [])
                if new_addr_list and new_addr_list[0].get("fullAddressRoad"):
                    road_address = new_addr_list[0]["fullAddressRoad"].strip()

                # 지번/행정동 주소 조합
                jibun_parts = [
                    item.get("upperAddrName", ""),
                    item.get("middleAddrName", ""),
                    item.get("lowerAddrName", ""),
                    item.get("detailAddrName", ""),
                    item.get("firstNo", ""),
                ]
                jibun_address = " ".join(p.strip() for p in jibun_parts if p and p.strip())

                display_address = road_address or jibun_address

                dist_km = None
                dist_text = ""
                if center_lat is not None and center_lon is not None:
                    dist_km = _calc_distance_km(center_lat, center_lon, lat_f, lon_f)
                    dist_text = _format_distance(dist_km)

                results.append(
                    {
                        "name": item.get("name", keyword),
                        "address": display_address,
                        "road_address": road_address,
                        "jibun_address": jibun_address,
                        "lat": lat_f,
                        "lon": lon_f,
                        "dist_km": dist_km,
                        "dist_text": dist_text,
                    }
                )

            if not results:
                return [], f"'{keyword}' 검색 결과를 찾지 못했습니다."

            # 현위치 적용 시 가까운 장소 우선, 먼 타지역 장소는 후순위로 정렬
            if center_lat is not None and center_lon is not None:
                results.sort(key=lambda x: x["dist_km"] if x["dist_km"] is not None else 999999.0)

            return results[:7], ""

    except urllib.error.HTTPError as http_err:
        err_msg = f"HTTP {http_err.code} 오류 (SK Open API '장소 통합검색' 권한 확인)"
        print(f"[TMAP 검색 오류] {err_msg}")
        return [], err_msg
    except Exception as ex:
        print(f"[TMAP 검색 오류] {ex}")
        return [], f"검색 오류: {ex}"


# =====================================================================
# [3] TMAP 역지오코딩 (좌표 -> 도로명/지번 주소 변환)
# =====================================================================
def _reverse_geocode_tmap(lat: float, lon: float) -> dict:
    """
    위도/경도 좌표로 TMAP Reverse Geocoding API를 호출해 도로명/지번 주소 반환
    """
    fallback_coord = f"위도 {lat:.5f}, 경도 {lon:.5f}"
    if not TMAP_APP_KEY or "붙여넣기" in TMAP_APP_KEY:
        return {"primary": fallback_coord, "secondary": ""}

    for addr_type in ("A10", "A02"):
        try:
            url = (
                f"https://apis.openapi.sk.com/tmap/geo/reversegeocoding"
                f"?version=1&lat={lat}&lon={lon}&coordType=WGS84GEO&addressType={addr_type}"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "appKey": TMAP_APP_KEY.strip(),
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw_body = resp.read().decode("utf-8").strip()
                if not raw_body:
                    continue

                data = json.loads(raw_body)
                info = data.get("addressInfo", {})
                if not info:
                    continue

                city_do = (info.get("city_do") or "").strip()
                gu_gun = (info.get("gu_gun") or "").strip()
                eup_myeon = (info.get("eup_myeon") or "").strip()
                road_name = (info.get("roadName") or "").strip()
                building_idx = (info.get("buildingIndex") or "").strip()
                building_name = (info.get("buildingName") or "").strip()
                jibun_full = (info.get("fullAddress") or "").strip()

                road_full = ""
                if road_name:
                    road_parts = [city_do, gu_gun, eup_myeon, road_name, building_idx]
                    road_full = " ".join(p for p in road_parts if p).strip()
                    if building_name and building_name not in road_full:
                        road_full = f"{road_full} ({building_name})"

                if road_full and jibun_full:
                    return {"primary": road_full, "secondary": f"지번: {jibun_full}"}
                if road_full:
                    return {"primary": road_full, "secondary": ""}
                if jibun_full:
                    return {"primary": jibun_full, "secondary": ""}
        except Exception as ex:
            print(f"[TMAP 역지오코딩 오류({addr_type})] {ex}")

    return {"primary": fallback_coord, "secondary": "주소 정보 없음"}


def _fetch_ip_location() -> tuple[float, float] | None:
    """WebView GPS가 제한된 환경에서 IP 기반으로 대략적 현위치 좌표를 조회하는 폴백"""
    endpoints = [
        ("https://ipwho.is/", "latitude", "longitude"),
        ("https://ipapi.co/json/", "latitude", "longitude"),
    ]
    for url, lat_k, lon_k in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MeetApp/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                lat_v = data.get(lat_k)
                lon_v = data.get(lon_k)
                if lat_v is not None and lon_v is not None:
                    return float(lat_v), float(lon_v)
        except Exception:
            continue
    return None


def _build_hosted_map_url() -> str:
    """GitHub Pages HTTPS URL에 API 키와 캐시 방지 타임스탬프를 결합하여 반환"""
    params = urllib.parse.urlencode(
        {
            "tmap": (TMAP_APP_KEY or "").strip(),
            "kakao": (KAKAO_JS_KEY or "").strip(),
            "naver": (NAVER_CLIENT_ID or "").strip(),
            "_v": int(time.time()),
        }
    )
    return f"{GITHUB_PAGES_MAP_URL}?{params}"


# =====================================================================
# [4] 지도 페이지 빌드 함수 (현위치 우선검색 + 터치 주소검색 + 자동복사)
# =====================================================================
def build_map_page() -> ft.Container:
    map_providers = [
        {"id": "kakao", "label": "카카오맵", "color": "#FEE500", "text_color": "#191919"},
        {"id": "naver", "label": "네이버맵", "color": "#03C75A", "text_color": "#FFFFFF"},
        {"id": "tmap", "label": "티맵", "color": "#0064FF", "text_color": "#FFFFFF"},
    ]

    state = {
        "debounce_task": None,
        "last_keyword": "",
        "suggestions": [],
        "is_selecting": False,
        "use_my_location": False,
        "my_lat": None,
        "my_lon": None,
        "selected_lat": 37.5665,
        "selected_lon": 126.9780,
        "copied_address": "",
        "secondary_address": "",
    }

    async def exec_js(js_code: str):
        """WebView 내부 JS 함수를 안전하게 실행"""
        try:
            res = map_webview.run_javascript(js_code)
            if asyncio.iscoroutine(res):
                await res
        except Exception as ex:
            print(f"[WebView JS 오류] {ex}")

    async def copy_to_clipboard(text: str):
        """Flet 1.x Clipboard, Page Clipboard, WebView 브라우저 복사를 순차 시도"""
        if not text:
            return
        copied = False
        try:
            if hasattr(ft, "Clipboard"):
                cb = ft.Clipboard()
                res = cb.set(text)
                if asyncio.iscoroutine(res):
                    await res
                copied = True
        except Exception as ex:
            print(f"[Clipboard 서비스 경고] {ex}")

        if not copied:
            try:
                target_page = map_webview.page
                if target_page and hasattr(target_page, "set_clipboard"):
                    res = target_page.set_clipboard(text)
                    if asyncio.iscoroutine(res):
                        await res
                    copied = True
            except Exception as ex:
                print(f"[Page Clipboard 경고] {ex}")

        safe_js_text = json.dumps(text, ensure_ascii=False)
        await exec_js(f"copyTextInBrowser({safe_js_text});")

    # -----------------------------------------------------------------
    # 하단 복사된 주소 표시 바 UI
    # -----------------------------------------------------------------
    copied_badge_text = ft.Text(
        value="주소 복사됨",
        size=11,
        weight=ft.FontWeight.W_700,
        color="#13A84F",
    )

    copied_primary_text = ft.Text(
        value="",
        size=13,
        weight=ft.FontWeight.W_700,
        color="#111111",
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    copied_secondary_text = ft.Text(
        value="",
        size=11,
        color="#666666",
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        visible=False,
    )

    async def handle_recopy_click(e):
        if not state["copied_address"]:
            return
        await copy_to_clipboard(state["copied_address"])
        copied_badge_text.value = "클립보드에 다시 복사됨!"
        copied_badge_text.update()

    async def handle_set_as_my_loc_click(e):
        lat = state["selected_lat"]
        lon = state["selected_lon"]
        if lat is None or lon is None:
            return
        await apply_my_location_coords(lat, lon, "선택한 위치를 현위치로 적용했습니다.", move_center=False)

    recopy_btn = ft.Container(
        height=30,
        padding=ft.Padding.symmetric(horizontal=10),
        border_radius=6,
        bgcolor="#EEF4FF",
        border=ft.Border.all(1, "#C2D8FF"),
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=lambda e: asyncio.create_task(handle_recopy_click(e)),
        content=ft.Text("다시 복사", size=11, weight=ft.FontWeight.W_700, color="#0064FF"),
    )

    pin_my_loc_btn = ft.Container(
        height=30,
        padding=ft.Padding.symmetric(horizontal=8),
        border_radius=6,
        bgcolor="#F3F5F7",
        border=ft.Border.all(1, "#DCDFE4"),
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=lambda e: asyncio.create_task(handle_set_as_my_loc_click(e)),
        content=ft.Text("현위치 기준", size=11, weight=ft.FontWeight.W_600, color="#333333"),
    )

    copied_address_bar = ft.Container(
        visible=False,
        margin=ft.Margin.only(left=12, right=12, top=6, bottom=52),
        padding=ft.Padding.symmetric(horizontal=12, vertical=9),
        bgcolor=ft.Colors.WHITE,
        border_radius=10,
        border=ft.Border.all(1, "#D0D7DE"),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=6,
            color="#1A000000",
            offset=ft.Offset(0, -1),
        ),
        content=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon=ft.Icons.CONTENT_COPY_ROUNDED, size=18, color="#13A84F"),
                ft.Column(
                    expand=True,
                    spacing=2,
                    controls=[
                        copied_badge_text,
                        copied_primary_text,
                        copied_secondary_text,
                    ],
                ),
                ft.Column(
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        recopy_btn,
                        pin_my_loc_btn,
                    ],
                ),
            ],
        ),
    )

    async def set_and_copy_address(primary_addr: str, secondary_addr: str = ""):
        """주소 상태 갱신 + 클립보드 자동 복사 + 하단 카드 표시"""
        if not primary_addr:
            return
        state["copied_address"] = primary_addr
        state["secondary_address"] = secondary_addr

        copied_badge_text.value = "주소 자동 복사됨"
        copied_primary_text.value = primary_addr
        if secondary_addr:
            copied_secondary_text.value = secondary_addr
            copied_secondary_text.visible = True
        else:
            copied_secondary_text.visible = False

        copied_address_bar.visible = True
        copied_address_bar.update()

        await copy_to_clipboard(primary_addr)

    # -----------------------------------------------------------------
    # 현위치 버튼 및 적용 로직
    # -----------------------------------------------------------------
    search_status_text = ft.Text(
        value="",
        size=12,
        color="#13A84F",
        weight=ft.FontWeight.W_600,
        visible=False,
    )

    my_loc_icon = ft.Icon(icon=ft.Icons.MY_LOCATION_ROUNDED, size=15, color="#0064FF")
    my_loc_label = ft.Text("현위치", size=12, weight=ft.FontWeight.W_700, color="#0064FF")

    def update_my_loc_button_ui():
        is_on = state["use_my_location"]
        my_loc_btn.bgcolor = "#0064FF" if is_on else "#EEF4FF"
        my_loc_btn.border = ft.Border.all(1, "#0064FF" if is_on else "#C2D8FF")
        my_loc_icon.color = ft.Colors.WHITE if is_on else "#0064FF"
        my_loc_label.value = "현위치 ON" if is_on else "현위치"
        my_loc_label.color = ft.Colors.WHITE if is_on else "#0064FF"
        my_loc_btn.update()

    async def apply_my_location_coords(
        lat: float,
        lon: float,
        status_msg: str,
        move_center: bool = True,
    ):
        state["use_my_location"] = True
        state["my_lat"] = lat
        state["my_lon"] = lon
        state["selected_lat"] = lat
        state["selected_lon"] = lon
        update_my_loc_button_ui()

        search_status_text.value = status_msg
        search_status_text.color = "#0064FF"
        search_status_text.visible = True
        search_status_text.update()

        move_flag = "true" if move_center else "false"
        await exec_js(f"setMyLocation({lat}, {lon}, {move_flag});")

        # 현위치 주소도 역지오코딩 후 자동 복사 및 하단 표시
        addr_info = await asyncio.to_thread(_reverse_geocode_tmap, lat, lon)
        await set_and_copy_address(addr_info["primary"], addr_info["secondary"])

        # 이미 검색창에 입력된 검색어가 있다면 현위치 기준으로 즉시 재검색
        current_kw = (search_input.value or "").strip()
        if current_kw:
            results, _ = await asyncio.to_thread(
                _fetch_tmap_pois, current_kw, 12, lat, lon
            )
            state["last_keyword"] = current_kw
            state["suggestions"] = results
            if results:
                render_suggestions(results)

    async def handle_my_loc_click(e):
        # 이미 현위치 기준 검색이 켜져 있으면 토글 해제
        if state["use_my_location"]:
            state["use_my_location"] = False
            state["my_lat"] = None
            state["my_lon"] = None
            update_my_loc_button_ui()
            await exec_js("clearMyLocation();")

            search_status_text.value = "현위치 기준 검색이 해제되었습니다."
            search_status_text.color = "#666666"
            search_status_text.visible = True
            search_status_text.update()
            return

        search_status_text.value = "현위치를 확인하는 중..."
        search_status_text.color = "#444444"
        search_status_text.visible = True
        search_status_text.update()

        await exec_js("requestCurrentLocation();")

    my_loc_btn = ft.Container(
        height=40,
        padding=ft.Padding.symmetric(horizontal=10),
        border_radius=8,
        bgcolor="#EEF4FF",
        border=ft.Border.all(1, "#C2D8FF"),
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=lambda e: asyncio.create_task(handle_my_loc_click(e)),
        content=ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[my_loc_icon, my_loc_label],
        ),
    )

    # -----------------------------------------------------------------
    # WebView 이벤트 수신 (지도 터치 좌표, GPS 결과 처리)
    # -----------------------------------------------------------------
    async def process_map_click(lat: float, lon: float):
        state["selected_lat"] = lat
        state["selected_lon"] = lon

        suggestion_box.visible = False
        suggestion_box.update()

        search_status_text.value = "선택한 지점의 주소를 조회하는 중..."
        search_status_text.color = "#444444"
        search_status_text.visible = True
        search_status_text.update()

        addr_info = await asyncio.to_thread(_reverse_geocode_tmap, lat, lon)
        primary_addr = addr_info["primary"]
        secondary_addr = addr_info["secondary"]

        search_status_text.value = "선택 위치 주소 조회 완료"
        search_status_text.color = "#13A84F"
        search_status_text.update()

        safe_label = json.dumps(primary_addr, ensure_ascii=False)
        await exec_js(f"updateMarkerTitle({lat}, {lon}, {safe_label});")
        await set_and_copy_address(primary_addr, secondary_addr)

    async def process_geo_fallback():
        ip_coords = await asyncio.to_thread(_fetch_ip_location)
        if ip_coords:
            lat, lon = ip_coords
            await apply_my_location_coords(
                lat,
                lon,
                "현위치 적용됨 (네트워크 위치 기준 · 지도 터치 후 '현위치 기준'으로 미세조정 가능)",
                move_center=True,
            )
        else:
            # IP 조회마저 오프라인 등으로 실패 시 현재 지도 중심 좌표를 현위치로 적용
            lat = state["selected_lat"]
            lon = state["selected_lon"]
            await apply_my_location_coords(
                lat,
                lon,
                "현재 지도 중심 좌표를 현위치 기준으로 적용했습니다.",
                move_center=False,
            )

    def handle_webview_console(e):
        msg = getattr(e, "message", "") or ""
        if not msg.startswith("MEETAPP_EVENT:"):
            return
        try:
            payload = json.loads(msg[len("MEETAPP_EVENT:") :])
        except Exception:
            return

        evt_type = payload.get("type")
        if evt_type == "map_click":
            lat = float(payload["lat"])
            lon = float(payload["lon"])
            asyncio.create_task(process_map_click(lat, lon))
        elif evt_type == "geo_result":
            lat = float(payload["lat"])
            lon = float(payload["lon"])
            asyncio.create_task(
                apply_my_location_coords(
                    lat,
                    lon,
                    "현위치 적용 완료 (가까운 장소 우선으로 검색됩니다)",
                    move_center=True,
                )
            )
        elif evt_type == "geo_error":
            asyncio.create_task(process_geo_fallback())

    # GitHub Pages HTTPS 주소로 단일 WebView 로드
    map_webview = fwv.WebView(
        url=_build_hosted_map_url(),
        expand=True,
        on_console_message=handle_webview_console,
    )

    # -----------------------------------------------------------------
    # 연관검색어 및 검색 실행 로직
    # -----------------------------------------------------------------
    suggestion_list_col = ft.Column(spacing=0)
    suggestion_box = ft.Container(
        visible=False,
        margin=ft.Margin.only(top=4),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, "#D0D7DE"),
        border_radius=8,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=suggestion_list_col,
    )

    async def move_to_place(place: dict):
        """선택 또는 검색된 장소 좌표로 이동 + 주소 조회 및 자동 복사"""
        lat = place["lat"]
        lon = place["lon"]
        state["selected_lat"] = lat
        state["selected_lon"] = lon

        safe_name = json.dumps(place["name"], ensure_ascii=False)
        dist_suffix = f" ({place['dist_text']})" if place.get("dist_text") else ""

        search_status_text.value = f"이동 완료: {place['name']}{dist_suffix}"
        search_status_text.color = "#13A84F"
        search_status_text.visible = True
        search_status_text.update()

        await exec_js(f"moveToLocation({lat}, {lon}, {safe_name});")

        # 역지오코딩으로 정확한 도로명/지번 주소 조회 후 자동 복사 & 하단 표시
        addr_info = await asyncio.to_thread(_reverse_geocode_tmap, lat, lon)
        primary_addr = addr_info["primary"]
        secondary_addr = addr_info["secondary"]

        if primary_addr.startswith("위도 ") and place.get("address"):
            primary_addr = place["address"]

        await set_and_copy_address(primary_addr, secondary_addr)

    async def on_suggestion_tap(e, place: dict):
        """연관검색어 항목 클릭 시 입력창 반영 + 목록 닫기 + 지도 자동 이동"""
        if state["debounce_task"] and not state["debounce_task"].done():
            state["debounce_task"].cancel()

        state["is_selecting"] = True
        search_input.value = place["name"]
        clear_btn.visible = True
        search_input.update()
        clear_btn.update()

        suggestion_box.visible = False
        suggestion_box.update()

        await move_to_place(place)
        state["is_selecting"] = False

    def render_suggestions(items: list[dict]):
        """조회된 연관검색어 리스트 UI 생성 (현위치 적용 시 거리 배지 표시)"""
        suggestion_list_col.controls.clear()
        if not items:
            suggestion_box.visible = False
            suggestion_box.update()
            return

        for idx, item in enumerate(items):
            dist_badge = (
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                    bgcolor="#EEF4FF",
                    content=ft.Text(
                        value=item["dist_text"],
                        size=11,
                        weight=ft.FontWeight.W_700,
                        color="#0064FF",
                    ),
                )
                if item.get("dist_text")
                else ft.Container()
            )

            row_item = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=9),
                bgcolor=ft.Colors.WHITE,
                border=(
                    ft.Border.only(bottom=ft.BorderSide(1, "#F0F2F5"))
                    if idx < len(items) - 1
                    else None
                ),
                ink=True,
                on_click=lambda e, p=item: asyncio.create_task(on_suggestion_tap(e, p)),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(icon=ft.Icons.LOCATION_ON_ROUNDED, size=18, color="#0064FF"),
                        ft.Column(
                            expand=True,
                            spacing=2,
                            controls=[
                                ft.Row(
                                    spacing=6,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text(
                                            value=item["name"],
                                            size=13,
                                            weight=ft.FontWeight.W_700,
                                            color="#111111",
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            expand=True,
                                        ),
                                        dist_badge,
                                    ],
                                ),
                                ft.Text(
                                    value=item["address"] or "주소 정보 없음",
                                    size=11,
                                    color="#666666",
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                        ),
                    ],
                ),
            )
            suggestion_list_col.controls.append(row_item)

        suggestion_box.visible = True
        suggestion_box.update()

    def _get_search_center() -> tuple[float | None, float | None]:
        if state["use_my_location"] and state["my_lat"] is not None and state["my_lon"] is not None:
            return state["my_lat"], state["my_lon"]
        return None, None

    async def fetch_suggestions_debounced(keyword: str):
        """입력 멈춤 후 0.35초 뒤 연관검색어 조회"""
        try:
            await asyncio.sleep(0.35)
            c_lat, c_lon = _get_search_center()
            results, err_msg = await asyncio.to_thread(_fetch_tmap_pois, keyword, 12, c_lat, c_lon)
            state["last_keyword"] = keyword
            state["suggestions"] = results

            if results:
                search_status_text.visible = False
                search_status_text.update()
                render_suggestions(results)
            else:
                suggestion_box.visible = False
                suggestion_box.update()
                if err_msg:
                    search_status_text.value = err_msg
                    search_status_text.color = "#D32F2F"
                    search_status_text.visible = True
                    search_status_text.update()
        except asyncio.CancelledError:
            pass

    async def handle_input_change(e):
        """검색창 타이핑 시 실시간 연관검색어 트리거"""
        if state["is_selecting"]:
            return

        keyword = (search_input.value or "").strip()
        clear_btn.visible = bool(keyword)
        clear_btn.update()

        if state["debounce_task"] and not state["debounce_task"].done():
            state["debounce_task"].cancel()

        if not keyword:
            state["suggestions"] = []
            suggestion_box.visible = False
            search_status_text.visible = False
            suggestion_box.update()
            search_status_text.update()
            return

        state["debounce_task"] = asyncio.create_task(fetch_suggestions_debounced(keyword))

    async def handle_search_submit(e):
        """엔터 또는 [검색] 버튼 클릭 시 최상단 결과 위치로 자동 이동"""
        if state["debounce_task"] and not state["debounce_task"].done():
            state["debounce_task"].cancel()

        keyword = (search_input.value or "").strip()
        if not keyword:
            return

        suggestion_box.visible = False
        suggestion_box.update()

        if state["last_keyword"] == keyword and state["suggestions"]:
            await move_to_place(state["suggestions"][0])
            return

        search_status_text.value = f"'{keyword}' 위치 찾는 중..."
        search_status_text.color = "#444444"
        search_status_text.visible = True
        search_status_text.update()

        c_lat, c_lon = _get_search_center()
        results, err_msg = await asyncio.to_thread(_fetch_tmap_pois, keyword, 12, c_lat, c_lon)
        state["last_keyword"] = keyword
        state["suggestions"] = results

        if results:
            await move_to_place(results[0])
        else:
            search_status_text.value = err_msg or f"'{keyword}' 검색 결과를 찾지 못했습니다."
            search_status_text.color = "#D32F2F"
            search_status_text.update()

    def handle_clear_click(e):
        """검색어 지우기 버튼"""
        if state["debounce_task"] and not state["debounce_task"].done():
            state["debounce_task"].cancel()
        search_input.value = ""
        clear_btn.visible = False
        suggestion_box.visible = False
        search_status_text.visible = False
        search_input.update()
        clear_btn.update()
        suggestion_box.update()
        search_status_text.update()

    clear_btn = ft.IconButton(
        icon=ft.Icons.CANCEL_ROUNDED,
        icon_size=18,
        icon_color="#888888",
        padding=0,
        width=32,
        height=32,
        visible=False,
        tooltip="지우기",
        on_click=handle_clear_click,
    )

    def handle_input_focus(e):
        search_box.border = ft.Border.all(1.5, "#0064FF")
        search_box.update()

    def handle_input_blur(e):
        search_box.border = ft.Border.all(1, "#DCDFE4")
        search_box.update()

    search_input = ft.TextField(
        hint_text="장소 또는 주소 입력",
        hint_style=ft.TextStyle(color="#888888", size=13),
        color="#111111",
        text_style=ft.TextStyle(color="#111111", size=13, weight=ft.FontWeight.W_600),
        cursor_color="#111111",
        dense=True,
        border=ft.NoInputBorder(),
        bgcolor=ft.Colors.TRANSPARENT,
        content_padding=ft.Padding.symmetric(vertical=0, horizontal=0),
        expand=True,
        on_change=handle_input_change,
        on_submit=handle_search_submit,
        on_focus=handle_input_focus,
        on_blur=handle_input_blur,
    )

    search_box = ft.Container(
        height=40,
        expand=True,
        bgcolor="#F8F9FA",
        border_radius=8,
        border=ft.Border.all(1, "#DCDFE4"),
        padding=ft.Padding.only(left=12, right=4),
        alignment=ft.Alignment.CENTER,
        content=ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                search_input,
                clear_btn,
            ],
        ),
    )

    search_btn = ft.Container(
        height=40,
        padding=ft.Padding.symmetric(horizontal=12),
        border_radius=8,
        bgcolor="#0064FF",
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=handle_search_submit,
        content=ft.Text("검색", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
    )

    # 3사 지도 전환 버튼 생성
    provider_buttons = []

    async def on_provider_click(e, selected_id: str):
        for btn in provider_buttons:
            p_info = btn.data
            is_selected = (p_info["id"] == selected_id)
            btn.bgcolor = p_info["color"] if is_selected else "#F3F5F7"
            btn.border = ft.Border.all(
                1,
                p_info["color"] if is_selected else "#E0E0E0",
            )
            btn.content.color = p_info["text_color"] if is_selected else "#444444"
            btn.update()

        await exec_js(f"switchProvider('{selected_id}');")

    for p in map_providers:
        is_default = (p["id"] == "tmap")
        btn = ft.Container(
            data=p,
            expand=True,
            height=36,
            border_radius=8,
            bgcolor=p["color"] if is_default else "#F3F5F7",
            border=ft.Border.all(1, p["color"] if is_default else "#E0E0E0"),
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=lambda e, pid=p["id"]: asyncio.create_task(on_provider_click(e, pid)),
            content=ft.Text(
                value=p["label"],
                size=13,
                weight=ft.FontWeight.W_700,
                color=p["text_color"] if is_default else "#444444",
            ),
        )
        provider_buttons.append(btn)

    sub_menu_bar = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=8, bottom=6),
        bgcolor=ft.Colors.WHITE,
        content=ft.Row(
            controls=provider_buttons,
            spacing=8,
        ),
    )

    search_bar = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=2, bottom=8),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.only(bottom=ft.BorderSide(1, "#EEEEEE")),
        content=ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    controls=[search_box, search_btn, my_loc_btn],
                    spacing=6,
                ),
                suggestion_box,
                search_status_text,
            ],
        ),
    )

    return ft.Container(
        expand=True,
        bgcolor="#FAFAFA",
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                sub_menu_bar,        # 1단: 카카오맵 / 네이버맵 / 티맵 선택 버튼
                search_bar,          # 2단: 검색창 + 검색 버튼 + 현위치 버튼 + 연관검색어
                map_webview,         # 3단: GitHub Pages HTTPS WebView (지도 터치/현위치 연동)
                copied_address_bar,  # 4단: 지도 하단 복사된 주소 표시 카드
            ],
        ),
    )