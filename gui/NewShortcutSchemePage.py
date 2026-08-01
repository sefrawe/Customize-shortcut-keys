'''
新建的快捷键方案
'''
from tkinter import messagebox

from core.configManager import configDirectory, changeShortcutSchemeConfig
from utils.shortcutUtils import getShortcutSchemesNames, getStartupEnabledShortcutScheme, getShortcutSchemes

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
    def __init__(self, master, schemeName=None, onRenamed=None, onStartupChanged=None,**kwargs):#on*ed用于回调
        # ← 新增 on*ed 回调参数
        # ← schemeName 单独拎出来
        super().__init__(master, **kwargs)  # ← kwargs 里只剩 fg_color，不会再报错
        self.schemeName = schemeName  # 保存下来，后续页面内部可以用
        self.onRenamed = onRenamed  # 保存回调
        self.onStartupChanged = onStartupChanged
        # 创建水平布局的容器
        headerFrame = ctk.CTkFrame(self)
        headerFrame.pack(pady=20, fill="x")
        # 标题标签
        ctk.CTkLabel(headerFrame, text=f"{schemeName}", font=("微软雅黑", 25)).pack(side="left", padx=10)
        # 更名按钮
        renameButton = ctk.CTkButton(headerFrame, text="快捷键方案重命名", command=self.changeTheShortcutSchemeName)
        renameButton.pack(side="left", padx=10)
        #启动状态选择分段按钮

        # ★ 改成 self.xxx，后面才能更新
        self.selectSegmentedButtonForStartup = ctk.CTkSegmentedButton(
            headerFrame, values=["启用", "禁用"],
            command=self.changeShortcutSchemeEnabled
        )
        self.selectSegmentedButtonForStartup.pack(side="left", padx=10)

        # 根据“自己是不是当前启用方案”来决定分段按钮显示什么
        try:
            startupSchemeName = getStartupEnabledShortcutScheme(configDirectory)["name"]
        except (KeyError, TypeError):
            startupSchemeName = None
        if startupSchemeName == self.schemeName:
            self.selectSegmentedButtonForStartup.set("启用")
        else:
            self.selectSegmentedButtonForStartup.set("禁用")
        # ★ 状态 Label 也改成 self.xxx
        self.startupStatusLabel = ctk.CTkLabel(
            self,
            text=f"当前启用方案: {startupSchemeName}" if startupSchemeName else "当前启用方案: 无",
            font=("微软雅黑", 16)
        )
        self.startupStatusLabel.pack(side="left", padx=10)

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

    def changeShortcutSchemeEnabled(self, status):
        """切换启用状态：保证全局只有一个启用方案，并刷新所有相关页面"""
        if status == "启用":
            # 1) 先把“除自己外其它已启用”的方案全部禁用
            for scheme in getShortcutSchemes(configDirectory):
                if scheme["name"] != self.schemeName and scheme["startupEnabled"]:
                    changeShortcutSchemeConfig(
                        newStartupEnabled=False,
                        schemeName=scheme["name"]
                    )
            # 2) 再启用当前方案
            changeShortcutSchemeConfig(
                newStartupEnabled=True,
                schemeName=self.schemeName
            )
        else:  # status == "禁用"
            changeShortcutSchemeConfig(
                newStartupEnabled=False,
                schemeName=self.schemeName
            )
        # 3) 刷新当前页面（分段按钮 + 状态 Label）
        self.refreshStartupDisplay()
        # 4) 通知主窗口去刷新其它方案页面里同样的显示
        if self.onStartupChanged:
            self.onStartupChanged()

    def refreshStartupDisplay(self):
        """根据最新配置刷新本页面的分段按钮和状态 Label"""
        try:
            startupSchemeName = getStartupEnabledShortcutScheme(configDirectory)["name"]
        except (KeyError, TypeError):
            startupSchemeName = None

        # 更新 Label 文本
        self.startupStatusLabel.configure(
            text=f"当前启用方案: {startupSchemeName}" if startupSchemeName# 如果有启用方案，显示其名称
            else "当前启用方案: 无"
        )
        # 更新分段按钮选中态（避免触发 command 死循环）
        if startupSchemeName == self.schemeName:
            self.selectSegmentedButtonForStartup.set("启用")
        else:
            self.selectSegmentedButtonForStartup.set("禁用")
