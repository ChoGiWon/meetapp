import flet as ft

def main(page: ft.Page):
    # 1. 앱 기본 메타데이터 및 배경 설정
    page.title = "Cross-Platform Base App"
    page.bgcolor = ft.Colors.WHITE
    page.padding = 0

    # 2. 데스크톱 테스트용 창 크기 (실제 모바일 기기에서는 기기 해상도에 맞춰 자동 무시됨)
    page.window.width = 390
    page.window.height = 844

    # 3. 모바일 기기 상단 노치 및 하단 홈 바 영역 보호를 위한 빈 기본 컨테이너
    base_screen = ft.SafeArea(
        content=ft.Container(
            expand=True,
            bgcolor=ft.Colors.WHITE,
        ),
        expand=True,
    )

    # 4. 화면에 기본 컨테이너 추가
    page.add(base_screen)

if __name__ == "__main__":
    ft.run(main)