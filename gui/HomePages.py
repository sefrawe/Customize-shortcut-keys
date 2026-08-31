''' 首页 '''
import os
import webbrowser
import customtkinter as ctk
from PIL import Image


class HomePage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # ── 图片（项目根目录下的 icon.png）───────────────────────
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "icon.png",
        )
        if os.path.exists(icon_path):
            pil_image = Image.open(icon_path)
            ctk.CTkLabel(self, text="", image=ctk.CTkImage(
                light_image=pil_image,
                dark_image=pil_image,
                size=(96, 96),
            )).pack(pady=(30, 10))

        # ── 标题 ────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="自定义快捷键工具",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(pady=(0, 5))

        ctk.CTkLabel(
            self,
            text="开源全局快捷键监听与自定义工具",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        ).pack(pady=(0, 25))

        # ── 功能简介 ────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text=(
                "功能简介：\n\n"
                "· 全局快捷键监听，自定义组合键映射到各种动作\n"
                "· 支持模拟输入文本、执行系统命令、鼠标操作等\n"
                "· 多方案管理，一键启用/禁用，支持冲突检测\n"
                "· 动作组：把一系列键盘鼠标操作串起来执行\n"
            ),
            justify="left",
            font=ctk.CTkFont(size=14),
        ).pack(pady=10)

        # ── 项目地址 ────────────────────────────────────────────
        repo_url = "https://github.com/sefrawe/Customize-shortcut-keys"
        link = ctk.CTkLabel(
            self,
            text="GitHub 项目地址：https://github.com/sefrawe/Customize-shortcut-keys",
            font=ctk.CTkFont(size=14, underline=True),
            text_color="#4A9EFF",
            cursor="hand2",
        )
        link.pack(pady=(20, 30))
        link.bind("<Button-1>", lambda e: webbrowser.open(repo_url))
