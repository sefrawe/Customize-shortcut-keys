'''
新建的快捷键方案
'''
from tkinter import messagebox

from core.configManager import configDirectory, changeShortcutSchemeConfig, changeShortcutSchemeConfig_Description, \
    copyShortcutSchemeConfig, deleteShortcutSchemeConfig, changeShortcutConfig_enabled

from utils.shortcutUtils import getShortcutSchemesNames, getStartupEnabledShortcutScheme, getShortcutSchemes, \
    getShortcutSchemeConfigBySchemeName, getShortcutBySchemeName, \
    getShortcutByShortcutId, getshortcut

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
    def __init__(self, master, schemeName=None, onRenamed=None, onStartupChanged=None,onCopied=None,ondeleted=None,**kwargs):
        #on*ed用于回调
        # ← 新增 on*ed 回调参数
        # ← schemeName 单独拎出来
        super().__init__(master, **kwargs)  # ← kwargs 里只剩 fg_color，不会再报错
        self.schemeName = schemeName  # 保存下来，后续页面内部可以用
        self.onRenamed = onRenamed  # 保存回调
        self.onStartupChanged = onStartupChanged
        self.onCopied = onCopied
        self.onDeleted = ondeleted
        self._save_after_id = None# 防抖计时器ID(用于自动保存快捷键方案备注)

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
        self.shortcutFrame = ctk.CTkScrollableFrame(self)
        self.shortcutFrame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        ctk.CTkLabel(self.headFrame, text=f"{schemeName}", font=("微软雅黑", 25)).pack(side="left")
        btnGroup = ctk.CTkFrame(self.headFrame)
        btnGroup.pack(side="right")
        createNewShortcutButton = ctk.CTkButton(btnGroup, text="+ 新建快捷键", command=None)#todo:新建快捷键函数
        createNewShortcutButton.pack(side='right', padx=10)
        renameButton = ctk.CTkButton(btnGroup, text="重命名", width=80, command=self.changeTheShortcutSchemeName)
        renameButton.pack(side="right", padx=5)
        copyButton = ctk.CTkButton(btnGroup, text="复制", width=80, command=self.copyTheShortcutScheme)
        copyButton.pack(side="right", padx=5)
        deleteButton = ctk.CTkButton(btnGroup, text="删除", width=80, command=self.deleteTheShortcutScheme,fg_color="#A30000", hover_color="#7A0000")
        deleteButton.pack(side="right", padx=5)

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
            text_color="green"if startupSchemeName == self.schemeName else "orange",#这个不行，切换页面颜色不变
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

        shortcuts = getShortcutBySchemeName(self.schemeName)
        shortcuts.sort(key=lambda x: x.get("id", 0))
        self.shortcutStartupButtons = {}

        headInfoFrame = ctk.CTkLabel(self.shortcutFrame, text="冲突检查提示\n\n66", font=("微软雅黑", 14), bg_color="transparent")
        headInfoFrame.pack(fill="x", pady=5, padx=5)#todo是否冲突提示（无冲突则显示没有冲突，有则提示移动到末尾查看具体冲突内容）

        for item in shortcuts:
            # 1. 单行卡片外框
            rowFrame = ctk.CTkFrame(self.shortcutFrame, corner_radius=5)
            rowFrame.pack(fill="x", pady=5, padx=5)
            # 左侧信息区容器
            infoFrame = ctk.CTkFrame(rowFrame)
            infoFrame.pack(side="left", fill="x", expand=True, pady=5)
            # 使用 grid 布局
            infoFrame.grid_columnconfigure(0, weight=0, minsize=80)  # ID 列（最小宽度40）
            infoFrame.grid_columnconfigure(1, weight=0, minsize=100)  # 名字列（最小宽度120）
            infoFrame.grid_columnconfigure(2, weight=0, minsize=100)  # 案键列（最小宽度150）
            infoFrame.grid_columnconfigure(3, weight=1)  # 备注列（可扩展）
            # 1. ID
            ctk.CTkLabel(infoFrame, text=str(item.get("id", ""))).grid(row=0, column=0, padx=(10, 5), sticky="w")
            # 2. 名字
            ctk.CTkLabel(infoFrame, text=item.get("name", "")).grid(row=0, column=1, padx=5, sticky="w")
            # 3. 案键
            ctk.CTkLabel(infoFrame, text=item.get("keyCombination", "")).grid(row=0, column=2, padx=5, sticky="w")
            # 4. 备注
            ctk.CTkLabel(infoFrame, text=item.get("description", "")).grid(row=0, column=3, padx=5, sticky="w")
            # 右侧操作区容器 (靠右对齐)
            actionFrame = ctk.CTkFrame(rowFrame, fg_color="transparent")
            actionFrame.pack(side="right", padx=10, pady=5)
            # 7. 删除按钮 (最右侧)
            ctk.CTkButton(actionFrame, text="删除", width=50, fg_color="#A30000", hover_color="#7A0000").pack(
                side="right", padx=(5, 0))
            # 6. 编辑按钮
            ctk.CTkButton(actionFrame, text="编辑", width=50).pack(side="right", padx=5)
            # 5. 状态开关
            shortcutsSelectSegmentedButtonForStartup= ctk.CTkSegmentedButton(
                actionFrame,
                values=["启用", "禁用"],
                command=lambda value, shortcutId=item.get("id"): self.changeShortcutEnabled(shortcutId, value)
            )
            shortcutsSelectSegmentedButtonForStartup.pack(side="right", padx=5)
            shortcutId = item.get("id")
            self.shortcutStartupButtons[shortcutId] = shortcutsSelectSegmentedButtonForStartup
            shortcutsSelectSegmentedButtonForStartup.set("启用" if item.get("enabled", False) else "禁用")





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
        self.refreshSchemeStartupDisplay()
        # 4) 通知主窗口去刷新其它方案页面里同样的显示
        if self.onStartupChanged:
            self.onStartupChanged()

    def refreshSchemeStartupDisplay(self):
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
            self.startupStatusLabel.configure(text_color="green")
        else:
            self.selectSegmentedButtonForStartup.set("禁用")
            self.startupStatusLabel.configure(text_color="orange")

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

    def copyTheShortcutScheme(self):
        """复制当前快捷键方案"""
        dialog = ctk.CTkInputDialog(text="输入新方案的名字（不可重复）", title="复制快捷键方案")
        newSchemeName = dialog.get_input()  # ← 只读取，不覆盖
        if newSchemeName is None or newSchemeName.strip() == "":
            return
        oldSchemeName = self.schemeName  # ← 先保存旧名字
        try:
            if newSchemeName in getShortcutSchemesNames(configDirectory):
                raise ValueError(f"快捷键方案名称 '{newSchemeName}' 已存在，请更换名称")
            try:
                copyShortcutSchemeConfig(newSchemeName=newSchemeName, schemeName=oldSchemeName)
            except FileNotFoundError as e:
                messagebox.showerror("错误", f"复制快捷键方案失败: {e}, 请确保原方案的配置文件存在。")
            if self.onCopied:
                self.onCopied(oldSchemeName, newSchemeName)
        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def deleteTheShortcutScheme(self):
        """删除当前快捷键方案"""
        confirm = messagebox.askyesno("确认删除", f"确定要删除快捷键方案 '{self.schemeName}' 吗？此操作不可撤销。")
        if not confirm:
            return
        try:
            deleteShortcutSchemeConfig(schemeName=self.schemeName)
        except FileNotFoundError as e:
            messagebox.showerror("错误", f"删除快捷键方案失败: {e}, 请确保方案的配置文件存在。")
        if self.onDeleted:
            self.onDeleted(self.schemeName)

    def changeShortcutEnabled(self, shortcutId, status=None):
        """切换单个快捷键的启用状态"""
        shortcut = getShortcutByShortcutId(self.schemeName, shortcutId)
        if shortcut is None:
            messagebox.showerror("错误", f"未找到快捷键 ID {shortcutId} 的配置。")
            return

        shortcutOldStatus = getshortcut(shortcut).get("enabled", False)
        shortcutNewStatus = (not shortcutOldStatus) if status is None else (status == "启用")
        try:
            changeShortcutConfig_enabled(self.schemeName, shortcutId, shortcutNewStatus)
        except (FileNotFoundError, ValueError) as e:
            messagebox.showerror("错误", f"切换快捷键启用状态失败: {e}")
            return
        self.refreshShortcutStartupDisplay(shortcutId)



        # try:
        #     startupShortcutNames = getStartupEnabledShortcutNameBySchemeName(self.schemeName)
        # except (KeyError, TypeError):
        #     startupShortcutNames = None
        #
        # for startupShortcutName in startupShortcutNames:
        #     if startupShortcutName == item.get("name", ""):
        #         # 判断条件是当前启用的快捷键名称是否与该快捷键的名称相同
        #         shortcutsSelectSegmentedButtonForStartup.set("启用")
        #     else:
        #         shortcutsSelectSegmentedButtonForStartup.set("禁用")

    def refreshShortcutStartupDisplay(self,shortcutId):
        """刷新快捷键的启用状态显示"""
        shortcut = getShortcutByShortcutId(self.schemeName, shortcutId)
        if not shortcut:
            return
        button = self.shortcutStartupButtons.get(shortcutId)
        if button is None:
            return
        button.set("启用" if shortcut.get("enabled", False) else "禁用")
