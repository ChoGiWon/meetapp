import flet as ft


def build_memo_page() -> ft.Container:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        bgcolor="#FAFAFA",
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Icon(icon=ft.Icons.EDIT_NOTE_ROUNDED, size=56, color="#13A84F"),
                ft.Text("메모장", size=24, weight=ft.FontWeight.BOLD, color="#222222"),
                ft.Text("회의록, 준비물, 공지 메모를 기록하는 공간입니다.", size=14, color="#666666"),
            ],
        ),
    )