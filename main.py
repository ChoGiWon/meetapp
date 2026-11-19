import flet as ft
from buttons import MenuButtonManager


def main(page: ft.Page):
    # 1. 앱 기본 메타데이터 및 배경 설정
    page.title = "meetapp"
    page.bgcolor = ft.Colors.WHITE
    page.padding = 0

    # 2. 데스크톱 테스트용 모바일 창 크기
    page.window.width = 390
    page.window.height = 844

    # 선택된 메뉴 상태를 화면 중앙에서 확인하기 위한 임시 텍스트
    status_text = ft.Text(
        value="현재 선택된 메뉴: 전체모임",
        size=18,
        weight=ft.FontWeight.W_600,
        color="#333333",
    )

    # 버튼 클릭 시 메인 화면에서 처리할 동작 연결
    def handle_menu_change(selected_label: str):
        status_text.value = f"현재 선택된 메뉴: {selected_label}"
        status_text.update()

    # 3. 버튼 전용 매니저 인스턴스 생성 및 5개 버튼 가져오기
    btn_manager = MenuButtonManager(on_menu_selected=handle_menu_change)
    menu_button_list = btn_manager.build_menu_buttons()

    # 4. [위치 관리] 화면 상단 메뉴 버튼 배치 영역 (가로 스크롤 지원)
    top_menu_bar = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=12, bottom=12),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.only(bottom=ft.BorderSide(1, "#EEEEEE")),
        content=ft.Row(
            controls=menu_button_list,
            spacing=10,                        # 버튼과 버튼 사이의 가로 간격
            scroll=ft.ScrollMode.HIDDEN,       # 모바일 화면 폭을 넘어가면 손가락/마우스로 자연스럽게 가로 스크롤
        ),
    )

    # 5. [위치 관리] 하단 본문 영역
    body_area = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        bgcolor="#FAFAFA",
        content=status_text,
    )

    # 6. 전체 화면 조립 (상단 메뉴바 + 하단 본문)
    base_screen = ft.SafeArea(
        expand=True,
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                top_menu_bar,  # 최상단 배치
                body_area,     # 나머지 아래 공간 전체 배치
            ],
        ),
    )

    page.add(base_screen)


if __name__ == "__main__":
    ft.run(main)