import customtkinter as ctk
from gui.main_window import MainWindow


def main():
    # 设置CustomTkinter的外观和主题
    ctk.set_appearance_mode("light")  # 可选: "light", "dark", "system"
    ctk.set_default_color_theme("blue")

    # 创建主窗口
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()