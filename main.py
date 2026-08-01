'''
入口文件，启动应用程序
'''
import customtkinter as ctk
from gui.MainWindow import MainWindow


def main():
    ctk.set_default_color_theme("dark-blue")  # Themes: "blue" (standard), "green", "dark-blue"
    # 创建主窗口
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
