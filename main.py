'''
入口文件，启动应用程序
'''
import sys
import threading

import customtkinter as ctk

from core.executor import Executor
from gui.MainWindow import MainWindow
from gui.trayIcon import TrayIconManager


def main():
    executor = Executor()
    ctk.set_default_color_theme("dark-blue")  # Themes: "blue" (standard), "green", "dark-blue"
    app = MainWindow(executor=executor)
    executor.setTipCallback(app.showExecutorTip)

    # 新增：初始化系统托盘
    tray = TrayIconManager(app)
    app.set_tray_icon(tray)

    # 新增：将托盘图标运行放入守护线程
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    # 新增：检查静默启动参数
    if "--minimized" in sys.argv or "--silent" in sys.argv:
        app.withdraw()  # 不显示主窗口，直接驻留托盘

    executor.start()
    try:
        app.mainloop()
    finally:
        executor.stop()


if __name__ == "__main__":
    main()
