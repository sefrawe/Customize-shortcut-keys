'''
新建的快捷键方案
'''
from tkinter import messagebox

from core.configManager import configDirectory, changeShortcutSchemeConfig
from utils.shortcutUtils import getShortcutSchemesNames

'''
原先schemeName 混在 **kwargs 里被传给了 CTkFrame，而 CTkFrame 不认识它。导致启动报错。
import customtkinter as ctk
class NewShortcutSchemePage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # 这里写新建的快捷键方案的所有组件和逻辑
        ctk.CTkLabel(self, text="这是新建的快捷键方案").pack(pady=20)
'''

import customtkinter as ctk


class NewShortcutSchemePage(ctk.CTkFrame):
    def __init__(self, master, schemeName=None, onRenamed=None, **kwargs):
        # ← 新增 onRenamed 参数
        # ← schemeName 单独拎出来
        super().__init__(master, **kwargs)  # ← kwargs 里只剩 fg_color，不会再报错
        self.schemeName = schemeName  # 保存下来，后续页面内部可以用
        self.onRenamed = onRenamed  # ← 保存回调
        # 创建水平布局的容器
        headerFrame = ctk.CTkFrame(self)
        headerFrame.pack(pady=20, fill="x")
        # 标题标签
        ctk.CTkLabel(headerFrame, text=f"{schemeName}", font=("微软雅黑", 25)).pack(side="left", padx=10)
        # 按钮
        button = ctk.CTkButton(headerFrame, text="改变快捷键方案名字", command=self.changeTheShortcutSchemeName)
        button.pack(side="left", padx=10)

    # def changeTheShortcutSchemeName(self):
    #     dialog = ctk.CTkInputDialog(text="输入新名字", title="改变快捷键方案名字")
    #     self.schemeName = dialog.get_input()
    #     newName = self.schemeName
    #     if newName is None or newName.strip() == "":  # ← 用变量判断
    #         return
    #     oldName = self.schemeName  # ← 先保存旧名字！原代码直接覆盖了，是bug
    #     try:
    #         if newName in getShortcutSchemesNames(configDirectory):
    #             raise ValueError(f"快捷键方案名称 '{newName}' 已存在，请更换名称")
    #         # 用正确的参数名调用
    #         changeShortcutSchemeConfig(newSchemeName=newName, schemeName=oldName)
    #         # 改名成功，更新自身记录
    #         self.schemeName = newName
    #         # 通过回调通知主窗口刷新导航栏并跳转
    #         if self.onRenamed:
    #             self.onRenamed(oldName, newName)
    #     except ValueError as e:
    #         messagebox.showerror("错误", str(e))

    def changeTheShortcutSchemeName(self):
        dialog = ctk.CTkInputDialog(text="输入新名字", title="改变快捷键方案名字")
        newName = dialog.get_input()  # ← 只读取，不覆盖
        if newName is None or newName.strip() == "":
            return
        oldName = self.schemeName  # ← 先保存旧名字（此时还是"3"）
        try:
            if newName in getShortcutSchemesNames(configDirectory):
                raise ValueError(f"快捷键方案名称 '{newName}' 已存在，请更换名称")
            changeShortcutSchemeConfig(newSchemeName=newName, schemeName=oldName)
            self.schemeName = newName  # ← 改名成功后才更新
            if self.onRenamed:
                self.onRenamed(oldName, newName)
        except ValueError as e:
            messagebox.showerror("错误", str(e))
