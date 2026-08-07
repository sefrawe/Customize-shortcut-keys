""" 设置页面 """
import customtkinter as ctk
from tkinter import messagebox
from core.configManager import loadThemeFromConfig, saveThemeToConfig
from utils.systemUtils import set_auto_start, is_auto_start_enabled


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # 1. 主页面只负责撑满空间，并放入一个滚动容器
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
            font=("微软雅黑", 16)
        )
        current_theme = loadThemeFromConfig()
        self.themeSeg.set(current_theme)
        self.themeSeg.pack(pady=10, padx=20, fill="x")
        self.changeTheme(current_theme)

        # ==================== 通用设置 ====================
        self.generalLabel = ctk.CTkLabel(self.scrollFrame, text="通用设置", font=("微软雅黑", 24))
        self.generalLabel.pack(pady=(40, 10))

        # 开机自启动
        autoStartFrame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
        autoStartFrame.pack(pady=10, padx=20, fill="x")

        autoStartLabel = ctk.CTkLabel(
            autoStartFrame,
            text="开机自启动（静默启动到系统托盘）",
            font=("微软雅黑", 16),
            anchor="w"
        )
        autoStartLabel.pack(side="left", padx=(0, 10))

        self.autoStartSwitch = ctk.CTkSwitch(
            autoStartFrame,
            text="",
            command=self.toggleAutoStart,
            width=60
        )
        self.autoStartSwitch.pack(side="right")

        # 初始化开关状态：从注册表读取当前是否已开启
        if is_auto_start_enabled():
            self.autoStartSwitch.select()

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

