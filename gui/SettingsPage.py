""" 设置页面 """
from utils.interpreterRegistry import INTERPRETER_REGISTRY
from utils.systemUtils import set_auto_start, is_auto_start_enabled

# 顶部 import re 一行【删除】——re 只被旧版 saveCustomBlacklist 使用，
# 解析已下沉 configManager，留着是死导入（改动 2.6 后无任何使用点）。
from tkinter import messagebox
import customtkinter as ctk
from core.configManager import (
    loadThemeFromConfig,
    saveThemeToConfig,
    loadUserBlacklist,
    saveUserBlacklist,
    parseBlacklistText,      # 15 号新增：黑名单文本解析器（唯一真相源）
    formatBlacklistDict,     # 15 号新增：黑名单字典序列化器（回显共用）
    loadWindowSettings,
    saveWindowSettings,
)


# "监听/执行"状态文案的计算分支收敛到 utils/statusText，与托盘状态行
# 共用同一函数——本文件不再自持分支，任何口径调整只改 statusText 一处
# （Bug#34 的教训：两处各写一套必然漂移）。
from utils.statusText import getListenStatus, getExecStatus

# 35 号修订：停止按钮的组合串改为消费 reservedCombos 真相源——
# 修订前本文件两处按钮硬编码 "ctrl_r+alt_r+esc" 字面串，是全项目
# 仅存的组合串副本（换键时若忘改必与监听端漂移），本轮一并清偿。
from utils.reservedCombos import kindToComboStr, STOP_KIND_HARD, STOP_KIND_SOFT

# ==================== 15 号：状态行自动清除时长（两档，定稿拍板）========
_STATUS_CLEAR_QUICK_MS = 3000   # 净成功：无丢弃、无警告、保存无异常
_STATUS_CLEAR_LONG_MS = 10000   # 其余：确认跳过 / 有警告 / 保存失败

