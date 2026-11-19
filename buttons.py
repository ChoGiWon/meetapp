import flet as ft

# =====================================================================
# [1] 메뉴 버튼 공통 UI 매개변수 관리 영역 (여기 수치만 바꾸면 전체 일괄 적용)
# =====================================================================
MENU_BTN_CONFIG = {
    "height": 42,
    "padding_horizontal": 16,
    "border_radius": 21,           # 높이의 절반으로 설정해 깔끔한 알약(Pill) 형태 구현
    "bg_color": "#F3F5F7",         # 기본 연회색 배경
    "active_bg_color": "#13A84F",  # 선택 시 메인 포인트 초록색
    "text_color": "#222222",
    "active_text_color": ft.Colors.WHITE,
    "border_color": "#E2E6EA",
    "font_size": 14,
    "icon_size": 18,
    "spacing": 6,                  # 버튼 내부 아이콘과 텍스트 사이 간격
}


# =====================================================================
# [2] 버튼 전용 관리 클래스 (기능 + UI 통합)
# =====================================================================
class MenuButtonManager:
    def __init__(self, on_menu_selected=None):
        """
        on_menu_selected: 버튼 클릭 시 main 페이지로 선택된 메뉴 이름을 전달할 콜백 함수
        """
        self.on_menu_selected = on_menu_selected
        self.buttons = []  # 생성된 5개 버튼 객체를 추적하여 활성/비활성 상태 관리

        # 임시 메뉴 5개 데이터 정의 (라벨 + 어울리는 아이콘)
        self.menu_items = [
            {"label": "전체모임", "icon": ft.Icons.GRID_VIEW_ROUNDED},
            {"label": "운동·스포츠", "icon": ft.Icons.FITNESS_CENTER_ROUNDED},
            {"label": "맛집·카페", "icon": ft.Icons.RESTAURANT_ROUNDED},
            {"label": "스터디", "icon": ft.Icons.MENU_BOOK_ROUNDED},
            {"label": "친목·여행", "icon": ft.Icons.FLIGHT_TAKEOFF_ROUNDED},
        ]

    def _handle_click(self, e, selected_label: str):
        """버튼 클릭 시 실행되는 내부 기능: 선택된 버튼 스타일 강조 및 외부 알림"""
        # 1. 모든 버튼의 색상을 초기화하고, 클릭된 버튼만 포인트 컬러로 변경
        for btn in self.buttons:
            is_selected = (btn.data == selected_label)
            btn.bgcolor = (
                MENU_BTN_CONFIG["active_bg_color"]
                if is_selected
                else MENU_BTN_CONFIG["bg_color"]
            )
            btn.border = ft.Border.all(
                1,
                MENU_BTN_CONFIG["active_bg_color"]
                if is_selected
                else MENU_BTN_CONFIG["border_color"],
            )
            # 내부 Row 안의 Icon과 Text 색상 변경
            row_controls = btn.content.controls
            row_controls[0].color = (
                MENU_BTN_CONFIG["active_text_color"]
                if is_selected
                else MENU_BTN_CONFIG["active_bg_color"]
            )
            row_controls[1].color = (
                MENU_BTN_CONFIG["active_text_color"]
                if is_selected
                else MENU_BTN_CONFIG["text_color"]
            )
            btn.update()

        # 2. main 페이지에 어떤 메뉴가 눌렸는지 전달
        if self.on_menu_selected:
            self.on_menu_selected(selected_label)

    def build_menu_buttons(self) -> list[ft.Container]:
        """설정된 매개변수를 바탕으로 5개의 메뉴 버튼 위젯 리스트를 생성해 반환"""
        self.buttons.clear()

        for idx, item in enumerate(self.menu_items):
            is_first = (idx == 0)  # 첫 번째 버튼('전체모임')을 기본 선택 상태로 표시
            label = item["label"]
            icon = item["icon"]

            btn = ft.Container(
                data=label,  # 버튼 식별용 이름 저장
                height=MENU_BTN_CONFIG["height"],
                padding=ft.Padding.symmetric(horizontal=MENU_BTN_CONFIG["padding_horizontal"]),
                border_radius=MENU_BTN_CONFIG["border_radius"],
                bgcolor=(
                    MENU_BTN_CONFIG["active_bg_color"]
                    if is_first
                    else MENU_BTN_CONFIG["bg_color"]
                ),
                border=ft.Border.all(
                    1,
                    MENU_BTN_CONFIG["active_bg_color"]
                    if is_first
                    else MENU_BTN_CONFIG["border_color"],
                ),
                alignment=ft.Alignment.CENTER,
                # 부드러운 터치 반응(잉크 효과) 및 클릭 이벤트 연결
                ink=True,
                on_click=lambda e, lbl=label: self._handle_click(e, lbl),
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            icon=icon,
                            size=MENU_BTN_CONFIG["icon_size"],
                            color=(
                                MENU_BTN_CONFIG["active_text_color"]
                                if is_first
                                else MENU_BTN_CONFIG["active_bg_color"]
                            ),
                        ),
                        ft.Text(
                            value=label,
                            size=MENU_BTN_CONFIG["font_size"],
                            weight=ft.FontWeight.W_600,
                            color=(
                                MENU_BTN_CONFIG["active_text_color"]
                                if is_first
                                else MENU_BTN_CONFIG["text_color"]
                            ),
                        ),
                    ],
                    spacing=MENU_BTN_CONFIG["spacing"],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,  # 내용물 크기만큼만 가로 너비 차지
                ),
            )
            self.buttons.append(btn)

        return self.buttons