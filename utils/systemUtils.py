''' 系统相关工具 '''
import sys
import os
import platform

# 注册表自启动项的路径
AUTO_START_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
# 注册表中的键名
APP_NAME = "CustomShortcutKeys"


def get_app_command():
    """
    获取程序的启动命令（包含静默参数 --silent）
    开发环境: "pythonw.exe路径" "main.py路径" --silent
    打包后:   "exe路径" --silent
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的 exe 路径
        app_path = f'"{sys.executable}"'
    else:
        # 开发环境：用 pythonw.exe 隐藏命令行窗口
        pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        app_path = f'"{pythonw_path}" "{os.path.abspath(sys.argv[0])}"'
    # 拼接静默启动参数
    return f"{app_path} --silent"



def set_auto_start(enable: bool) -> bool:
    r"""
    设置或取消开机自启动。
    向 HKEY_CURRENT_USER\...\Run 写入/删除键值对。
    返回 True 表示操作成功，False 表示失败。
    """
    if platform.system() != "Windows":
        print("非 Windows 系统，不支持开机自启动")
        return False

    import winreg
    try:
        # 打开注册表项（HKEY_CURRENT_USER 下，不需要管理员权限）
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTO_START_REG_PATH,
            0,
            winreg.KEY_SET_VALUE
        )
        if enable:
            command = get_app_command()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass  # 键本来就不存在，无需删除，视为成功
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"设置开机自启动失败: {e}")
        return False


def is_auto_start_enabled() -> bool:
    """
    检查是否已开启开机自启动。
    读取注册表，判断 APP_NAME 键是否存在。
    """
    if platform.system() != "Windows":
        return False

    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTO_START_REG_PATH,
            0,
            winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False

