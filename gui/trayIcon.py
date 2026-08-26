''' 系统托盘功能 '''
import threading

import pystray
from PIL import Image
from pathlib import Path
from core.configManager import configDirectory
from utils.shortcutUtils import getShortcutSchemes, getStartupEnabledShortcutScheme
# ==============================================================================
# 【系统托盘功能开发核心架构说明】
# ------------------------------------------------------------------------------
# 1. 核心定位：
#    将系统托盘作为软件的“第二控制器”，实现后台静默驻留与无界面快捷操作。
#
# 2. 架构原则：托盘发指令，主窗口干实活
#    - pystray (托盘) 运行在独立的后台子线程中。
#    - MainWindow 和 Executor (pynput) 运行在主线程中。
#    - 【跨线程红线】托盘线程绝对不能直接操作 UI 组件或读写配置文件！
#    - 必须通过 main_window.after(0, 回调函数) 将所有修改指令安全地抛回主线程排队执行。
#
# 3. 确定实现的四大核心功能：
#    a) 静默启动到托盘：开机自启时带启动参数(如 --minimized)，主窗口 withdraw() 隐藏，不弹窗打扰。
#    b) 托盘内退出程序：作为唯一的彻底退出通道，依次执行：executor.stop() -> icon.stop() -> window.destroy()。
#    c) 方案热切换：右键菜单动态读取方案列表(带 radio 单选勾)，点击后修改 JSON 配置并调用 executor.sync() 立即生效。
#    d) 暂停/恢复监听：右键菜单一键控制 pynput 监听器的挂起与恢复，并根据状态切换托盘图标(如蓝色变灰色)。
#    (注：不包含“一键启用/禁用所有快捷键”，该功能因涉及冲突检测，体验上交由主界面处理)
#
# 4. 各文件对接职责：
#    - gui/trayIcon.py [新建]：TrayIconManager 类。负责构建动态菜单、图标切换、接收事件并转发 after() 给主窗口。
#    - gui/MainWindow.py [改动]：新增 hide_window()、show_window()、toggle_listening_status()、switch_scheme_from_tray()、quit_app()。
#    - main.py [改动]：初始化托盘并放入 daemon 线程，解析 sys.argv 判断是否静默启动。
#    - core/executor.py [改动]：拆分出独立的 pause_listener() 和 resume_listener() 方法供托盘调用。
# ==============================================================================


class TrayIconManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.image_normal = self._load_icon()
        # 删除了 self.menu = self._build_menu()，不再需要

        self.icon = pystray.Icon(
            "custom_shortcut",
            self.image_normal,
            "自定义快捷键工具",
            menu=pystray.Menu(self._build_dynamic_menu)
        )

    def _build_dynamic_menu(self, icon=None):
        """每次展开菜单时调用，读取最新配置构建菜单"""
        # 1. 获取当前启用的方案
        current_enabled = getStartupEnabledShortcutScheme(configDirectory)
        current_name = current_enabled["name"] if current_enabled else None

        # ==================== 新增：获取忙碌状态 ====================
        is_busy = getattr(self.main_window.executor, 'is_busy', False) if self.main_window.executor else False
        # ==========================================================

        # 2. 构建二级菜单项（方案列表）
        submenu_items = []
        submenu_items.append(
            pystray.MenuItem(
                "（无）",
                self._on_switch,
                radio=True,
                checked=lambda item: current_name is None
            )
        )
        for scheme in getShortcutSchemes(configDirectory):
            name = scheme["name"]
            submenu_items.append(
                pystray.MenuItem(
                    name,
                    self._on_switch,
                    radio=True,
                    checked=lambda item, n=name: n == current_name
                )
            )

        # 3. 获取当前监听状态
        is_paused = getattr(self.main_window, 'is_listening_paused', False)
        listen_text = "恢复监听" if is_paused else "暂停监听"

        # 4. 组装并返回主菜单
        return [
            pystray.MenuItem("显示主窗口", self._on_show, default=True),
            pystray.Menu.SEPARATOR,
            # ==================== 新增：忙碌时禁用方案切换 ====================
            pystray.MenuItem(
                f"当前启用: {current_name}" if current_name else "启用方案选择 ▶",
                pystray.Menu(*submenu_items),
                enabled=lambda item: not is_busy
            ),
            # ==============================================================
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(listen_text, self._on_toggle_listening),
            # ==================== 新增：强制停止动作组 ====================
            pystray.MenuItem(
                "⏸ 平滑停止动作组",
                self._on_soft_stop_action_group,
                # 只有在忙碌且尚未发送过软停止信号时才显示
                visible=lambda item: is_busy and not getattr(self.main_window.executor, 'action_group_soft_stop_event',
                                                             threading.Event()).is_set()
            ),
            pystray.MenuItem(
                "⏹ 强制停止动作组",
                self._on_force_stop_action_group,
                visible=lambda item: is_busy
            ),
            # ==============================================================
            # ==================== 新增：忙碌时禁用退出 ====================
            pystray.MenuItem("退出程序", self._on_quit, enabled=lambda item: not is_busy)
            # ==============================================================
        ]

    def _on_force_stop_action_group(self, icon=None, item=None):
        """点击强制停止动作组时的回调"""
        self.main_window.after(0, self.main_window.force_stop_action_group)

    def _on_toggle_listening(self, icon=None, item=None):
        """点击暂停/恢复监听时的回调"""
        self.main_window.after(0, self.main_window.toggle_listening_status)

    def _on_switch(self, icon=None, item=None):
        """点击二级菜单项时的回调，将指令抛给主线程"""
        target_name = item.text
        if target_name == "（无）":
            target_name = None
        self.main_window.after(
            0,
            lambda: self.main_window.switch_scheme_from_tray(target_name)
        )

    def _load_icon(self):
        """加载图标"""
        icon_path = Path(__file__).parent.parent / "icon.png"
        if icon_path.exists():
            return Image.open(icon_path)
        else:
            return Image.new('RGB', (64, 64), color=(73, 109, 137))

    # --- 跨线程通信桥梁 ---
    def _on_show(self, icon=None, item=None):
        self.main_window.after(0, self.main_window.show_window)

    def _on_quit(self, icon=None, item=None):
        self.main_window.after(0, self.main_window.quit_app)
        self.icon.stop()

    def run(self):
        self.icon.run()

    def _on_soft_stop_action_group(self, icon=None, item=None):
        """点击平滑停止动作组时的回调"""
        self.main_window.after(0, self.main_window.soft_stop_action_group)

