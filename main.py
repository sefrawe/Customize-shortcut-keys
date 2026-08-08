''' 入口文件，启动应用程序 '''
import sys
import ctypes
import platform
import threading

from tkinter import messagebox
import customtkinter as ctk
from core.executor import Executor
from gui.MainWindow import MainWindow
from gui.trayIcon import TrayIconManager


def check_single_instance():
    """
    使用 Windows 互斥锁检测是否已有实例运行。
    返回 True 表示是首个实例，False 表示已有实例在运行。
    """
    if platform.system() != "Windows":
        return True  # 非 Windows 系统暂时跳过单例检测

    # 定义互斥锁名称（建议加上 Global\\ 前缀，确保跨会话有效，但仅当前用户可不加）
    mutex_name = "CustomShortcutKeys_App_Mutex"

    # 尝试创建一个已命名的互斥锁
    # 参数：默认安全属性，初始不拥有，锁名称
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)

    # 获取错误码。如果错误码是 183 (ERROR_ALREADY_EXISTS)，说明锁已存在（已有实例运行）
    if ctypes.windll.kernel32.GetLastError() == 183:
        return False
    return True

def main():
    # ===== 新增：单实例检测 =====
    if not check_single_instance():
        # 隐藏掉 Tkinter 默认的隐藏根窗口，只显示弹窗
        root = ctk.CTk()
        root.withdraw()
        messagebox.showwarning("提示", "自定义快捷键工具已在后台运行，请勿重复启动。")
        root.destroy()
        sys.exit(0)
    # ============================

    executor = Executor()
    app = MainWindow(executor=executor)

    # 删除了原本注释掉的旧检测逻辑

    ctk.set_default_color_theme("dark-blue") # Themes: "blue" (standard), "green", "dark-blue"
    executor.setTipCallback(app.showExecutorTip)

    # 新增：初始化系统托盘
    tray = TrayIconManager(app)
    app.set_tray_icon(tray)

    # 新增：将托盘图标运行放入守护线程
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    # 新增：检查静默启动参数
    if "--minimized" in sys.argv or "--silent" in sys.argv:
        app.withdraw() # 不显示主窗口，直接驻留托盘
    else:
        # 只有非静默启动时才最大化
        app.after(100, lambda: app.state("zoomed"))

    executor.start()

    try:
        app.mainloop()

    finally:
        executor.stop()

if __name__ == "__main__":
    main()
