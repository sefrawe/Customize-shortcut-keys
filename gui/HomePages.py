'''
首页
'''
import customtkinter as ctk
class HomePage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # 这里写首页的所有组件和逻辑
        ctk.CTkLabel(self, text="这是首页").pack(pady=20)
