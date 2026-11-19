import flet as ft


def build_chat_page() -> ft.Container:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        bgcolor="#FAFAFA",
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Icon(icon=ft.Icons.CHAT_BUBBLE_ROUNDED, size=56, color="#13A84F"),
                ft.Text("채팅창", size=24, weight=ft.FontWeight.BOLD, color="#222222"),
                ft.Text("멤버들과 실시간 대화를 나누는 채팅방입니다.", size=14, color="#666666"),
            ],
        ),
    )