''' 入口文件，启动应用程序 '''
import sys
import ctypes

# use_last_error=True：让 ctypes 在每次调用后把 GetLastError 快照到线程私有
# 缓冲，配 ctypes.get_last_error() 读取。原写法 ctypes.windll 共享全局
# last error，中间任何 ctypes 调用都可能污染读数，造成"明明没实例却误判
# 已存在"或反之。这是 WinAPI 调用的标准姿势（34 号定稿 E 节第 2 条）。
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

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
    # 尝试创建一个已命名的互斥锁
    # 参数：默认安全属性，初始不拥有，锁名称
    mutex = _kernel32.CreateMutexW(None, False, mutex_name)

    # 获取错误码。如果错误码是 183 (ERROR_ALREADY_EXISTS)，说明锁已存在（已有实例运行）
    # 34 号：改用 ctypes.get_last_error()（配 use_last_error=True 的线程私有
    # 快照），不再读可能被中间调用污染的全局 last error
    if ctypes.get_last_error() == 183:
        return False

    return True

def main():
    # ===== 新增：单实例检测 =====
    if not check_single_instance():
        # ==================== 34 号新增：静默启动撞单例不弹窗 ==================
        # 开机自启路径带 --silent/--minimized；若此刻已有实例在跑（典型：
        # 用户手动开过软件，重启电脑触发自启竞态），弹警告窗违背静默语义
        # （用户什么都没做却弹出窗口）。静默路径直接退出即可——已有实例
        # 正常服务，无需任何用户交互。
        if "--minimized" in sys.argv or "--silent" in sys.argv:
            sys.exit(0)
        # ======================================================================
        # 隐藏掉 Tkinter 默认的隐藏根窗口，只显示弹窗
        root = ctk.CTk()
        root.withdraw()
        messagebox.showwarning("提示", "自定义快捷键工具已在后台运行，请勿重复启动。")
        root.destroy()
        sys.exit(0)


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
        pass
        # 只有非静默启动时才最大化
        # app.after(100, lambda: app.state("zoomed"))

    executor.start()

    try:
        app.mainloop()

    finally:
        executor.stop()


if __name__ == "__main__":
    main()
