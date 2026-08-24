""" 设置页面 """
import re
from tkinter import messagebox

import customtkinter as ctk

from core.configManager import (
    loadThemeFromConfig,
    saveThemeToConfig,
    loadUserBlacklist,
    saveUserBlacklist,
    loadWindowSettings,
    saveWindowSettings,
)
from utils.interpreterRegistry import INTERPRETER_REGISTRY
from utils.systemUtils import set_auto_start, is_auto_start_enabled


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # ── 页面整体布局：单个滚动容器撑满 ──
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scrollFrame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollFrame.grid(row=0, column=0, sticky="nsew")

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
            {"key": "searchWindow", "title": "搜索窗口", "min_w": 400, "min_h": 400}
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
                "• 不区分大小写（如输入 'del' 会匹配 'DEL'）\n"
                "• 子串包含匹配（如输入 'ping' 会匹配 'ping 127.0.0.1'）\n"
                "• 自动去除每行首尾空格，过滤空行\n"
                "• 修改后需点击「保存自定义黑名单」按钮生效"
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

    def _loadCustomBlacklist(self):
        """从 Global Settings.json 读取用户自定义黑名单，转换为文本格式显示"""
        blacklist_dict = loadUserBlacklist()
        # 将字典转换为文本格式
        lines = []
        for interpreter, keywords in blacklist_dict.items():
            if keywords:
                keywords_str = ", ".join(keywords)
                lines.append(f"[{interpreter}] {keywords_str}")
        text = "\n".join(lines)
        self.customBlacklistTextbox.delete("1.0", "end")
        self.customBlacklistTextbox.insert("1.0", text)

    def saveCustomBlacklist(self):
        """保存按钮的回调：将文本框内容解析为字典格式保存"""
        raw_text = self.customBlacklistTextbox.get("1.0", "end-1c")
        blacklist_dict = {}

        for line in raw_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):  # 跳过空行和注释
                continue

            match = re.match(r'^\[(.+?)\]\s*(.+)$', line)
            if match:
                interpreter = match.group(1).strip()
                keywords_str = match.group(2).strip()
                keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                if keywords:
                    blacklist_dict[interpreter] = keywords

        try:
            saveUserBlacklist(blacklist_dict)
            self.blacklistSaveStatus.configure(
                text=f"✅ 已保存 {len(blacklist_dict)} 个解释器的黑名单", text_color="green"
            )
        except Exception as e:
            self.blacklistSaveStatus.configure(text=f"❌ 保存失败: {e}", text_color="red")
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
                self.winSizeSaveStatus.configure(text=f"❌ 保存失败: 宽度和高度必须是整数", text_color="red")
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
            self.winSizeSaveStatus.configure(text="✅ 窗口设置已保存！主窗口修改需重启生效。", text_color="green")
        except Exception as e:
            self.winSizeSaveStatus.configure(text=f"❌ 保存失败: {e}", text_color="red")

