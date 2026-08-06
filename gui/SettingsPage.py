""" 设置页面 """
import customtkinter as ctk
from core.configManager import loadThemeFromConfig, saveThemeToConfig

class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)# 初始化父类

        # 1. 主页面只负责撑满空间，并放入一个滚动容器
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scrollFrame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollFrame.grid(row=0, column=0, sticky="nsew")

        # 2. 以下所有控件的父容器从 self 改为 self.scrollFrame

        # 创建主题选择分段按钮
        self.themeLabel = ctk.CTkLabel(self.scrollFrame, text="主题设置", font=("微软雅黑", 24))
        self.themeLabel.pack(pady=20,)

        self.themeSeg = ctk.CTkSegmentedButton(
            self.scrollFrame,
            values=["亮", "暗", "跟随系统"],
            command=self.changeTheme,
            font=("微软雅黑", 16)
        )

        # 从配置文件读取当前主题并设置默认值
        current_theme = loadThemeFromConfig()
        self.themeSeg.set(current_theme)
        self.themeSeg.pack(pady=10, padx=20, fill="x")

        # 立即应用当前主题
        self.changeTheme(current_theme)

        #

    def changeTheme(self, choice):
        """切换主题并保存配置"""
        # 应用主题
        if choice == "亮":
            ctk.set_appearance_mode("light")
        elif choice == "暗":
            ctk.set_appearance_mode("dark")
        else: # System
            ctk.set_appearance_mode("system")
            # 保存到配置文件
        saveThemeToConfig(choice)
