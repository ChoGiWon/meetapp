import asyncio
import json
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
# [1] TMAP 장소 통합검색 (POI) 다건 조회 함수 (연관검색어 + 좌표 추출)
# =====================================================================
def _fetch_tmap_pois(keyword: str, count: int = 6) -> tuple[list[dict], str]:
    """
    검색어로 TMAP POI API를 조회하여 (장소 리스트, 오류메시지) 반환
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

                # 도로명 주소 또는 지번 주소 조합
                new_addr_list = item.get("newAddressList", {}).get("newAddress", [])
                if new_addr_list and new_addr_list[0].get("fullAddressRoad"):
                    address = new_addr_list[0]["fullAddressRoad"]
                else:
                    addr_parts = [
                        item.get("upperAddrName", ""),
                        item.get("middleAddrName", ""),
                        item.get("lowerAddrName", ""),
                        item.get("roadName", ""),
                        item.get("firstBuildNo", ""),
                    ]
                    address = " ".join(p for p in addr_parts if p).strip()

                results.append(
                    {
                        "name": item.get("name", keyword),
                        "address": address,
                        "lat": float(lat_val),
                        "lon": float(lon_val),
                    }
                )

            if not results:
                return [], f"'{keyword}' 검색 결과를 찾지 못했습니다."
            return results, ""

    except urllib.error.HTTPError as http_err:
        err_msg = f"HTTP {http_err.code} 오류 (SK Open API '장소 통합검색' 권한 확인)"
        print(f"[TMAP 검색 오류] {err_msg}")
        return [], err_msg
    except Exception as ex:
        print(f"[TMAP 검색 오류] {ex}")
        return [], f"검색 오류: {ex}"


def _build_hosted_map_url() -> str:
    """GitHub Pages HTTPS URL에 config.py의 API 키 파라미터를 결합하여 반환"""
    params = urllib.parse.urlencode(
        {
            "tmap": (TMAP_APP_KEY or "").strip(),
            "kakao": (KAKAO_JS_KEY or "").strip(),
            "naver": (NAVER_CLIENT_ID or "").strip(),
        }
    )
    return f"{GITHUB_PAGES_MAP_URL}?{params}"


# =====================================================================
# [2] 지도 페이지 빌드 함수 (연관검색어 + 자동 이동 + HTTPS WebView JS 제어)
# =====================================================================
def build_map_page() -> ft.Container:
    map_providers = [
        {"id": "kakao", "label": "카카오맵", "color": "#FEE500", "text_color": "#191919"},
        {"id": "naver", "label": "네이버맵", "color": "#03C75A", "text_color": "#FFFFFF"},
        {"id": "tmap", "label": "티맵", "color": "#0064FF", "text_color": "#FFFFFF"},
    ]

    # GitHub Pages HTTPS 주소로 단일 WebView 로드 (카카오/네이버 도메인 인증 통과)
    map_webview = fwv.WebView(
        url=_build_hosted_map_url(),
        expand=True,
    )

    state = {
        "debounce_task": None,
        "last_keyword": "",
        "suggestions": [],
        "is_selecting": False,
    }

    async def exec_js(js_code: str):
        """WebView 내부 JS 함수를 안전하게 실행"""
        try:
            res = map_webview.run_javascript(js_code)
            if asyncio.iscoroutine(res):
                await res
        except Exception as ex:
            print(f"[WebView JS 오류] {ex}")

    search_status_text = ft.Text(
        value="",
        size=12,
        color="#13A84F",
        weight=ft.FontWeight.W_600,
        visible=False,
    )

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
        """선택 또는 검색된 장소 좌표로 지도 즉시 이동"""
        safe_name = json.dumps(place["name"], ensure_ascii=False)
        lat = place["lat"]
        lon = place["lon"]

        search_status_text.value = f"이동 완료: {place['name']}"
        search_status_text.color = "#13A84F"
        search_status_text.visible = True
        search_status_text.update()

        await exec_js(f"moveToLocation({lat}, {lon}, {safe_name});")

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
        """조회된 연관검색어 리스트 UI 생성"""
        suggestion_list_col.controls.clear()
        if not items:
            suggestion_box.visible = False
            suggestion_box.update()
            return

        for idx, item in enumerate(items):
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
                                ft.Text(
                                    value=item["name"],
                                    size=13,
                                    weight=ft.FontWeight.W_700,
                                    color="#111111",
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
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

    async def fetch_suggestions_debounced(keyword: str):
        """입력 멈춤 후 0.35초 뒤 연관검색어 조회"""
        try:
            await asyncio.sleep(0.35)
            results, err_msg = await asyncio.to_thread(_fetch_tmap_pois, keyword, 6)
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

        results, err_msg = await asyncio.to_thread(_fetch_tmap_pois, keyword, 6)
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
        hint_text="장소 또는 주소 입력 (연관검색어 자동 표시)",
        hint_style=ft.TextStyle(color="#888888", size=13),
        color="#111111",
        text_style=ft.TextStyle(color="#111111", size=13, weight=ft.FontWeight.W_600),
        cursor_color="#111111",
        dense=True,
        border_width=0,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.TRANSPARENT,
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
        padding=ft.Padding.symmetric(horizontal=14),
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
                    controls=[search_box, search_btn],
                    spacing=8,
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
                sub_menu_bar,  # 1단: 카카오맵 / 네이버맵 / 티맵 선택 버튼
                search_bar,    # 2단: 장소 검색창 + 실시간 연관검색어 목록
                map_webview,   # 3단: GitHub Pages HTTPS WebView (3사 지도 통합)
            ],
        ),
    )