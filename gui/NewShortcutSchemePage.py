'''
新建的快捷键方案
原先schemeName 混在 **kwargs 里被传给了 CTkFrame，而 CTkFrame 不认识它。导致启动报错。
import customtkinter as ctk
class NewShortcutSchemePage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # 这里写新建的快捷键方案的所有组件和逻辑
        ctk.CTkLabel(self, text="这是新建的快捷键方案").pack(pady=20)
'''
''' 新建的快捷键方案 '''
import customtkinter as ctk

class NewShortcutSchemePage(ctk.CTkFrame):
    def __init__(self, master, schemeName=None, **kwargs):
        # ← schemeName 单独拎出来
        super().__init__(master, **kwargs)                  # ← kwargs 里只剩 fg_color，不会再报错
        self.schemeName = schemeName  # 保存下来，后续页面内部可以用
        # 页面内容（暂时占位）
        ctk.CTkLabel(self, text=f"这是新的快捷键方案: {schemeName}").pack(pady=20)
