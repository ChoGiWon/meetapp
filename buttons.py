import flet as ft

# =====================================================================
# [1] 메뉴 버튼 공통 UI 매개변수 관리 영역
# =====================================================================
MENU_BTN_CONFIG = {
    "height": 42,
    "padding_horizontal": 16,
    "border_radius": 21,
    "bg_color": "#F3F5F7",
    "active_bg_color": "#13A84F",
    "text_color": "#222222",
    "active_text_color": ft.Colors.WHITE,
    "border_color": "#E2E6EA",
    "font_size": 14,
    "icon_size": 18,
    "spacing": 6,
}


# =====================================================================
# [2] 버튼 전용 관리 클래스
# =====================================================================
class MenuButtonManager:
    def __init__(self, on_menu_selected=None):
        self.on_menu_selected = on_menu_selected
        self.buttons = []

        # 6개 메뉴 데이터 정의 (메모장 우측에 '지도' 추가)
        self.menu_items = [
            {"label": "메인화면", "icon": ft.Icons.HOME_ROUNDED},
            {"label": "캘린더", "icon": ft.Icons.CALENDAR_MONTH_ROUNDED},
            {"label": "사진첩", "icon": ft.Icons.PHOTO_LIBRARY_ROUNDED},
            {"label": "채팅창", "icon": ft.Icons.CHAT_BUBBLE_ROUNDED},
            {"label": "메모장", "icon": ft.Icons.EDIT_NOTE_ROUNDED},
            {"label": "지도", "icon": ft.Icons.MAP_ROUNDED},
        ]

    def _handle_click(self, e, selected_label: str):
        """버튼 클릭 시 활성/비활성 스타일 업데이트 및 선택된 메뉴 이름 전달"""
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

        if self.on_menu_selected:
            self.on_menu_selected(selected_label)

    def build_menu_buttons(self) -> list[ft.Container]:
        """6개의 메뉴 버튼 위젯 리스트 생성"""
        self.buttons.clear()

        for idx, item in enumerate(self.menu_items):
            is_first = (idx == 0)
            label = item["label"]
            icon = item["icon"]

            btn = ft.Container(
                data=label,
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
                    tight=True,
                ),
            )
            self.buttons.append(btn)

        return self.buttons