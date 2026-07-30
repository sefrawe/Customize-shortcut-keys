"""
设置页面
"""
import customtkinter as ctk

from core.configManager import loadThemeFromConfig, saveThemeToConfig


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)# 初始化父类
        # 创建主题选择分段按钮
        self.themeLabel = ctk.CTkLabel(self, text="主题设置", font=("微软雅黑", 24))
        self.themeLabel.pack(pady=20)

        self.themeSeg = ctk.CTkSegmentedButton(# 创建主题选择分段按钮
            self,
            values=["亮", "暗", "跟随系统"],
            command=self.change_theme,
            font=("微软雅黑", 16)
        )
        # 从配置文件读取当前主题并设置默认值
        current_theme = loadThemeFromConfig()
        self.themeSeg.set(current_theme)
        self.themeSeg.pack(pady=10, padx=20, fill="x")

        # 立即应用当前主题
        self.change_theme(current_theme)

    def change_theme(self, choice):
        """切换主题并保存配置"""
        # 应用主题
        if choice == "亮":
            ctk.set_appearance_mode("light")
        elif choice == "暗":
            ctk.set_appearance_mode("dark")
        else:  # System
            ctk.set_appearance_mode("system")

        # 保存到配置文件
        saveThemeToConfig(choice)

        # # 显示提示信息
        # if choice!="System":
        #     self.showNotification(f"主题已切换为: {choice}")
        # else:
        #     self.showNotification(f"主题已切换为: 跟随系统")

    # def showNotification(self, param):
    #     """显示提示信息"""
    #     notification = ctk.CTkLabel(self, text=param, font=("微软雅黑", 14), text_color="green")
    #     notification.pack(pady=10)
    #     # 4秒后自动销毁提示信息
    #     self.after(4000, notification.destroy)