class SettingsPage(ctk.CTkFrame):

    def __init__(self, master, main_window=None, **kwargs):
        super().__init__(master, **kwargs)
        # ==================== 32 号新增：主窗口引用注入 ====================
        # MainWindow 创建本页时传入自身，供"软件控制与状态"区调用其控制方法
        # （暂停/恢复监听、强制/平滑停止、退出）并读取监听暂停标志。
        # 默认 None 保持向后兼容：未传引用的调用点页面照常渲染，控制区降级
        # 为只读提示（见 _refreshControlStatus 的降级分支）。
        self.main_window = main_window
        # 轮询定时器 ID 占位（destroy 时取消）
        self._poll_after_id = None
        # ================================================================

        # 15 号：两个状态行的自动清除定时器 ID 占位（destroy 时取消）。
        # 两个定时器完全独立：黑名单保存不动 winSize 提示，反之亦然。
        self._blacklistClearAfterId = None
        self._winSizeClearAfterId = None


        # ── 页面整体布局：单个滚动容器撑满 ──
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scrollFrame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollFrame.grid(row=0, column=0, sticky="nsew")

        # ==================== 32 号新增：软件控制与状态区 ====================
        # 设计定稿第三节：设置页最顶部（点进设置第一眼即达）。
        # 定位：观察窗口 + 鼠标可用时的备用控制通道 —— 主通道是键盘停止组合，
        # 备用通道是托盘；鼠标被动作组劫持时本区同样点不到，这是模型边界。
        ctk.CTkLabel(self.scrollFrame, text="软件控制与状态", font=("微软雅黑", 24)).pack(pady=(20, 10))

        controlCard = ctk.CTkFrame(self.scrollFrame, corner_radius=10)
        controlCard.pack(pady=(0, 10), padx=20, fill="x")

        # --- 状态行 1：监听状态（只读）---
        listenRow = ctk.CTkFrame(controlCard, fg_color="transparent")
        listenRow.pack(fill="x", padx=10, pady=(10, 2))
        ctk.CTkLabel(listenRow, text="监听状态:", font=("微软雅黑", 14)).pack(side="left")
        self.listenStateLabel = ctk.CTkLabel(listenRow, text="读取中...", font=("微软雅黑", 14, "bold"))
        self.listenStateLabel.pack(side="left", padx=8)

        # --- 状态行 2：执行状态（只读）---
        execRow = ctk.CTkFrame(controlCard, fg_color="transparent")
        execRow.pack(fill="x", padx=10, pady=(2, 8))
        ctk.CTkLabel(execRow, text="执行状态:", font=("微软雅黑", 14)).pack(side="left")
        self.execStateLabel = ctk.CTkLabel(execRow, text="读取中...", font=("微软雅黑", 14, "bold"))
        self.execStateLabel.pack(side="left", padx=8)

        # --- 按钮行 ---
        # 忙碌置灰口径（设计定稿第三节）：暂停/恢复监听、退出软件 → 动作组
        # 执行中禁用；两个停止按钮 → 常启用（空闲时点击得到"没有正在执行的
        # 动作组"提示，与托盘同口径）。轮询置灰存在 ≤500ms 窗口，方法层守卫
        # （MainWindow 三个方法）兜底，双保险。
        btnRow = ctk.CTkFrame(controlCard, fg_color="transparent")
        btnRow.pack(fill="x", padx=10, pady=(0, 10))
        self.toggleListenBtn = ctk.CTkButton(btnRow, text="暂停监听", width=110,
                                             font=("微软雅黑", 13), command=self._onToggleListen)
        self.toggleListenBtn.pack(side="left", padx=5)
        # 35 号修订：组合串消费 kindToComboStr（唯一真相源），不再硬编码；
        # width 110 → 150：caps_lock 比 esc 长 6 字符，110 定宽必然截字，
        # 原 esc 文案本就偏挤，顺手放行。
        self.forceStopBtn = ctk.CTkButton(
            btnRow,
            text=f"⏹ 强制停止（{kindToComboStr(STOP_KIND_HARD)}）",
            width=150,
            font=("微软雅黑", 13),
            fg_color="#A30000", hover_color="#7A0000",
            command=self._onForceStop,
        )
        self.forceStopBtn.pack(side="left", padx=5)
        self.softStopBtn = ctk.CTkButton(
            btnRow,
            text=f"⏸ 平滑停止（{kindToComboStr(STOP_KIND_SOFT)}）",
            width=150,
            font=("微软雅黑", 13),
            command=self._onSoftStop,
        )
        self.softStopBtn.pack(side="left", padx=5)

        self.quitBtn = ctk.CTkButton(btnRow, text="退出软件", width=110,
                                     font=("微软雅黑", 13), fg_color="#A30000",
                                     hover_color="#7A0000", command=self._onQuit)
        self.quitBtn.pack(side="left", padx=5)
        # ==================================================================


        # ==================== 主题设置 ====================
        self.themeLabel = ctk.CTkLabel(self.scrollFrame, text="主题设置", font=("微软雅黑", 24))
        self.themeLabel.pack(pady=20)

        self.themeSeg = ctk.CTkSegmentedButton(
            self.scrollFrame,
            values=["亮", "暗", "跟随系统"],
            command=self.changeTheme,
            font=("微软雅黑", 16),
        )
        current_theme = loadThemeFromConfig()
        self.themeSeg.set(current_theme)
        self.themeSeg.pack(pady=10, padx=20, fill="x")
        self.changeTheme(current_theme)

        # ==================== 通用设置 ====================
        self.generalLabel = ctk.CTkLabel(self.scrollFrame, text="通用设置", font=("微软雅黑", 24))
        self.generalLabel.pack(pady=(40, 10))

        # --- 开机自启动 ---
        autoStartFrame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
        autoStartFrame.pack(pady=10, padx=20, fill="x")

        autoStartLabel = ctk.CTkLabel(
            autoStartFrame,
            text="开机自启动（静默启动到系统托盘）",
            font=("微软雅黑", 16),
            anchor="w",
        )
        autoStartLabel.pack(side="left", padx=(0, 10))

        self.autoStartSwitch = ctk.CTkSwitch(
            autoStartFrame, text="", command=self.toggleAutoStart, width=60
        )
        self.autoStartSwitch.pack(side="right")
        if is_auto_start_enabled():
            self.autoStartSwitch.select()

        # ==================== 窗口大小设置 ====================
        self.windowSizeLabel = ctk.CTkLabel(
            self.scrollFrame, text="窗口大小设置", font=("微软雅黑", 24)
        )
        self.windowSizeLabel.pack(pady=(40, 5))

        # 增加全局提示：未勾选最大化时生效，修改后需保存
        ctk.CTkLabel(
            self.scrollFrame,
            text="* 宽高设置仅在未勾选“启动时最大化”时生效。修改后请点击下方保存按钮。",
            font=("微软雅黑", 12),
            text_color="#FFA500",
            anchor="w"
        ).pack(pady=(0, 10), padx=20, fill="x")

        # 加载当前已有的窗口配置
        current_win_settings = loadWindowSettings()
        self._win_ui_vars = {}  # 用于存储每个窗口对应的UI控件引用，方便保存时读取

        # --- 循环创建三个窗口的配置UI ---
        # config_key: 配置文件里的键名, title: 界面显示的名称, min_w/min_h: 允许的最小宽高
        win_configs = [
            {"key": "mainWindow", "title": "主窗口", "min_w": 1000, "min_h": 800},
            {"key": "editWindow", "title": "编辑窗口", "min_w": 600, "min_h": 400},
            {"key": "searchWindow", "title": "搜索窗口", "min_w": 400, "min_h": 400},
            {"key": "actionGroupWindow", "title": "动作组编辑窗口", "min_w": 700, "min_h": 600},
        ]

        for cfg in win_configs:
            win_key = cfg["key"]
            win_data = current_win_settings.get(win_key, {})

            # 单个窗口的容器
            win_frame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
            win_frame.pack(pady=10, padx=20, fill="x")

            # 标题与最大化勾选框
            header_frame = ctk.CTkFrame(win_frame, fg_color="transparent")
            header_frame.pack(fill="x")
            ctk.CTkLabel(header_frame, text=cfg["title"], font=("微软雅黑", 16, "bold")).pack(side="left", padx=(0, 10))

            # 最大化勾选框
            max_switch = ctk.CTkCheckBox(
                header_frame, text="启动时最大化", font=("微软雅黑", 14)
            )
            if win_data.get("maximized", False):
                max_switch.select()
            max_switch.pack(side="left")

            # 宽高输入区
            size_frame = ctk.CTkFrame(win_frame, fg_color="transparent")
            size_frame.pack(fill="x", pady=(5, 0))

            # 宽度 (对应 X 轴)
            ctk.CTkLabel(size_frame, text="宽度:", font=("微软雅黑", 14)).pack(side="left", padx=(0, 5))
            w_entry = ctk.CTkEntry(size_frame, width=70, font=("微软雅黑", 14))
            w_entry.insert(0, str(win_data.get("width", 1000)))
            w_entry.pack(side="left", padx=(0, 5))
            ctk.CTkLabel(size_frame, text=f"(X轴, 最小{cfg['min_w']}像素)", font=("微软雅黑", 12),
                         text_color="gray").pack(side="left", padx=(0, 20))

            # 高度 (对应 Y 轴)
            ctk.CTkLabel(size_frame, text="高度:", font=("微软雅黑", 14)).pack(side="left", padx=(0, 5))
            h_entry = ctk.CTkEntry(size_frame, width=70, font=("微软雅黑", 14))
            h_entry.insert(0, str(win_data.get("height", 800)))
            h_entry.pack(side="left", padx=(0, 5))
            ctk.CTkLabel(size_frame, text=f"(Y轴, 最小{cfg['min_h']}像素)", font=("微软雅黑", 12),
                         text_color="gray").pack(side="left")

            # 保存时需要用到的提示标签 (仅主窗口有)
            if win_key == "mainWindow":
                ctk.CTkLabel(
                    win_frame, text="* 主窗口大小修改需重启软件生效",
                    font=("微软雅黑", 12), text_color="#FF6B6B"
                ).pack(anchor="w", pady=(2, 0))

            # 把控件存起来，保存时用
            self._win_ui_vars[win_key] = {
                "max_switch": max_switch,
                "w_entry": w_entry,
                "h_entry": h_entry,
                "min_w": cfg["min_w"],
                "min_h": cfg["min_h"]
            }

        # 保存窗口设置按钮
        self.saveWinSizeBtn = ctk.CTkButton(
            self.scrollFrame, text="保存窗口设置", command=self.saveWindowSettings, font=("微软雅黑", 14)
        )
        self.saveWinSizeBtn.pack(pady=(0, 20), padx=20, anchor="e")

        # 窗口大小保存状态提示
        self.winSizeSaveStatus = ctk.CTkLabel(
            self.scrollFrame, text="", font=("微软雅黑", 12), text_color="green", anchor="w"
        )
        self.winSizeSaveStatus.pack(pady=(0, 2), padx=20, fill="x")

        # ==================== 黑名单管理 ====================
        self.blacklistLabel = ctk.CTkLabel(
            self.scrollFrame, text="黑名单管理", font=("微软雅黑", 24)
        )
        self.blacklistLabel.pack(pady=(40, 10))

        # ── 第一层：强制黑名单（只读展示） ──
        forcedLabel = ctk.CTkLabel(
            self.scrollFrame,
            text="⛔ 强制黑名单（系统内置，不可修改，命中直接拒绝执行）",
            font=("微软雅黑", 14, "bold"),
            text_color="#FF6B6B",
            anchor="w",
        )
        forcedLabel.pack(pady=(10, 5), padx=20, fill="x")

        self.forcedBlacklistTextbox = ctk.CTkTextbox(
            self.scrollFrame,
            font=("微软雅黑", 13),
            height=120,
            corner_radius=5,
            state="disabled",
        )
        self.forcedBlacklistTextbox.pack(pady=(0, 10), padx=20, fill="x")
        self._populateForcedBlacklist()

        # ── 第二层：用户自定义黑名单（可编辑） ──
        customLabel = ctk.CTkLabel(
            self.scrollFrame,
            text="⚠️ 自定义黑名单（命中后弹窗确认后再执行）",
            font=("微软雅黑", 14, "bold"),
            text_color="#FFA500",
            anchor="w",
        )
        customLabel.pack(pady=(10, 5), padx=20, fill="x")

        # ★ 格式说明区域（保持不变） ★
        formatLabel = ctk.CTkLabel(
            self.scrollFrame,
            text="📝 格式说明：",
            font=("微软雅黑", 13, "bold"),
            text_color="#4ECDC4",
            anchor="w",
        )
        formatLabel.pack(pady=(5, 2), padx=20, fill="x")

        formatContent = ctk.CTkLabel(
            self.scrollFrame,
            text=(
                "• 每行格式：[解释器名] 关键词1, 关键词2\n"
                "• 例如：[cmd] format, diskpart\n"
                "• 解释器名与关键词都不区分大小写（[CMD] 等价 [cmd]）\n"
                "• 子串包含匹配（如输入 'ping' 会匹配 'ping 127.0.0.1'）\n"
                "• 自动去除每行首尾空格；空行与 # 开头的行视为注释\n"
                "• 无法解析的行保存时会提示确认后丢弃；重复关键词自动去重\n"
                "• 修改后需点击「保存自定义黑名单」按钮生效；保存的提示几秒后自动消失"
            ),
            font=("微软雅黑", 12),
            text_color="gray",
            anchor="w",
            justify="left",
        )
        formatContent.pack(pady=(0, 5), padx=20, fill="x")

        self.customBlacklistTextbox = ctk.CTkTextbox(
            self.scrollFrame,
            font=("微软雅黑", 13),
            height=100,
            corner_radius=5,
        )
        self.customBlacklistTextbox.pack(pady=(0, 5), padx=20, fill="x")

        self.blacklistSaveStatus = ctk.CTkLabel(
            self.scrollFrame,
            text="",
            font=("微软雅黑", 12),
            text_color="green",
            anchor="w",
        )
        self.blacklistSaveStatus.pack(pady=(0, 2), padx=20, fill="x")

        self.saveBlacklistBtn = ctk.CTkButton(
            self.scrollFrame,
            text="保存自定义黑名单",
            command=self.saveCustomBlacklist,
            font=("微软雅黑", 14),
        )
        self.saveBlacklistBtn.pack(pady=(0, 20), padx=20, anchor="e")

        # 加载已保存的用户黑名单数据到文本框
        self._loadCustomBlacklist()

        # ==================== 32 号新增：启动状态轮询 ====================
        # 每 500ms 轮询（设计定稿：500ms~1s）。轮询而非事件推送：监听暂停
        # 标志/执行状态在托盘、GUI、动作组三个入口都可能变化，轮询天然
        # 覆盖全部通道（如托盘暂停后本区文案自动跟随）。
        self._startControlPolling()

    # ==================== 32 号新增：软件控制与状态区方法 ====================

    def _startControlPolling(self):
        """启动控制区状态轮询。"""
        self._poll_after_id = self.after(500, self._pollControlStatus)

    def _pollControlStatus(self):
        """轮询回调：刷新状态，再排下一拍。窗口销毁后防御性退出。"""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        # 页面被 grid_forget（未显示）时跳过刷新工作，只续下一拍 ——
        # 页面对象常驻内存，不显示时没必要每 500ms 空刷控件
        if self.winfo_ismapped():
            self._refreshControlStatus()
        self._poll_after_id = self.after(500, self._pollControlStatus)

    def _getExecutor(self):
        """取主窗口持有的执行器（未注入主窗口引用时返回 None）。"""
        if self.main_window is None:
            return None
        return getattr(self.main_window, "executor", None)

    def _refreshControlStatus(self):
        """根据 executor / 主窗口标志刷新状态标签与按钮可用性。"""
        mw = self.main_window
        executor = self._getExecutor()

        # ── 降级分支：未注入主窗口引用（旧调用点 / 测试环境）──
        if mw is None:
            self.listenStateLabel.configure(text="（未注入主窗口引用）", text_color="gray")
            self.execStateLabel.configure(text="未知", text_color="gray")
            for btn in (self.toggleListenBtn, self.forceStopBtn, self.softStopBtn, self.quitBtn):
                btn.configure(state="disabled")
            return

        # ── 状态标签：34 号起文案计算收敛到 utils/statusText 单点真相源 ──────
        # 本方法不再自持"已暂停/监听中/未启动"分支——分支逻辑与托盘状态行
        # 共用同一函数（判定优先级、措辞、颜色全部单点）。paused 一并从
        # executor.isPaused 读（与 mw.is_listening_paused property 同一真相源）。
        listen_text, listen_color = getListenStatus(executor)
        exec_text, exec_color = getExecStatus(executor)
        self.listenStateLabel.configure(text=listen_text, text_color=listen_color)
        self.execStateLabel.configure(text=exec_text, text_color=exec_color)

        # ── 按钮可用性（口径见按钮行注释，原样保留）──
        # 忙碌置灰口径（设计定稿第三节）：暂停/恢复监听、退出软件 → 动作组
        # 执行中禁用；两个停止按钮 → 常启用。轮询置灰存在 ≤500ms 窗口，
        # 方法层守卫（MainWindow 三个方法）兜底，双保险。
        paused = bool(getattr(executor, 'isPaused', False))
        busy = bool(executor is not None and executor.is_busy)
        self.toggleListenBtn.configure(
            text="恢复监听" if paused else "暂停监听",
            state="disabled" if busy else "normal",
        )
        self.quitBtn.configure(state="disabled" if busy else "normal")
        # 两个停止按钮常启用，不做 configure

    def _onToggleListen(self):
        """暂停/恢复监听 → 主窗口方法（方法层自带忙碌守卫，双保险）。"""
        if self.main_window is None:
            return
        self.main_window.toggle_listening_status()
        self._refreshControlStatus()  # 立即刷新一次，不等下一拍

    def _onForceStop(self):
        if self.main_window is None:
            return
        self.main_window.force_stop_action_group()

    def _onSoftStop(self):
        if self.main_window is None:
            return
        self.main_window.soft_stop_action_group()  # 重复发送提示已内置

    def _onQuit(self):
        if self.main_window is None:
            return
        self.main_window.quit_app()  # 忙碌守卫在 quit_app 内

    def destroy(self):
        """页面销毁时取消状态轮询（32 号纪律）+ 15 号新增的两个状态行
        清除定时器。不取消的话：最后一次排期的 after 回调会在控件销毁
        后触发，winfo_exists 守卫虽能防御，但显式取消更干净（不依赖
        防御）——三个槽位统一走同一段取消逻辑。"""
        for attr in ("_poll_after_id", "_blacklistClearAfterId", "_winSizeClearAfterId"):
            after_id = getattr(self, attr, None)
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)
        super().destroy()

    # =======================================================================


    def _populateForcedBlacklist(self):
        """
        从 interpreterRegistry 中读取所有解释器的 danger_keywords，
        格式化后填充到只读文本框中展示给用户。

        输出格式示例：
            [cmd] format, diskpart
            [powershell] Format-Volume, Remove-Item
            [python] os.system, shutil.rmtree
        """
        lines = []
        for spec in INTERPRETER_REGISTRY:
            if spec.danger_keywords:
                # 将关键词列表用逗号连接，前面加上解释器名称
                keywords_str = ", ".join(spec.danger_keywords)
                lines.append(f"[{spec.name}] {keywords_str}")
        text = "\n".join(lines) if lines else "（当前无内置黑名单）"

        # 解锁 → 写入 → 重新锁定
        self.forcedBlacklistTextbox.configure(state="normal")
        self.forcedBlacklistTextbox.delete("1.0", "end")
        self.forcedBlacklistTextbox.insert("1.0", text)
        self.forcedBlacklistTextbox.configure(state="disabled")

    # ==================== 15 号新增：状态行统一清除机制 ====================

    def _showStatusAndScheduleClear(self, label, attr_name: str,
                                    text: str, color: str, duration_ms: int):
        """
        统一的状态行显示 + 定时清除（黑名单 / winSize 两个标签共用）。

        纪律一（先 cancel 后排新）：连续两次保存时，若不取消第一次的
        定时器，它会把第二次的提示提前清掉——提示刚显示即消失（验收
        项 A5）。cancel 对已触发/不存在的 ID 是安全的（Tcl after cancel
        对未知 ID 静默忽略），外层 try 兜底属项目惯例防御。

        纪律二（独立定时器）：attr_name 区分两个标签各自的定时器槽位，
        黑名单与 winSize 互不干扰（验收项 A6）。
        """
        label.configure(text=text, text_color=color)

        old_id = getattr(self, attr_name, None)
        if old_id is not None:
            try:
                self.after_cancel(old_id)
            except Exception:
                pass

        def _clear():
            # winfo_exists 守卫 + try 兜底（照 _updateStepSummary 先例）：
            # 页面销毁竞态下静默退出。本页面常驻（MainWindow 创建一次、
            # showPage 仅 grid_forget），唯一销毁路径是 quit_app 级联，
            # 且 destroy 里会 after_cancel——这里守卫只是最后一道防线。
            try:
                if label.winfo_exists():
                    label.configure(text="")
            except Exception:
                pass
            # 定时器已执行完毕，清空槽位表示"当前无挂起任务"
            setattr(self, attr_name, None)

        new_id = self.after(duration_ms, _clear)
        setattr(self, attr_name, new_id)

    def _formatDropsPreview(self, drops) -> str:
        """
        丢弃级问题列表 → 确认弹窗正文。
        原文截断约 40 字符；超过 8 条只列前 8 条 + 汇总行（定稿拍板）。
        截断导致的"看不全"是已接受边界：行号已给出，用户可回文本框
        对照，不值得做滚动详情窗（定稿"不做清单"第 7 条）。
        """
        lines = []
        for lineno, reason, raw in drops[:8]:
            preview = raw if len(raw) <= 40 else raw[:40] + "…"
            lines.append(f"第 {lineno} 行（{reason}）：{preview}")
        if len(drops) > 8:
            lines.append(f"……等共 {len(drops)} 行")
        return "\n".join(lines)

    # ======================================================================

    def _loadCustomBlacklist(self):
        """从 Global Settings.json 读取用户自定义黑名单并回显到文本框。

        15 号改造：回显文本改由 formatBlacklistDict 统一生成（旧版是
        本文件内联的又一份序列化副本）。回显的就是实际存储格式，
        归一化成果（解释器名 lower、去重）会自然"回写"到用户视野
        （验收项 B14：保存后重开设置页看到规范化写法）。
        """
        blacklist_dict = loadUserBlacklist()
        text = formatBlacklistDict(blacklist_dict)
        self.customBlacklistTextbox.delete("1.0", "end")
        self.customBlacklistTextbox.insert("1.0", text)

    def saveCustomBlacklist(self):
        """保存按钮的回调（15 号重写：语法检查 + 统一清除机制）。

        流程（定稿第四节）：
        1. 空文本框 → 显式清空配置（文案明确"已清空"）；
        2. parseBlacklistText 一次性收集全部问题（单点解析器）；
        3. 丢弃级 → askyesno 确认（keyValidator 逃生口同款交互，
           方向相反：那里默认拒、这里默认保）；
        4. 警告级 → 不拦，状态行提示首条 + "另有 K 条"；
        5. 状态行时长按"净成功 3s / 其余 10s"两档（定稿拍板）。
        """
        raw_text = self.customBlacklistTextbox.get("1.0", "end-1c")

        # ── 空文本框：显式清空 ──
        # 走到这说明用户删光了全部内容，意图就是清空。不弹确认
        # （清空自定义黑名单无破坏性——强制黑名单仍在兜底），文案
        # 明确告知即可（验收项 A9）。
        if not raw_text.strip():
            try:
                saveUserBlacklist({})
            except Exception as e:
                self._showStatusAndScheduleClear(
                    self.blacklistSaveStatus, "_blacklistClearAfterId",
                    f"❌ 保存失败: {e}", "red", _STATUS_CLEAR_LONG_MS)
                return
            self._showStatusAndScheduleClear(
                self.blacklistSaveStatus, "_blacklistClearAfterId",
                "✅ 已保存（自定义黑名单已清空）", "green",
                _STATUS_CLEAR_QUICK_MS)
            return

        # ── 解析 + 问题收集（单点解析器，一次收集全部问题）──
        blacklist_dict, drops, warns = parseBlacklistText(raw_text)

        # ── 丢弃级：askyesno 确认（逃生口）──
        if drops:
            if not blacklist_dict:
                # 特判（定稿第四节）：所有行都被丢弃 → 保存将清空现有
                # 配置，文案必须点破，防用户改坏文本误清已有保护。
                confirm_msg = (
                        "所有行都无法解析，继续保存将使自定义黑名单清空"
                        "（现有配置会被清除）。\n\n"
                        + self._formatDropsPreview(drops)
                        + "\n\n确定要保存吗？"
                )
            else:
                confirm_msg = (
                        f"以下 {len(drops)} 行无法解析，保存时将被丢弃：\n\n"
                        + self._formatDropsPreview(drops)
                        + "\n\n其余行照常保存。是否继续？"
                )
            if not messagebox.askyesno("黑名单格式问题", confirm_msg):
                self._showStatusAndScheduleClear(
                    self.blacklistSaveStatus, "_blacklistClearAfterId",
                    "已取消，未保存", "gray", _STATUS_CLEAR_QUICK_MS)
                return

        # ── 写入 ──
        try:
            saveUserBlacklist(blacklist_dict)
        except Exception as e:
            self._showStatusAndScheduleClear(
                self.blacklistSaveStatus, "_blacklistClearAfterId",
                f"❌ 保存失败: {e}", "red", _STATUS_CLEAR_LONG_MS)
            return

        # ── 状态行拼装（定稿第五节模板，按序用"；"连接）──
        parts = []
        if blacklist_dict:
            parts.append(f"✅ 已保存 {len(blacklist_dict)} 个解释器")
            if drops:
                parts.append(f"已跳过 {len(drops)} 行")
        else:
            # 空字典 = 清空（用户显式清空 / 全部行被丢弃后确认 /
            # 只写了注释行——三种路径文案统一）
            parts.append("✅ 已保存（自定义黑名单已清空）")
            if drops:
                parts.append(f"已跳过 {len(drops)} 行")
        if warns:
            head = warns[0]
            extra = f"（另有 {len(warns) - 1} 条警告）" if len(warns) > 1 else ""
            parts.append(f"⚠ {head}{extra}")

        text = "；".join(parts)
        has_issue = bool(drops or warns)
        self._showStatusAndScheduleClear(
            self.blacklistSaveStatus, "_blacklistClearAfterId",
            text,
            "#FFA500" if has_issue else "green",  # 有问题橙色更醒目
            _STATUS_CLEAR_LONG_MS if has_issue else _STATUS_CLEAR_QUICK_MS)

    # ──────────── 原有功能 ────────────

    def changeTheme(self, choice):
        """切换主题并保存配置"""
        if choice == "亮":
            ctk.set_appearance_mode("light")
        elif choice == "暗":
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("system")
        saveThemeToConfig(choice)

    def toggleAutoStart(self):
        """切换开机自启动状态"""
        enabled = self.autoStartSwitch.get() == 1
        success = set_auto_start(enabled)
        if success:
            if enabled:
                messagebox.showinfo("提示", "已开启开机自启动\n程序将在开机时静默启动到系统托盘。")
            else:
                messagebox.showinfo("提示", "已关闭开机自启动。")
        else:
            messagebox.showerror("错误", "设置开机自启动失败，请重试。")
            # 操作失败，恢复开关到之前的状态
            if enabled:
                self.autoStartSwitch.deselect()
            else:
                self.autoStartSwitch.select()

    def saveWindowSettings(self):
        """保存窗口大小设置"""
        settings_to_save = {}

        # 遍历刚才存的UI控件，收集数据
        for win_key, ui_refs in self._win_ui_vars.items():
            is_max = ui_refs["max_switch"].get() == 1

            # 读取并校验宽高
            try:
                w = int(ui_refs["w_entry"].get())
                h = int(ui_refs["h_entry"].get())
            except ValueError:
                # 15 号：接入统一清除机制，失败走 10s 长档
                self._showStatusAndScheduleClear(
                    self.winSizeSaveStatus, "_winSizeClearAfterId",
                    "❌ 保存失败: 宽度和高度必须是整数", "red",
                    _STATUS_CLEAR_LONG_MS)
                return

            # 强制约束最小值，防止UI崩溃
            min_w = ui_refs["min_w"]
            min_h = ui_refs["min_h"]
            if w < min_w: w = min_w
            if h < min_h: h = min_h

            settings_to_save[win_key] = {
                "maximized": is_max,
                "width": w,
                "height": h
            }

        # 调用 configManager 保存
        try:
            saveWindowSettings(settings_to_save)
            # 15 号：接入统一清除机制。"需重启"信息有页面静态标签
            # （"* 主窗口大小修改需重启软件生效"）常驻兜底，3s 清掉
            # 不丢信息（定稿拍板 A3）。
            self._showStatusAndScheduleClear(
                self.winSizeSaveStatus, "_winSizeClearAfterId",
                "✅ 窗口设置已保存！主窗口修改需重启生效。", "green",
                _STATUS_CLEAR_QUICK_MS)
        except Exception as e:
            self._showStatusAndScheduleClear(
                self.winSizeSaveStatus, "_winSizeClearAfterId",
                f"❌ 保存失败: {e}", "red", _STATUS_CLEAR_LONG_MS)
