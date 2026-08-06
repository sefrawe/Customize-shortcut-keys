'''
系统托盘
'''
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
''' 系统托盘功能 '''
import pystray
from PIL import Image, ImageDraw


class TrayIconManager:
    def __init__(self, main_window):
        self.main_window = main_window

        # 生成占位图标 (后续可替换为真实 .ico)
        self.image_normal = self._create_placeholder_image((73, 109, 137))

        # 构建初始右键菜单
        self.menu = self._build_menu()

        # 创建托盘图标实例
        self.icon = pystray.Icon(
            "custom_shortcut",
            self.image_normal,
            "自定义快捷键工具",
            self.menu
        )

    def _create_placeholder_image(self, color):
        """生成一个简单的纯色方块作为临时图标"""
        image = Image.new('RGB', (64, 64), color=color)
        return image

    def _build_menu(self):
        """构建右键菜单 (后续会改为动态生成)"""
        return pystray.Menu(
            pystray.MenuItem("显示主窗口", self._on_show, default=True),
            pystray.MenuItem("退出程序", self._on_quit)
        )

    # --- 跨线程通信桥梁：只发指令，不直接操作 ---

    def _on_show(self, icon=None, item=None):
        """点击'显示主窗口'或双击图标时的回调"""
        # 必须用 after 抛给主线程执行
        self.main_window.after(0, self.main_window.show_window)

    def _on_quit(self, icon=None, item=None):
        """点击'退出程序'时的回调"""
        # 通知主线程执行彻底退出
        self.main_window.after(0, self.main_window.quit_app)
        # 停止托盘自身运行
        self.icon.stop()

    def run(self):
        """在后台线程中运行托盘图标"""
        self.icon.run()
