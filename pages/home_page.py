import flet as ft


def build_home_page() -> ft.Container:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        bgcolor="#FAFAFA",
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Icon(icon=ft.Icons.HOME_ROUNDED, size=56, color="#13A84F"),
                ft.Text("메인화면", size=24, weight=ft.FontWeight.BOLD, color="#222222"),
                ft.Text("모임 공지 및 주요 피드가 표시되는 공간입니다.", size=14, color="#666666"),
            ],
        ),
    )       