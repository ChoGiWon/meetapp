import flet as ft


def build_gallery_page() -> ft.Container:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        bgcolor="#FAFAFA",
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Icon(icon=ft.Icons.PHOTO_LIBRARY_ROUNDED, size=56, color="#13A84F"),
                ft.Text("사진첩", size=24, weight=ft.FontWeight.BOLD, color="#222222"),
                ft.Text("모임 활동 사진을 공유하고 모아보는 공간입니다.", size=14, color="#666666"),
            ],
        ),
    )