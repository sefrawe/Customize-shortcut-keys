'''
新建的快捷键方案
'''
from tkinter import messagebox

from core.configManager import configDirectory, changeShortcutSchemeConfig, changeShortcutSchemeConfig_Description

from utils.shortcutUtils import getShortcutSchemesNames, getStartupEnabledShortcutScheme, getShortcutSchemes, \
    getShortcutSchemeConfigBySchemeName, getShortcutBySchemeName

'''
原先schemeName 混在 **kwargs 里被传给了 CTkFrame，而 CTkFrame 不认识它。导致启动报错。
import customtkinter as ctk
class NewShortcutSchemePage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # 这里写新建的快捷键方案的所有组件和逻辑
        ctk.CTkLabel(self, text="这是新建的快捷键方案").pack(pady=20)
        
        
之前宽度定死是因为mainwindow没有给这个页面设置grid_columnconfigure和grid_rowconfigure，没有权限，导致无法伸缩
# MainWindow.py
self.contentFrame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
self.contentFrame.grid_columnconfigure(0, weight=1)
self.contentFrame.grid_rowconfigure(0, weight=1)
'''

import customtkinter as ctk


class NewShortcutSchemePage(ctk.CTkFrame):
    def __init__(self, master, schemeName=None, onRenamed=None, onStartupChanged=None,**kwargs):
        #on*ed用于回调
        # ← 新增 on*ed 回调参数
        # ← schemeName 单独拎出来
        super().__init__(master, **kwargs)  # ← kwargs 里只剩 fg_color，不会再报错
        self.schemeName = schemeName  # 保存下来，后续页面内部可以用
        self.onRenamed = onRenamed  # 保存回调
        self.onStartupChanged = onStartupChanged

        # 防抖计时器ID
        self._save_after_id = None

        self.grid_columnconfigure(0, weight=1)# 让标题水平可伸缩
        self.grid_rowconfigure(0,weight=0)# 让标题垂直不可伸缩

        # self.grid_columnconfigure(1, weight=1)# 让内容区水平可伸缩
        """后一个框架的宽度由第一个框架决定，指定第二个框架的宽度为1，会导致它们均只占页面的一半宽度"""
        self.grid_rowconfigure(1,weight=0)# 让描述区垂直不可伸缩

        self.grid_rowconfigure(2, weight=1)# 让快捷键列表垂直可伸缩

        #第一个框架用于放置标题和启用状态等
        self.headFrame = ctk.CTkFrame(self,height=80,fg_color="transparent")
        self.headFrame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)#sticky="ew"表示水平填充，sticky="nsew"表示水平和垂直都填充
        # 第二个框架用于放置快捷键方案描述
        self.descFrame = ctk.CTkFrame(self,height=200,fg_color="transparent")
        self.descFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        #第三个框架用于放置快捷键列表
        self.shortcutFrame = ctk.CTkFrame(self)
        self.shortcutFrame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        ctk.CTkLabel(self.headFrame, text=f"{schemeName}", font=("微软雅黑", 25)).pack(side="left")
        btnGroup = ctk.CTkFrame(self.headFrame)
        btnGroup.pack(side="right")
        renameButton = ctk.CTkButton(btnGroup, text="重命名", width=80, command=self.changeTheShortcutSchemeName)
        renameButton.pack(side="right", padx=5)
        #todo 还要有删除与复制（改名但是不删）
        self.selectSegmentedButtonForStartup = ctk.CTkSegmentedButton(
            btnGroup, values=["启用", "禁用"], command=self.changeShortcutSchemeEnabled
        )
        self.selectSegmentedButtonForStartup.pack(side="left", padx=5)

        try:
            startupSchemeName = getStartupEnabledShortcutScheme(configDirectory)["name"]
        except (KeyError, TypeError):
            startupSchemeName = None
        self.startupStatusLabel = ctk.CTkLabel(
            self.headFrame,
            text=f"当前启用方案: {startupSchemeName}" if startupSchemeName else "当前启用方案: 无",
            font=("微软雅黑", 16),
            text_color="green",
            anchor="w"# 左对齐
        )
        self.startupStatusLabel.pack(fill="x", padx=20, pady=(0, 10),side="left")
        # 初始化分段按钮状态
        if startupSchemeName == self.schemeName:
            self.selectSegmentedButtonForStartup.set("启用")
        else:
            self.selectSegmentedButtonForStartup.set("禁用")

        # 备注卡片
        descCard = ctk.CTkFrame(self.descFrame, corner_radius=10)
        descCard.pack(fill="both", expand=True, padx=10, pady=5)
        # 卡片顶部标题行
        descHeader = ctk.CTkFrame(descCard, fg_color="transparent")
        descHeader.pack(fill="x", pady=(5, 2), padx=5)
        ctk.CTkLabel(descHeader, text="方案备注", font=("微软雅黑", 16, "bold")).pack(side="left")
        # 自动保存状态提示 Label
        self.saveStatusVar = ctk.CTkLabel(
            descHeader,
            text="已自动保存",
            text_color="green",
            font=("微软雅黑", 12)
        )
        self.saveStatusVar.pack(side="left", padx=10)
        # 文本输入框 (自动撑满剩余空间)
        self.descTextbox = ctk.CTkTextbox(descCard, font=("微软雅黑", 14), corner_radius=5)
        self.descTextbox.pack(fill="both", expand=True, padx=5, pady=(0, 5))#fill="both"表示水平和垂直都填充，expand=True表示扩展以填充父容器的剩余空间
        # 绑定键盘释放事件，触发防抖自动保存
        self.descTextbox.bind("<KeyRelease>", self.onTextChange)
        # 初次加载数据
        self.loadDescription()


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

    def onTextChange(self, event=None):
        """键盘释放时触发，防抖处理"""
        # 忽略方向键等无意义按键
        if event and event.keysym in ['Up', 'Down', 'Left', 'Right', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R']:
            return
        # 状态变为"编辑中"
        self.saveStatusVar.configure(text="编辑中...", text_color="orange")
        # 取消之前的定时器
        if self._save_after_id:
            self.after_cancel(self._save_after_id)
        # 1000ms (1秒) 后执行保存
        self._save_after_id = self.after(1000, self.saveDescription)

    def saveDescription(self):
        """实际执行保存的逻辑"""
        self.saveStatusVar.configure(text="正在保存...", text_color="blue")
        # "end-1c" 去掉文本框末尾自动多出的一个换行符
        newDescription = self.descTextbox.get("1.0", "end-1c").strip()
        try:
            # 调用 configManager 保存
            changeShortcutSchemeConfig_Description(newDescription=newDescription, name=self.schemeName)
            # 保存成功，恢复状态
            self.saveStatusVar.configure(text="已自动保存", text_color="green")
        except Exception as e:
            self.saveStatusVar.configure(text="保存失败", text_color="red")
            messagebox.showerror("错误", f"备注保存失败: {e}")
        self._save_after_id = None

    def loadDescription(self):
        """从配置文件读取 description 并显示在文本框"""
        config = getShortcutSchemeConfigBySchemeName(self.schemeName)
        if config:
            description = config.get("settings", {}).get("description", "")
            self.descTextbox.delete("1.0", "end")# 清空文本框
            self.descTextbox.insert("1.0", description)
            # 加载完成后重置状态
            self.saveStatusVar.configure(text="已保存", text_color="green")

