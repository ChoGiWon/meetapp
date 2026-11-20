import asyncio
import calendar
import datetime
import json
import os
import sqlite3
import flet as ft

try:
    import holidays as py_holidays
except ImportError:
    py_holidays = None

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "calendar.db")
_SHARED_MAP_ADDR_FILE = os.path.join(_BASE_DIR, "last_map_address.json")


# =====================================================================
# [CAL-02] 일정 데이터 스키마 및 카테고리 정의
# =====================================================================
CATEGORIES = {
    "모임": {"color": "#0064FF", "bg": "#EEF4FF"},
    "개인": {"color": "#13A84F", "bg": "#E8F5E9"},
    "기념일": {"color": "#E91E63", "bg": "#FCE4EC"},
}

WEEKDAY_NAMES_KO = ["월", "화", "수", "목", "금", "토", "일"]


# =====================================================================
# [CAL-01] SQLite 로컬 DB 관리 (calendar.db CRUD)
# =====================================================================
def _init_calendar_db():
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_date TEXT NOT NULL,
                event_time TEXT DEFAULT '',
                title TEXT NOT NULL,
                location TEXT DEFAULT '',
                category TEXT DEFAULT '모임',
                memo TEXT DEFAULT '',
                created_at TEXT DEFAULT ''
            )
            """
        )
        conn.commit()


def _db_insert_event(
    event_date: str,
    event_time: str,
    title: str,
    location: str,
    category: str,
    memo: str,
):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO events (event_date, event_time, title, location, category, memo, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_date, event_time, title, location, category, memo, now_str),
        )
        conn.commit()


def _db_update_event(
    event_id: int,
    event_date: str,
    event_time: str,
    title: str,
    location: str,
    category: str,
    memo: str,
):
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            """
            UPDATE events
            SET event_date = ?, event_time = ?, title = ?, location = ?, category = ?, memo = ?
            WHERE id = ?
            """,
            (event_date, event_time, title, location, category, memo, event_id),
        )
        conn.commit()


def _db_delete_event(event_id: int):
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()


def _row_to_event_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "event_date": row[1],
        "event_time": row[2] or "",
        "title": row[3],
        "location": row[4] or "",
        "category": row[5] if row[5] in CATEGORIES else "모임",
        "memo": row[6] or "",
    }


def _db_get_events_by_month(year: int, month: int) -> dict[str, list[dict]]:
    prefix = f"{year:04d}-{month:02d}-"
    grouped: dict[str, list[dict]] = {}
    with sqlite3.connect(_DB_PATH) as conn:
        cur = conn.execute(
            """
            SELECT id, event_date, event_time, title, location, category, memo
            FROM events
            WHERE event_date LIKE ?
            ORDER BY event_date ASC, event_time ASC, id ASC
            """,
            (f"{prefix}%",),
        )
        for row in cur.fetchall():
            ev = _row_to_event_dict(row)
            grouped.setdefault(ev["event_date"], []).append(ev)
    return grouped


def _db_get_events_by_date(date_str: str) -> list[dict]:
    with sqlite3.connect(_DB_PATH) as conn:
        cur = conn.execute(
            """
            SELECT id, event_date, event_time, title, location, category, memo
            FROM events
            WHERE event_date = ?
            ORDER BY event_time ASC, id ASC
            """,
            (date_str,),
        )
        return [_row_to_event_dict(r) for r in cur.fetchall()]


def _db_search_events(category: str = "전체", keyword: str = "") -> list[dict]:
    sql = """
        SELECT id, event_date, event_time, title, location, category, memo
        FROM events
        WHERE 1=1
    """
    params: list = []
    if category and category != "전체":
        sql += " AND category = ?"
        params.append(category)
    if keyword.strip():
        sql += " AND (title LIKE ? OR location LIKE ? OR memo LIKE ?)"
        like_kw = f"%{keyword.strip()}%"
        params.extend([like_kw, like_kw, like_kw])
    sql += " ORDER BY event_date ASC, event_time ASC, id ASC"

    with sqlite3.connect(_DB_PATH) as conn:
        cur = conn.execute(sql, params)
        return [_row_to_event_dict(r) for r in cur.fetchall()]


def _db_get_next_upcoming_event(today_str: str) -> dict | None:
    with sqlite3.connect(_DB_PATH) as conn:
        cur = conn.execute(
            """
            SELECT id, event_date, event_time, title, location, category, memo
            FROM events
            WHERE event_date >= ?
            ORDER BY event_date ASC, event_time ASC, id ASC
            LIMIT 1
            """,
            (today_str,),
        )
        row = cur.fetchone()
        return _row_to_event_dict(row) if row else None


# =====================================================================
# [CAL-06] 대한민국 공휴일 조회 유틸리티
# =====================================================================
_FIXED_HOLIDAYS_MD = {
    "01-01": "신정",
    "03-01": "삼일절",
    "05-05": "어린이날",
    "06-06": "현충일",
    "07-17": "제헌절",
    "08-15": "광복절",
    "10-03": "개천절",
    "10-09": "한글날",
    "12-25": "성탄절",
}

_LUNAR_AND_SUB_HOLIDAYS = {
    # 2025
    "2025-01-28": "설날 연휴",
    "2025-01-29": "설날",
    "2025-01-30": "설날 연휴",
    "2025-03-03": "대체공휴일(삼일절)",
    "2025-05-06": "대체공휴일(부처님오신날)",
    "2025-10-05": "추석 연휴",
    "2025-10-06": "추석",
    "2025-10-07": "추석 연휴",
    "2025-10-08": "대체공휴일(추석)",
    # 2026
    "2026-02-16": "설날 연휴",
    "2026-02-17": "설날",
    "2026-02-18": "설날 연휴",
    "2026-03-02": "대체공휴일(삼일절)",
    "2026-05-24": "부처님오신날",
    "2026-05-25": "대체공휴일(부처님오신날)",
    "2026-08-17": "대체공휴일(광복절)",
    "2026-09-24": "추석 연휴",
    "2026-09-25": "추석",
    "2026-09-26": "추석 연휴",
    "2026-10-05": "대체공휴일(개천절)",
    # 2027
    "2027-02-06": "설날 연휴",
    "2027-02-07": "설날",
    "2027-02-08": "설날 연휴",
    "2027-02-09": "대체공휴일(설날)",
    "2027-05-13": "부처님오신날",
    "2027-09-14": "추석 연휴",
    "2027-09-15": "추석",
    "2027-09-16": "추석 연휴",
}


def _get_korean_holiday_name(day_date: datetime.date) -> str:
    ymd = day_date.strftime("%Y-%m-%d")
    if ymd in _LUNAR_AND_SUB_HOLIDAYS:
        return _LUNAR_AND_SUB_HOLIDAYS[ymd]
    md = day_date.strftime("%m-%d")
    if md in _FIXED_HOLIDAYS_MD:
        return _FIXED_HOLIDAYS_MD[md]
    if py_holidays is not None:
        try:
            kr_hol = py_holidays.KR(years=day_date.year)
            if day_date in kr_hol:
                return str(kr_hol.get(day_date))
        except Exception:
            pass
    return ""


# =====================================================================
# 지도 탭 복사 주소 공유 헬퍼 ([CAL-12] 연동용)
# =====================================================================
def save_last_copied_map_address(address: str):
    """지도 탭에서 주소 복사 시 호출하면 캘린더에서 바로 불러올 수 있도록 저장"""
    if not address or not address.strip():
        return
    try:
        with open(_SHARED_MAP_ADDR_FILE, "w", encoding="utf-8") as f:
            json.dump({"address": address.strip()}, f, ensure_ascii=False)
    except Exception:
        pass


def _load_last_copied_map_address() -> str:
    try:
        if os.path.exists(_SHARED_MAP_ADDR_FILE):
            with open(_SHARED_MAP_ADDR_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return (data.get("address") or "").strip()
    except Exception:
        pass
    return ""


# =====================================================================
# 캘린더 메인 페이지 빌드 함수
# =====================================================================
def build_calendar_page(on_navigate_to_map=None) -> ft.Container:
    _init_calendar_db()

    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")

    state = {
        "view_year": today.year,
        "view_month": today.month,
        "selected_date": today_str,
        "filter_category": "전체",
        "search_keyword": "",
        "editing_event_id": None,
        "modal_category": "모임",
    }

    root_container_ref = ft.Ref[ft.Container]()

    async def copy_text_safe(text: str):
        if not text:
            return
        try:
            if hasattr(ft, "Clipboard"):
                cb = ft.Clipboard()
                res = cb.set(text)
                if asyncio.iscoroutine(res):
                    await res
                return
        except Exception:
            pass
        try:
            target_page = root_container_ref.current.page if root_container_ref.current else None
            if target_page and hasattr(target_page, "set_clipboard"):
                res = target_page.set_clipboard(text)
                if asyncio.iscoroutine(res):
                    await res
        except Exception:
            pass

    async def read_clipboard_safe() -> str:
        try:
            if hasattr(ft, "Clipboard"):
                cb = ft.Clipboard()
                res = cb.get()
                if asyncio.iscoroutine(res):
                    res = await res
                if res:
                    return str(res).strip()
        except Exception:
            pass
        try:
            target_page = root_container_ref.current.page if root_container_ref.current else None
            if target_page and hasattr(target_page, "get_clipboard"):
                res = target_page.get_clipboard()
                if asyncio.iscoroutine(res):
                    res = await res
                if res:
                    return str(res).strip()
        except Exception:
            pass
        return ""

    # =================================================================
    # [CAL-04] 다가오는 모임 D-Day 배너 UI
    # =================================================================
    dday_badge_text = ft.Text(
        value="D-DAY",
        size=11,
        weight=ft.FontWeight.W_800,
        color=ft.Colors.WHITE,
    )
    dday_badge_box = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=6,
        bgcolor="#0064FF",
        content=dday_badge_text,
    )
    dday_title_text = ft.Text(
        value="예정된 일정이 없습니다.",
        size=12,
        weight=ft.FontWeight.W_700,
        color="#111111",
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        expand=True,
    )
    dday_sub_text = ft.Text(
        value="",
        size=11,
        color="#666666",
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    dday_target = {"event_date": None}

    async def handle_dday_tap(e):
        target_ymd = dday_target["event_date"]
        if not target_ymd:
            return
        try:
            dt = datetime.datetime.strptime(target_ymd, "%Y-%m-%d").date()
            state["view_year"] = dt.year
            state["view_month"] = dt.month
            state["selected_date"] = target_ymd
            state["filter_category"] = "전체"
            state["search_keyword"] = ""
            search_input.value = ""
            refresh_all(do_update=True)
        except Exception:
            pass

    dday_banner = ft.Container(
        visible=False,
        margin=ft.Margin.only(left=14, right=14, top=8, bottom=2),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        bgcolor="#EEF4FF",
        border=ft.Border.all(1, "#C2D8FF"),
        ink=True,
        on_click=handle_dday_tap,
        content=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                dday_badge_box,
                dday_title_text,
                dday_sub_text,
            ],
        ),
    )

    def refresh_dday_banner(do_update: bool = False):
        cur_today_str = datetime.date.today().strftime("%Y-%m-%d")
        upcoming = _db_get_next_upcoming_event(cur_today_str)
        if not upcoming:
            dday_target["event_date"] = None
            dday_banner.visible = False
        else:
            dday_target["event_date"] = upcoming["event_date"]
            target_dt = datetime.datetime.strptime(upcoming["event_date"], "%Y-%m-%d").date()
            diff_days = (target_dt - datetime.date.today()).days
            if diff_days == 0:
                dday_badge_text.value = "오늘"
                dday_badge_box.bgcolor = "#E91E63"
            else:
                dday_badge_text.value = f"D-{diff_days}"
                dday_badge_box.bgcolor = "#0064FF"

            time_prefix = f"{upcoming['event_time']} " if upcoming["event_time"] else ""
            dday_title_text.value = f"{time_prefix}{upcoming['title']}"
            dday_sub_text.value = upcoming["location"] or upcoming["event_date"]
            dday_banner.visible = True

        if do_update:
            dday_banner.update()

    # =================================================================
    # [CAL-03] 연/월 이동 네비게이션 바 UI
    # =================================================================
    month_title_text = ft.Text(
        value=f"{state['view_year']}년 {state['view_month']:02d}월",
        size=16,
        weight=ft.FontWeight.W_800,
        color="#111111",
    )

    async def handle_prev_month(e):
        if state["view_month"] == 1:
            state["view_year"] -= 1
            state["view_month"] = 12
        else:
            state["view_month"] -= 1
        refresh_calendar_grid(do_update=True)

    async def handle_next_month(e):
        if state["view_month"] == 12:
            state["view_year"] += 1
            state["view_month"] = 1
        else:
            state["view_month"] += 1
        refresh_calendar_grid(do_update=True)

    async def handle_go_today(e):
        now_d = datetime.date.today()
        state["view_year"] = now_d.year
        state["view_month"] = now_d.month
        state["selected_date"] = now_d.strftime("%Y-%m-%d")
        refresh_all(do_update=True)

    nav_header_bar = ft.Container(
        padding=ft.Padding.only(left=14, right=14, top=8, bottom=6),
        bgcolor=ft.Colors.WHITE,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                            icon_size=22,
                            icon_color="#222222",
                            padding=0,
                            width=34,
                            height=34,
                            on_click=handle_prev_month,
                        ),
                        month_title_text,
                        ft.IconButton(
                            icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                            icon_size=22,
                            icon_color="#222222",
                            padding=0,
                            width=34,
                            height=34,
                            on_click=handle_next_month,
                        ),
                    ],
                ),
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            height=32,
                            padding=ft.Padding.symmetric(horizontal=10),
                            border_radius=8,
                            bgcolor="#F3F5F7",
                            border=ft.Border.all(1, "#DCDFE4"),
                            alignment=ft.Alignment.CENTER,
                            ink=True,
                            on_click=handle_go_today,
                            content=ft.Text("오늘", size=12, weight=ft.FontWeight.W_700, color="#333333"),
                        ),
                        ft.Container(
                            height=32,
                            padding=ft.Padding.symmetric(horizontal=10),
                            border_radius=8,
                            bgcolor="#0064FF",
                            alignment=ft.Alignment.CENTER,
                            ink=True,
                            on_click=lambda e: open_event_modal(None),
                            content=ft.Text("+ 일정", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ),
                    ],
                ),
            ],
        ),
    )

    # =================================================================
    # [CAL-05] ~ [CAL-08] 월간 달력 그리드 (7열 + 공휴일/주말 + 하이라이트 + 점 표시)
    # =================================================================
    weekday_labels = ["일", "월", "화", "수", "목", "금", "토"]
    weekday_header_row = ft.Row(
        spacing=2,
        controls=[
            ft.Container(
                expand=True,
                height=24,
                alignment=ft.Alignment.CENTER,
                content=ft.Text(
                    value=w_lbl,
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color="#D32F2F" if idx == 0 else ("#0064FF" if idx == 6 else "#555555"),
                ),
            )
            for idx, w_lbl in enumerate(weekday_labels)
        ],
    )

    calendar_weeks_col = ft.Column(spacing=3)

    def handle_day_cell_click(day_date: datetime.date):
        state["selected_date"] = day_date.strftime("%Y-%m-%d")
        if day_date.year != state["view_year"] or day_date.month != state["view_month"]:
            state["view_year"] = day_date.year
            state["view_month"] = day_date.month
        refresh_calendar_grid(do_update=True)
        refresh_event_list(do_update=True)

    def refresh_calendar_grid(do_update: bool = False):
        y = state["view_year"]
        m = state["view_month"]
        month_title_text.value = f"{y}년 {m:02d}월"
        if do_update:
            month_title_text.update()

        month_events_map = _db_get_events_by_month(y, m)
        cur_today = datetime.date.today()

        cal = calendar.Calendar(firstweekday=6)  # 일요일 시작 7열
        weeks = cal.monthdatescalendar(y, m)

        calendar_weeks_col.controls.clear()

        for week in weeks:
            day_cells = []
            for d in week:
                d_str = d.strftime("%Y-%m-%d")
                is_current_month = (d.month == m)
                is_today = (d == cur_today)
                is_selected = (d_str == state["selected_date"])
                holiday_name = _get_korean_holiday_name(d)

                # [CAL-06] 주말 및 공휴일 색상 구분
                if not is_current_month:
                    num_color = "#CCCCCC"
                elif d.weekday() == 6 or holiday_name:
                    num_color = "#D32F2F"
                elif d.weekday() == 5:
                    num_color = "#0064FF"
                else:
                    num_color = "#111111"

                # [CAL-07] 오늘 날짜 및 선택 날짜 하이라이트
                if is_today:
                    day_badge = ft.Container(
                        width=24,
                        height=24,
                        border_radius=12,
                        bgcolor="#0064FF",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(
                            value=str(d.day),
                            size=12,
                            weight=ft.FontWeight.W_800,
                            color=ft.Colors.WHITE,
                        ),
                    )
                else:
                    day_badge = ft.Container(
                        width=24,
                        height=24,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(
                            value=str(d.day),
                            size=12,
                            weight=ft.FontWeight.W_700 if is_selected else ft.FontWeight.W_500,
                            color=num_color,
                        ),
                    )

                # [CAL-08] 일정 보유 날짜 컬러 점(Dot) 인디케이터 (최대 3개)
                day_events = month_events_map.get(d_str, [])
                dots = []
                for ev in day_events[:3]:
                    cat_color = CATEGORIES.get(ev["category"], CATEGORIES["모임"])["color"]
                    dots.append(
                        ft.Container(
                            width=5,
                            height=5,
                            border_radius=3,
                            bgcolor=cat_color if is_current_month else "#DDDDDD",
                        )
                    )

                dot_row = ft.Row(
                    spacing=2,
                    height=6,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=dots,
                )

                cell = ft.Container(
                    expand=True,
                    height=38,
                    border_radius=8,
                    bgcolor="#F2F7FF" if is_selected else ft.Colors.WHITE,
                    border=ft.Border.all(
                        1.5 if is_selected else 0.5,
                        "#0064FF" if is_selected else "#F0F2F5",
                    ),
                    padding=ft.Padding.symmetric(vertical=2),
                    ink=True,
                    on_click=lambda e, target_d=d: handle_day_cell_click(target_d),
                    content=ft.Column(
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[day_badge, dot_row],
                    ),
                )
                day_cells.append(cell)

            calendar_weeks_col.controls.append(ft.Row(spacing=2, controls=day_cells))

        if do_update:
            calendar_weeks_col.update()

    calendar_grid_card = ft.Container(
        margin=ft.Margin.only(left=12, right=12, top=4, bottom=6),
        padding=ft.Padding.all(8),
        bgcolor=ft.Colors.WHITE,
        border_radius=12,
        border=ft.Border.all(1, "#E5E8EB"),
        content=ft.Column(
            spacing=4,
            controls=[
                weekday_header_row,
                calendar_weeks_col,
            ],
        ),
    )

    # =================================================================
    # [CAL-10] 카테고리 필터 및 키워드 검색 바
    # =================================================================
    filter_chips_row = ft.Row(spacing=6)

    def handle_filter_cat_click(cat_name: str):
        state["filter_category"] = cat_name
        rebuild_filter_chips(do_update=True)
        refresh_event_list(do_update=True)

    def rebuild_filter_chips(do_update: bool = False):
        filter_chips_row.controls.clear()
        for cat in ["전체", "모임", "개인", "기념일"]:
            is_active = (state["filter_category"] == cat)
            chip_color = CATEGORIES[cat]["color"] if cat in CATEGORIES else "#222222"
            chip = ft.Container(
                height=28,
                padding=ft.Padding.symmetric(horizontal=10),
                border_radius=14,
                bgcolor=chip_color if is_active else "#F3F5F7",
                border=ft.Border.all(1, chip_color if is_active else "#E0E0E0"),
                alignment=ft.Alignment.CENTER,
                ink=True,
                on_click=lambda e, c=cat: handle_filter_cat_click(c),
                content=ft.Text(
                    value=cat,
                    size=11,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.WHITE if is_active else "#444444",
                ),
            )
            filter_chips_row.controls.append(chip)
        if do_update:
            filter_chips_row.update()

    def handle_event_search_change(e):
        state["search_keyword"] = (search_input.value or "").strip()
        refresh_event_list(do_update=True)

    search_input = ft.TextField(
        hint_text="일정 제목·장소 검색",
        hint_style=ft.TextStyle(color="#888888", size=12),
        color="#111111",
        text_style=ft.TextStyle(color="#111111", size=12, weight=ft.FontWeight.W_600),
        dense=True,
        border=ft.NoInputBorder(),
        bgcolor=ft.Colors.TRANSPARENT,
        content_padding=ft.Padding.symmetric(vertical=0, horizontal=0),
        expand=True,
        on_change=handle_event_search_change,
    )

    search_box = ft.Container(
        height=30,
        expand=True,
        padding=ft.Padding.symmetric(horizontal=10),
        border_radius=15,
        bgcolor="#F3F5F7",
        border=ft.Border.all(1, "#DCDFE4"),
        alignment=ft.Alignment.CENTER,
        content=ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon=ft.Icons.SEARCH_ROUNDED, size=15, color="#777777"),
                search_input,
            ],
        ),
    )

    filter_search_bar = ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=4),
        content=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[filter_chips_row, search_box],
        ),
    )

    # =================================================================
    # [CAL-09] 선택 날짜 상세 일정 리스트 + [CAL-13] 삭제 + [CAL-14] 지도 이동 + [CAL-15] 공지 복사
    # =================================================================
    list_header_text = ft.Text(
        value="",
        size=13,
        weight=ft.FontWeight.W_800,
        color="#111111",
    )
    list_holiday_badge = ft.Container(
        visible=False,
        padding=ft.Padding.symmetric(horizontal=7, vertical=2),
        border_radius=6,
        bgcolor="#FFEBEE",
        content=ft.Text(value="", size=11, weight=ft.FontWeight.W_700, color="#D32F2F"),
    )
    copy_toast_text = ft.Text(
        value="",
        size=11,
        weight=ft.FontWeight.W_700,
        color="#13A84F",
        visible=False,
    )

    events_list_col = ft.Column(
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # [CAL-13] 일정 개별 삭제 처리
    def handle_delete_event(event_id: int):
        _db_delete_event(event_id)
        refresh_all(do_update=True)

    # [CAL-14] 일정 장소 클릭 시 지도 탭 바로가기 연동
    async def handle_open_location_on_map(location_str: str):
        if not location_str:
            return
        await copy_text_safe(location_str)
        if callable(on_navigate_to_map):
            res = on_navigate_to_map(location_str)
            if asyncio.iscoroutine(res):
                await res
        else:
            copy_toast_text.value = f"장소 복사됨 (상단 '지도' 탭에서 검색하세요): {location_str}"
            copy_toast_text.visible = True
            copy_toast_text.update()

    # [CAL-15] 모임 일정 공지 텍스트 복사
    async def handle_copy_announcement(ev: dict):
        try:
            dt = datetime.datetime.strptime(ev["event_date"], "%Y-%m-%d").date()
            w_name = WEEKDAY_NAMES_KO[dt.weekday()]
            date_label = f"{ev['event_date']} ({w_name})"
        except Exception:
            date_label = ev["event_date"]

        time_label = f" {ev['event_time']}" if ev["event_time"] else ""
        lines = [
            f"[{ev['category']} 일정 안내]",
            f"- 일시: {date_label}{time_label}",
            f"- 일정: {ev['title']}",
        ]
        if ev["location"]:
            lines.append(f"- 장소: {ev['location']}")
        if ev["memo"]:
            lines.append(f"- 내용: {ev['memo']}")

        announcement = "\n".join(lines)
        await copy_text_safe(announcement)

        copy_toast_text.value = "모임 안내 문구가 클립보드에 복사되었습니다!"
        copy_toast_text.visible = True
        copy_toast_text.update()

    def build_event_card(ev: dict, show_date_prefix: bool = False) -> ft.Container:
        cat_info = CATEGORIES.get(ev["category"], CATEGORIES["모임"])
        time_display = ev["event_time"] if ev["event_time"] else "종일"
        if show_date_prefix:
            time_display = f"{ev['event_date']} · {time_display}"

        location_widget = (
            ft.Container(
                padding=ft.Padding.only(top=4),
                ink=True,
                on_click=lambda e, loc=ev["location"]: asyncio.create_task(
                    handle_open_location_on_map(loc)
                ),
                content=ft.Row(
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(icon=ft.Icons.LOCATION_ON_ROUNDED, size=14, color="#0064FF"),
                        ft.Text(
                            value=ev["location"],
                            size=12,
                            weight=ft.FontWeight.W_600,
                            color="#0064FF",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                        ft.Text("지도보기 >", size=10, weight=ft.FontWeight.W_700, color="#0064FF"),
                    ],
                ),
            )
            if ev["location"]
            else ft.Container()
        )

        memo_widget = (
            ft.Container(
                padding=ft.Padding.only(top=3),
                content=ft.Text(
                    value=ev["memo"],
                    size=12,
                    color="#555555",
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            )
            if ev["memo"]
            else ft.Container()
        )

        return ft.Container(
            padding=ft.Padding.all(11),
            border_radius=10,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, "#E5E8EB"),
            content=ft.Column(
                spacing=2,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                        border_radius=5,
                                        bgcolor=cat_info["bg"],
                                        content=ft.Text(
                                            value=ev["category"],
                                            size=11,
                                            weight=ft.FontWeight.W_700,
                                            color=cat_info["color"],
                                        ),
                                    ),
                                    ft.Text(
                                        value=time_display,
                                        size=12,
                                        weight=ft.FontWeight.W_700,
                                        color="#444444",
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=2,
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.CONTENT_COPY_ROUNDED,
                                        icon_size=16,
                                        icon_color="#13A84F",
                                        padding=0,
                                        width=28,
                                        height=28,
                                        tooltip="공지 복사",
                                        on_click=lambda e, item=ev: asyncio.create_task(
                                            handle_copy_announcement(item)
                                        ),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_ROUNDED,
                                        icon_size=16,
                                        icon_color="#555555",
                                        padding=0,
                                        width=28,
                                        height=28,
                                        tooltip="수정",
                                        on_click=lambda e, item=ev: open_event_modal(item),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        icon_size=17,
                                        icon_color="#D32F2F",
                                        padding=0,
                                        width=28,
                                        height=28,
                                        tooltip="삭제",
                                        on_click=lambda e, eid=ev["id"]: handle_delete_event(eid),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Text(
                        value=ev["title"],
                        size=14,
                        weight=ft.FontWeight.W_800,
                        color="#111111",
                    ),
                    location_widget,
                    memo_widget,
                ],
            ),
        )

    def refresh_event_list(do_update: bool = False):
        is_filtering = (state["filter_category"] != "전체") or bool(state["search_keyword"])
        events_list_col.controls.clear()

        if is_filtering:
            items = _db_search_events(state["filter_category"], state["search_keyword"])
            list_header_text.value = f"검색·필터 결과 ({len(items)}건)"
            list_holiday_badge.visible = False
            for ev in items:
                events_list_col.controls.append(build_event_card(ev, show_date_prefix=True))
        else:
            sel_str = state["selected_date"]
            try:
                sel_dt = datetime.datetime.strptime(sel_str, "%Y-%m-%d").date()
                w_name = WEEKDAY_NAMES_KO[sel_dt.weekday()]
                hol_name = _get_korean_holiday_name(sel_dt)
            except Exception:
                w_name = ""
                hol_name = ""

            items = _db_get_events_by_date(sel_str)
            list_header_text.value = f"{sel_str} ({w_name}) 일정 ({len(items)}건)"
            if hol_name:
                list_holiday_badge.content.value = hol_name
                list_holiday_badge.visible = True
            else:
                list_holiday_badge.visible = False

            for ev in items:
                events_list_col.controls.append(build_event_card(ev, show_date_prefix=False))

        if not events_list_col.controls:
            events_list_col.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(vertical=24),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        value="등록된 일정이 없습니다. 우측 상단 '+ 일정' 버튼으로 추가해 보세요.",
                        size=12,
                        color="#888888",
                    ),
                )
            )

        if do_update:
            list_header_text.update()
            list_holiday_badge.update()
            events_list_col.update()

    # =================================================================
    # [CAL-11] 일정 등록/수정 팝업 + [CAL-12] 지도 탭 복사 주소 자동 불러오기
    # =================================================================
    modal_title_label = ft.Text("새 일정 등록", size=15, weight=ft.FontWeight.W_800, color="#111111")
    modal_status_text = ft.Text("", size=11, color="#0064FF", visible=False)

    modal_date_input = ft.TextField(
        label="날짜 (YYYY-MM-DD)",
        dense=True,
        text_style=ft.TextStyle(size=13, color="#111111", weight=ft.FontWeight.W_600),
        border=ft.OutlineInputBorder(border_radius=8),
        expand=True,
    )
    modal_time_input = ft.TextField(
        label="시간 (예: 18:30)",
        hint_text="18:30",
        dense=True,
        text_style=ft.TextStyle(size=13, color="#111111", weight=ft.FontWeight.W_600),
        border=ft.OutlineInputBorder(border_radius=8),
        width=120,
    )
    modal_title_input = ft.TextField(
        label="일정 제목 *",
        hint_text="예: 천안 정기 모임",
        dense=True,
        text_style=ft.TextStyle(size=13, color="#111111", weight=ft.FontWeight.W_600),
        border=ft.OutlineInputBorder(border_radius=8),
    )
    modal_location_input = ft.TextField(
        label="장소 / 주소",
        hint_text="직접 입력하거나 우측 버튼 클릭",
        dense=True,
        text_style=ft.TextStyle(size=13, color="#111111", weight=ft.FontWeight.W_600),
        border=ft.OutlineInputBorder(border_radius=8),
        expand=True,
    )
    modal_memo_input = ft.TextField(
        label="메모 / 준비물",
        hint_text="회비, 준비물, 참고사항 등",
        dense=True,
        multiline=True,
        min_lines=2,
        max_lines=3,
        text_style=ft.TextStyle(size=13, color="#111111"),
        border=ft.OutlineInputBorder(border_radius=8),
    )

    modal_cat_row = ft.Row(spacing=8)

    def select_modal_category(cat_name: str, do_update: bool = True):
        state["modal_category"] = cat_name
        modal_cat_row.controls.clear()
        for c_name, c_info in CATEGORIES.items():
            is_sel = (c_name == cat_name)
            btn = ft.Container(
                expand=True,
                height=32,
                border_radius=8,
                bgcolor=c_info["color"] if is_sel else "#F3F5F7",
                border=ft.Border.all(1, c_info["color"] if is_sel else "#DCDFE4"),
                alignment=ft.Alignment.CENTER,
                ink=True,
                on_click=lambda e, cn=c_name: select_modal_category(cn, True),
                content=ft.Text(
                    value=c_name,
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.WHITE if is_sel else "#444444",
                ),
            )
            modal_cat_row.controls.append(btn)
        if do_update:
            modal_cat_row.update()

    # [CAL-12] 지도 탭에서 복사한 주소 자동 불러오기 버튼 핸들러
    async def handle_import_map_address(e):
        shared_addr = _load_last_copied_map_address()
        clip_addr = await read_clipboard_safe()
        chosen = clip_addr or shared_addr
        if chosen:
            modal_location_input.value = chosen
            modal_location_input.update()
            modal_status_text.value = "복사된 주소를 장소 칸에 입력했습니다."
            modal_status_text.color = "#13A84F"
            modal_status_text.visible = True
            modal_status_text.update()
        else:
            modal_status_text.value = "복사된 주소가 없습니다. 지도 탭에서 위치를 먼저 선택해 주세요."
            modal_status_text.color = "#D32F2F"
            modal_status_text.visible = True
            modal_status_text.update()

    import_map_addr_btn = ft.Container(
        height=40,
        padding=ft.Padding.symmetric(horizontal=10),
        border_radius=8,
        bgcolor="#EEF4FF",
        border=ft.Border.all(1, "#C2D8FF"),
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=handle_import_map_address,
        content=ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon=ft.Icons.LOCATION_ON_ROUNDED, size=15, color="#0064FF"),
                ft.Text("지도 주소", size=11, weight=ft.FontWeight.W_700, color="#0064FF"),
            ],
        ),
    )

    def close_event_modal(e=None):
        modal_overlay.visible = False
        modal_overlay.update()

    def handle_save_event(e):
        date_val = (modal_date_input.value or "").strip()
        time_val = (modal_time_input.value or "").strip()
        title_val = (modal_title_input.value or "").strip()
        loc_val = (modal_location_input.value or "").strip()
        memo_val = (modal_memo_input.value or "").strip()
        cat_val = state["modal_category"]

        if not title_val:
            modal_status_text.value = "일정 제목을 입력해 주세요."
            modal_status_text.color = "#D32F2F"
            modal_status_text.visible = True
            modal_status_text.update()
            return

        try:
            parsed_d = datetime.datetime.strptime(date_val, "%Y-%m-%d").date()
        except ValueError:
            modal_status_text.value = "날짜 형식은 YYYY-MM-DD (예: 2026-11-20)로 입력해 주세요."
            modal_status_text.color = "#D32F2F"
            modal_status_text.visible = True
            modal_status_text.update()
            return

        if state["editing_event_id"] is not None:
            _db_update_event(
                state["editing_event_id"],
                date_val,
                time_val,
                title_val,
                loc_val,
                cat_val,
                memo_val,
            )
        else:
            _db_insert_event(
                date_val,
                time_val,
                title_val,
                loc_val,
                cat_val,
                memo_val,
            )

        state["view_year"] = parsed_d.year
        state["view_month"] = parsed_d.month
        state["selected_date"] = date_val
        modal_overlay.visible = False
        modal_overlay.update()
        refresh_all(do_update=True)

    def open_event_modal(ev: dict | None = None):
        modal_status_text.visible = False
        if ev is not None:
            state["editing_event_id"] = ev["id"]
            modal_title_label.value = "일정 수정"
            modal_date_input.value = ev["event_date"]
            modal_time_input.value = ev["event_time"]
            modal_title_input.value = ev["title"]
            modal_location_input.value = ev["location"]
            modal_memo_input.value = ev["memo"]
            select_modal_category(ev["category"], do_update=False)
        else:
            state["editing_event_id"] = None
            modal_title_label.value = "새 일정 등록"
            modal_date_input.value = state["selected_date"]
            modal_time_input.value = ""
            modal_title_input.value = ""
            modal_location_input.value = ""
            modal_memo_input.value = ""
            select_modal_category("모임", do_update=False)

        modal_overlay.visible = True
        modal_overlay.update()

    modal_card = ft.Container(
        width=340,
        padding=ft.Padding.all(16),
        border_radius=14,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, "#DCDFE4"),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=16,
            color="#40000000",
            offset=ft.Offset(0, 4),
        ),
        content=ft.Column(
            spacing=10,
            tight=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        modal_title_label,
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=20,
                            icon_color="#666666",
                            padding=0,
                            width=28,
                            height=28,
                            on_click=close_event_modal,
                        ),
                    ],
                ),
                modal_cat_row,
                ft.Row(spacing=8, controls=[modal_date_input, modal_time_input]),
                modal_title_input,
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[modal_location_input, import_map_addr_btn],
                ),
                modal_memo_input,
                modal_status_text,
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Container(
                            expand=True,
                            height=38,
                            border_radius=8,
                            bgcolor="#F3F5F7",
                            alignment=ft.Alignment.CENTER,
                            ink=True,
                            on_click=close_event_modal,
                            content=ft.Text("취소", size=13, weight=ft.FontWeight.W_700, color="#444444"),
                        ),
                        ft.Container(
                            expand=True,
                            height=38,
                            border_radius=8,
                            bgcolor="#0064FF",
                            alignment=ft.Alignment.CENTER,
                            ink=True,
                            on_click=handle_save_event,
                            content=ft.Text("저장", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ),
                    ],
                ),
            ],
        ),
    )

    modal_overlay = ft.Container(
        visible=False,
        expand=True,
        bgcolor="#66000000",
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.all(16),
        content=modal_card,
    )

    # =================================================================
    # 초기 데이터 렌더링 및 레이아웃 조립
    # =================================================================
    def refresh_all(do_update: bool = False):
        refresh_dday_banner(do_update=do_update)
        refresh_calendar_grid(do_update=do_update)
        rebuild_filter_chips(do_update=do_update)
        refresh_event_list(do_update=do_update)

    refresh_all(do_update=False)

    list_section = ft.Container(
        expand=True,
        padding=ft.Padding.only(left=14, right=14, top=4, bottom=10),
        content=ft.Column(
            expand=True,
            spacing=6,
            controls=[
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        list_header_text,
                        list_holiday_badge,
                    ],
                ),
                copy_toast_text,
                events_list_col,
            ],
        ),
    )

    main_column = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            nav_header_bar,     # [CAL-03] 연/월 이동 + 오늘 + 일정 추가
            dday_banner,        # [CAL-04] 다가오는 모임 D-Day 배너
            calendar_grid_card, # [CAL-05]~[CAL-08] 7열 달력 + 공휴일 + 하이라이트 + 점
            filter_search_bar,  # [CAL-10] 카테고리 필터 + 검색
            list_section,       # [CAL-09], [CAL-13]~[CAL-15] 상세 일정 리스트
        ],
    )

    return ft.Container(
        ref=root_container_ref,
        expand=True,
        bgcolor="#FAFAFA",
        content=ft.Stack(
            expand=True,
            controls=[
                main_column,
                modal_overlay,  # [CAL-11], [CAL-12] 등록/수정 및 지도 주소 가져오기 팝업
            ],
        ),
    )