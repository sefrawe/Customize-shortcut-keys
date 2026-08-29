''' 系统托盘功能 '''
import threading

import pystray
from PIL import Image, ImageOps
from pathlib import Path

from core.configManager import configDirectory
from utils.shortcutUtils import getShortcutSchemes, getStartupEnabledShortcutScheme
# ==================== 34 号新增：状态文案单点真相源 ====================
# 监听/执行状态行文案与设置页共用同一函数，杜绝两处口径漂移（Bug#34 教训）。
from utils.statusText import getListenStatus, getExecStatus
# =====================================================================

# ==============================================================================
# 【系统托盘功能开发核心架构说明】
# ------------------------------------------------------------------------------
# 1. 核心定位：
# 将系统托盘作为软件的“第二控制器”，实现后台静默驻留与无界面快捷操作。
#
# 2. 架构原则：托盘发指令，主窗口干实活
# - pystray (托盘) 运行在独立的后台子线程中。
# - MainWindow 和 Executor (pynput) 运行在主线程中。
# - 【跨线程红线】托盘线程绝对不能直接操作 UI 组件或读写配置文件！
# - 必须通过 main_window.after(0, 回调函数) 将所有修改指令安全地抛回主线程排队执行。
#
# 3. 确定实现的四大核心功能：
# a) 静默启动到托盘：开机自启时带启动参数(如 --minimized)，主窗口 withdraw() 隐藏，不弹窗打扰。
# b) 托盘内退出程序：作为唯一的彻底退出通道，依次执行：executor.stop() -> icon.stop() -> window.destroy()。
# c) 方案热切换：右键菜单动态读取方案列表(带 radio 单选勾)，点击后修改 JSON 配置并调用 executor.sync() 立即生效。
# d) 暂停/恢复监听：右键菜单一键控制 pynput 监听器的挂起与恢复，并根据状态切换托盘图标(如蓝色变灰色)。
# (注：不包含“一键启用/禁用所有快捷键”，该功能因涉及冲突检测，体验上交由主界面处理)
#
# 4. 各文件对接职责：
# - gui/trayIcon.py [新建]：TrayIconManager 类。负责构建动态菜单、图标切换、接收事件并转发 after() 给主窗口。
# - gui/MainWindow.py [改动]：新增 hide_window()、show_window()、toggle_listening_status()、switch_scheme_from_tray()、quit_app()。
# - main.py [改动]：初始化托盘并放入 daemon 线程，解析 sys.argv 判断是否静默启动。
# - core/executor.py [改动]：拆分出独立的 pause_listener() 和 resume_listener() 方法供托盘调用。
#
# 5. ==================== 34 号新增：状态可视化与降级保护 ====================
#    a) 状态行：菜单"显示主窗口"之后插入两行只读项（● 监听 / ● 执行），
#       文案来自 utils/statusText（与设置页单点共用）。托盘菜单是"展开
#       瞬间快照"，与设置页 500ms 轮询的粒度差异是模型差异，接受。
#    b) 即时刷新链：pystray win32 的动态菜单只在 update_menu() 时重建
#       （右键展开用的是缓存句柄——这正是 Bug#34"托盘滞后一拍"的根因）。
#       刷新由 MainWindow 驱动：签名轮询（变化才推）+ 控制方法末尾直推，
#       二者都落到 refresh_visual_state()（图标 + 菜单一次搞定）。
#    c) 暂停变灰：update_icon_state() 幂等切换彩色/灰度图标；灰图启动时
#       一次性预生成（_make_gray_icon，split/merge 保 alpha）。
#    d) 降级保护：_build_dynamic_menu 全量 try/except，构建失败（典型：
#       主线程写 JSON 半截被托盘线程读到）时降级为基础菜单，保托盘不死。
# ==============================================================================
class TrayIconManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.image_normal = self._load_icon()
        # ==================== 34 号新增：灰化副本（启动时一次性生成）===========
        # 实现期设计修正记录：设计阶段预估 ImageEnhance.Color(0.0) 可保 alpha，
        # 实测其内部路径 RGBA→L→RGBA 会把 alpha 置满 255（透明底图标灰化后
        # 变成实心灰方块）。改用 _make_gray_icon 的 split/merge 显式保 alpha。
        # 运行期零计算：灰图只生成这一次，切换仅是引用赋值。
        self.image_gray = self._make_gray_icon(self.image_normal)
        self._last_icon_paused = False  # 幂等基线：初始为彩色
        # ======================================================================
        # 删除了 self.menu = self._build_menu()，不再需要
        self.icon = pystray.Icon(
            "custom_shortcut",
            self.image_normal,
            "自定义快捷键工具",
            menu=pystray.Menu(self._build_dynamic_menu)
        )

    # ==================== 34 号新增：菜单构建降级保护外壳 ======================
    def _build_dynamic_menu(self, icon=None):
        """菜单构建总入口：全量 try/except，失败降级为基础菜单。

        为什么必须包住整个构建过程：_build_full_menu 里会读 JSON 配置文件
        （getStartupEnabledShortcutScheme / getShortcutSchemes），而主线程
        切方案/保存配置时正在写同一批文件——托盘线程（pystray 的菜单重建
        跑在自己线程）读到半截 JSON 会抛 JSONDecodeError，直接炸掉托盘
        菜单。降级菜单只含"显示主窗口 / 退出"两个零文件 IO 的项，保证最坏
        情况下托盘仍可用。签名轮询与点击后的重建都走本入口，一层保护
        覆盖两条路径。
        """
        try:
            return self._build_full_menu(icon)
        except Exception as e:
            print(f"[托盘] 菜单构建失败，降级为基础菜单: {e}")
            return [
                pystray.MenuItem("显示主窗口", self._on_show, default=True),
                pystray.MenuItem("退出程序", self._on_quit),
            ]

    def _build_full_menu(self, icon=None):
        """每次展开菜单时调用，读取最新配置构建菜单（原 _build_dynamic_menu 本体）。"""
        # 1. 获取当前启用的方案
        current_enabled = getStartupEnabledShortcutScheme(configDirectory)
        current_name = current_enabled["name"] if current_enabled else None

        # ==================== 获取忙碌状态（原逻辑原样）====================
        is_busy = getattr(self.main_window.executor, 'is_busy', False) if self.main_window.executor else False

        # ==================== 34 号新增：状态行（只读灰显）=====================
        # 文案来自 statusText 单点真相源（与设置页同一函数）；pystray 的
        # MenuItem 没有颜色概念 → 忽略颜色位只取文案；"●" 前缀标记只读
        # 语义（与可点击项区分）。enabled=False 让系统按禁用态灰显。
        # action 传 None：无回调，纯展示项。
        executor = self.main_window.executor
        listen_status_text, _ = getListenStatus(executor)
        exec_status_text, _ = getExecStatus(executor)
        status_items = [
            pystray.MenuItem(f"● 监听: {listen_status_text}", None, enabled=False),
            pystray.MenuItem(f"● 执行: {exec_status_text}", None, enabled=False),
        ]
        # ======================================================================

        # 2. 构建二级菜单项（方案列表）—— 原逻辑原样
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

        # 3. 获取当前监听状态（按钮行语义：显示的是"点我会发生什么"，
        #    与上面状态行的"现在是什么"刻意分离——Bug#34 的教训：
        #    按钮文案被误读为状态描述是启动时"两处矛盾"观感的来源之一）
        is_paused = getattr(self.main_window, 'is_listening_paused', False)
        listen_button_text = "恢复监听" if is_paused else "暂停监听"

        # 4. 组装并返回主菜单
        #    版式（34 号定稿）：状态行紧跟"显示主窗口"之后，与按钮行之间用
        #    分隔线隔开——状态（现在是什么）与动作（点了会怎样）两类语义
        #    分区呈现。
        return [
            pystray.MenuItem("显示主窗口", self._on_show, default=True),
            pystray.Menu.SEPARATOR,
            *status_items,  # 34 号新增：只读状态行
            pystray.Menu.SEPARATOR,
            # 忙碌时禁用方案切换（原逻辑）
            pystray.MenuItem(
                f"当前启用: {current_name}" if current_name else "启用方案选择 ▶",
                pystray.Menu(*submenu_items),
                enabled=lambda item: not is_busy
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(listen_button_text, self._on_toggle_listening),
            # 强制停止动作组（原逻辑）
            pystray.MenuItem(
                "⏸ 平滑停止动作组",
                self._on_soft_stop_action_group,
                # 只有在忙碌且尚未发送过软停止信号时才显示
                visible=lambda item: is_busy and not getattr(self.main_window.executor, 'action_group_soft_stop_event', threading.Event()).is_set()
            ),
            pystray.MenuItem(
                "⏹ 强制停止动作组",
                self._on_force_stop_action_group,
                visible=lambda item: is_busy
            ),
            pystray.Menu.SEPARATOR,
            # 忙碌时禁用退出（原逻辑）
            pystray.MenuItem("退出程序", self._on_quit, enabled=lambda item: not is_busy)
        ]

    # ==================== 34 号新增：暂停变灰 ==================================
    def _make_gray_icon(self, img):
        """生成保留 alpha 通道的灰度副本（仅启动时调用一次）。

        实现：取出 alpha → 灰度化（亮度只由 RGB 计算，alpha 不参与）→
        与原 alpha 重新合并为 RGBA。
        为什么不用 ImageEnhance.Color(img).enhance(0.0)：
            其内部走 img.convert("L").convert(原模式)——RGBA→L 丢 alpha、
            L→RGBA 时 alpha 被置满 255，透明底图标会变成实心灰方块。
            split/merge 是显式可控的正确做法（实测修正设计预估）。
        """
        img = img.convert("RGBA")            # 统一到 RGBA（_load_icon 的 fallback 是 RGB）
        alpha = img.split()[3]               # 只取 alpha 通道
        gray = ImageOps.grayscale(img)       # L 模式灰度
        return Image.merge("RGBA", (gray, gray, gray, alpha))

    def update_icon_state(self, paused: bool):
        """按暂停状态切换图标颜色（幂等：状态未变直接跳过）。

        幂等的原因：pystray 的 Icon.icon setter 每次赋值都会触发
        _update_icon → win32 后端销毁旧 HICON、NIM_MODIFY 重发新 HICON，
        重复赋同值是无谓开销；调用方（轮询/直推）因此无需先比对。
        口径：只对"暂停"语义变灰；is_busy 不变图，执行态由菜单状态行
        承载（34 号定稿 v2）。
        """
        paused = bool(paused)
        if paused == self._last_icon_paused:
            return
        self._last_icon_paused = paused
        try:
            # pystray 原生支持运行时换图：setter 赋值即触发重绘，无需手动刷新
            self.icon.icon = self.image_gray if paused else self.image_normal
        except Exception as e:
            print(f"[托盘] 图标切换失败: {e}")

    def refresh_visual_state(self):
        """主线程标志变化后的即时刷新入口：图标 + 菜单一次搞定。

        调用方：MainWindow._pushTrayUpdate()（签名轮询变化时 + toggle/switch
        直推时）。项目纪律统一"托盘操作收口主线程"，本方法只在主线程被调。
        update_menu 边界（记档）：若恰逢用户菜单展开中（模态
        TrackPopupMenuEx 中销毁重建 HMENU）理论可能毛刺——概率极低，
        try/except 包住，出问题也只是当次展开异常。
        """
        paused = bool(getattr(self.main_window, 'is_listening_paused', False))
        self.update_icon_state(paused)
        try:
            self.icon.update_menu()
        except Exception as e:
            print(f"[托盘] update_menu 失败: {e}")
    # ==========================================================================

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
