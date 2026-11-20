import flet as ft
from pages.map_page import build_map_page
from pages.calendar_page import build_calendar_page


def main(page: ft.Page):
    page.title = "MeetApp"
    page.bgcolor = "#FAFAFA"
    page.padding = 0
    page.spacing = 0

    # =================================================================
    # [1] 기본 채팅창 / 메모장 화면 (기존 작성 코드가 있다면 교체 가능)
    # =================================================================
    chat_messages = ft.Column(
        expand=True,
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=ft.Padding.all(12),
                border_radius=10,
                bgcolor=ft.Colors.WHITE,
                border=ft.Border.all(1, "#E5E8EB"),
                content=ft.Text(
                    "모임 채팅방입니다. 캘린더에서 복사한 일정 공지를 붙여넣어 공유해 보세요.",
                    size=13,
                    color="#333333",
                ),
            )
        ],
    )

    chat_input = ft.TextField(
        hint_text="메시지 입력 (공지 붙여넣기 가능)",
        dense=True,
        expand=True,
        border=ft.OutlineInputBorder(border_radius=8),
        text_style=ft.TextStyle(size=13, color="#111111"),
    )

    def handle_send_chat(e):
        msg = (chat_input.value or "").strip()
        if not msg:
            return
        chat_messages.controls.append(
            ft.Container(
                padding=ft.Padding.all(10),
                border_radius=10,
                bgcolor="#EEF4FF",
                border=ft.Border.all(1, "#C2D8FF"),
                content=ft.Text(msg, size=13, color="#111111"),
            )
        )
        chat_input.value = ""
        chat_messages.update()
        chat_input.update()

    chat_view = ft.Container(
        expand=True,
        padding=ft.Padding.all(14),
        content=ft.Column(
            expand=True,
            spacing=10,
            controls=[
                chat_messages,
                ft.Row(
                    spacing=8,
                    controls=[
                        chat_input,
                        ft.Container(
                            height=40,
                            padding=ft.Padding.symmetric(horizontal=14),
                            border_radius=8,
                            bgcolor="#13A84F",
                            alignment=ft.Alignment.CENTER,
                            ink=True,
                            on_click=handle_send_chat,
                            content=ft.Text("전송", size=13, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                        ),
                    ],
                ),
            ],
        ),
    )

    memo_input = ft.TextField(
        hint_text="모임 메모를 자유롭게 입력하세요...",
        multiline=True,
        min_lines=12,
        expand=True,
        border=ft.OutlineInputBorder(border_radius=10),
        bgcolor=ft.Colors.WHITE,
        text_style=ft.TextStyle(size=14, color="#111111"),
    )

    memo_view = ft.Container(
        expand=True,
        padding=ft.Padding.all(14),
        content=ft.Column(
            expand=True,
            spacing=8,
            controls=[
                ft.Text("공용 메모장", size=15, weight=ft.FontWeight.W_800, color="#111111"),
                memo_input,
            ],
        ),
    )

    # =================================================================
    # [2] 상단 메뉴 구성 및 화면 전환 로직
    # =================================================================
    menu_items = [
        {"name": "채팅창", "icon": ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED},
        {"name": "메모장", "icon": ft.Icons.EDIT_NOTE_ROUNDED},
        {"name": "지도", "icon": ft.Icons.MAP_OUTLINED},
        {"name": "캘린더", "icon": ft.Icons.CALENDAR_MONTH_ROUNDED},
    ]

    menu_buttons: dict[str, ft.Container] = {}
    body_area = ft.Container(expand=True)

    def select_menu(selected_name: str):
        """상단 탭 버튼 색상 변경 및 본문 화면 전환"""
        for m_name, btn in menu_buttons.items():
            is_active = (m_name == selected_name)
            btn.bgcolor = "#13A84F" if is_active else "#F3F5F7"
            btn.border = ft.Border.all(1, "#13A84F" if is_active else "#E0E0E0")
            row_controls = btn.content.controls
            row_controls[0].color = ft.Colors.WHITE if is_active else "#333333"
            row_controls[1].color = ft.Colors.WHITE if is_active else "#333333"

        body_area.content = pages[selected_name]
        page.update()

    def open_map_from_calendar(location_str: str):
        """[CAL-14] 캘린더 일정에서 장소 클릭 시 '지도' 탭으로 즉시 이동"""
        select_menu("지도")

    pages = {
        "채팅창": chat_view,
        "메모장": memo_view,
        "지도": build_map_page(),
        "캘린더": build_calendar_page(on_navigate_to_map=open_map_from_calendar),
    }

    nav_controls = []
    for item in menu_items:
        m_name = item["name"]
        is_default = (m_name == "지도")
        btn = ft.Container(
            expand=True,
            height=38,
            border_radius=19,
            bgcolor="#13A84F" if is_default else "#F3F5F7",
            border=ft.Border.all(1, "#13A84F" if is_default else "#E0E0E0"),
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=lambda e, name=m_name: select_menu(name),
            content=ft.Row(
                spacing=4,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        icon=item["icon"],
                        size=15,
                        color=ft.Colors.WHITE if is_default else "#333333",
                    ),
                    ft.Text(
                        value=m_name,
                        size=12,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.WHITE if is_default else "#333333",
                    ),
                ],
            ),
        )
        menu_buttons[m_name] = btn
        nav_controls.append(btn)

    nav_controls.append(
        ft.Text("v 0.0.3", size=11, color="#777777", weight=ft.FontWeight.W_600)
    )

    top_header = ft.Container(
        padding=ft.Padding.only(left=12, right=12, top=10, bottom=8),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.only(bottom=ft.BorderSide(1, "#EEEEEE")),
        content=ft.Row(
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=nav_controls,
        ),
    )

    body_area.content = pages["지도"]

    page.add(
        ft.Column(
            expand=True,
            spacing=0,
            controls=[
                top_header,
                body_area,
            ],
        )
    )


if __name__ == "__main__":
    ft.app(main)