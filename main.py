import flet as ft
from buttons import MenuButtonManager
from pages.home_page import build_home_page
from pages.calendar_page import build_calendar_page
from pages.gallery_page import build_gallery_page
from pages.chat_page import build_chat_page
from pages.memo_page import build_memo_page
from pages.map_page import build_map_page

# =====================================================================
# [버전 관리] 코드 업데이트 버전 텍스트 (수정 시 여기만 변경)
# =====================================================================
APP_VERSION = "v 0.0.2"


def main(page: ft.Page):
    # 1. 앱 기본 메타데이터 및 배경 설정
    page.title = "meetapp"
    page.bgcolor = ft.Colors.WHITE
    page.padding = 0
    page.spacing = 0

    # 2. 데스크톱 테스트용 모바일 창 크기
    page.window.width = 390
    page.window.height = 844

    # 3. 6개 메뉴 이름과 실제 페이지 위젯 매핑
    page_views = {
        "메인화면": build_home_page(),
        "캘린더": build_calendar_page(),
        "사진첩": build_gallery_page(),
        "채팅창": build_chat_page(),
        "메모장": build_memo_page(),
        "지도": build_map_page(),
    }

    # 4. 본문 영역 컨테이너 (초기 화면은 '메인화면')
    body_area = ft.Container(
        expand=True,
        bgcolor="#FAFAFA",
        content=page_views["메인화면"],
    )

    # 버튼 클릭 시 본문 영역의 페이지를 교체하는 함수
    def handle_menu_change(selected_label: str):
        if selected_label in page_views:
            body_area.content = page_views[selected_label]
            body_area.update()

    # 5. 버튼 전용 매니저 생성 및 6개 버튼 불러오기
    btn_manager = MenuButtonManager(on_menu_selected=handle_menu_change)
    menu_button_list = btn_manager.build_menu_buttons()

    # 6. 지도 버튼 우측에 배치할 코드 업데이트 버전 텍스트 위젯
    version_text = ft.Container(
        padding=ft.Padding.only(left=4, right=8),
        alignment=ft.Alignment.CENTER,
        content=ft.Text(
            value=APP_VERSION,
            size=12,
            weight=ft.FontWeight.W_600,
            color="#888888",
        ),
    )

    # 7. [위치 관리] 맨 위 상태바(시간 영역) 컬러 박스
    status_bar_box = ft.Container(
        height=36,
        bgcolor="#535353",
    )

    # 8. [위치 관리] 화면 상단 메뉴 버튼 + 우측 버전 텍스트 배치 영역
    top_menu_bar = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=12, bottom=12),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.only(bottom=ft.BorderSide(1, "#EEEEEE")),
        content=ft.Row(
            controls=[
                *menu_button_list,  # 1~6번 버튼 (메인화면 ~ 지도)
                version_text,       # 마지막 버튼 우측 업데이트 버전 표시
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.HIDDEN,
        ),
    )

    # 9. 전체 화면 조립 (단일 3단 Column 구조)
    main_layout = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            status_bar_box,  # 1층: 맨 위 상태바(시간/배터리) 배경 박스
            top_menu_bar,    # 2층: 상단 6개 메뉴 버튼 + 버전 텍스트
            body_area,       # 3층: 선택된 메뉴에 따라 바뀌는 페이지 영역
        ],
    )

    page.add(main_layout)
    page.update()


if __name__ == "__main__":
    ft.run(main)