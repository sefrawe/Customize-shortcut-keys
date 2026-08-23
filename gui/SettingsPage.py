""" 设置页面 """
import re
from tkinter import messagebox

import customtkinter as ctk

from core.configManager import (
    loadThemeFromConfig,
    saveThemeToConfig,
    loadUserBlacklist,
    saveUserBlacklist,
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
