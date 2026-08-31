''' 运行时窗口标题栏与任务栏图标工具函数 '''
import sys
from pathlib import Path

_ICON_PATH = Path(__file__).resolve().parent.parent / "icon.ico"


def applyAppIcon(window):
    """给任意 CTk/CTkToplevel 窗口设置应用图标（幂等，可重复调用）。

    注意：CTkToplevel 会在创建后约 200ms 把图标重设回 CTk 默认图标
    （CustomTkinter issue #2302 / #2663），所以在 __init__ 里同步调用
    会被覆盖。这里安排一个 250ms 的延迟重设，确保落在它之后。
    """
    if sys.platform.startswith("win") and _ICON_PATH.exists():
        def _set():
            try:
                window.iconbitmap(str(_ICON_PATH))
            except Exception:
                pass  # 窗口可能已销毁等竞态，静默跳过

        _set()                    # 立即设一次（主窗口 CTk 直接生效）
        window.after(250, _set)   # 晚于 CTkToplevel 的 200ms 默认图标回调，再设一次
