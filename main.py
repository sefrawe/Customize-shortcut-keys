'''
入口文件，启动应用程序
'''
import customtkinter as ctk

from core.executor import Executor
from gui.MainWindow import MainWindow


def main():
    executor = Executor()
    ctk.set_default_color_theme("dark-blue")  # Themes: "blue" (standard), "green", "dark-blue"
    app = MainWindow(executor=executor)
    executor.setTipCallback(app.showExecutorTip)
    executor.start()
    try:
        app.mainloop()
    finally:
        executor.stop()


if __name__ == "__main__":
    main()
