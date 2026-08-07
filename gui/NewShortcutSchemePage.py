'''
新建的快捷键方案
'''

"""
==========================================================
【冲突检测功能 - 整体架构与实现指南】
==========================================================

一、统一的数据结构（冲突报告）
----------------------------------------------------------
每次检测完一个方案，生成一份“冲突报告”字典，供前端直接渲染使用：
- scheme_name: str        -> 这是哪个方案的报告（路由分发用）。
- mode: str               -> 当前检测模式（"所有方案与此方案"、"关闭"等）。
- has_internal: bool      -> 是否有内部冲突。
- internal_conflicts: dict-> 内部冲突详情，格式: {"ctrl+c": [0, 2], "ctrl+v": [1, 3]}。
- has_cross: bool         -> 是否有跨方案冲突。
- cross_conflicts: list   -> 跨方案冲突详情，格式: [{"my_id": 0, "other_scheme": "方案B", "other_id": 1, "key": "ctrl+c"}]。

二、冲突检测逻辑（纯后台，置于 shortcutUtils.py 或专门工具类）
----------------------------------------------------------
1. 内部冲突检测（只看自己）：
   - 获取当前方案所有 enabled=True 的快捷键。
   - 【关键避坑：字符串归一化】比对前，对 keyCombination 进行归一化处理（按 '+' 拆分、排序后再拼接），
     避免 "ctrl+alt+1" 和 "alt+ctrl+1" 被误判为不冲突。
   - 按归一化后的 key 分组，若对应多个 ID 则为内部冲突。

2. 跨方案冲突检测（看别人）：
   - 若模式为“关闭”或“仅此方案内”，直接跳过。
   - 若模式为“当前启用的方案与此方案”，只拿其他方案中 startupEnabled=True 的数据比对。
   - 若模式为“所有方案与此方案”，拿所有方案数据比对。
   - 比对时同样使用归一化后的 keyCombination 进行匹配。

三、UI 渲染规则（前端，NewShortcutSchemePage）
----------------------------------------------------------
使用 CTkTextbox 的 Tag 机制（red_tag, orange_tag）实现单框多色混排。

1. 导航栏 Label 颜色决策树（优先级从高到低）：
   - 最高：has_internal == True -> 红色（内部冲突，最严重）
   - 次高：has_cross == True    -> 橙色（跨方案冲突）
   - 第三：mode == "关闭" 且 startupEnabled == True -> 橙色（警告：已启用但未开检测）
   - 第四：无冲突 且 startupEnabled == True -> 绿色（健康）
   - 默认：无冲突 且 startupEnabled == False -> 白色（默认不碍事）

2. 页面内 Textbox 混排渲染逻辑：
   - 清空 Textbox 内容。
   - 【关闭模式分支】：
     · 若方案已启用：用 orange_tag 插入“⚠️ 方案已启用但冲突检测处于关闭状态”。
     · 若方案未启用：用默认颜色插入“冲突检测已关闭”。
   - 【非关闭模式分支】：
     · 如果有内部冲突：用 red_tag 插入“🔴 发现内部冲突:”，换行，列出冲突的 ID。
     · 如果有跨方案冲突：用 orange_tag 插入“🟠 发现跨方案冲突:”，换行，列出与哪个方案、哪个 ID 冲突。
     · 如果无冲突：用默认颜色插入“✅ 未检测到冲突”。

四、架构与触发机制（核心难点，由 MainWindow 主导）
----------------------------------------------------------
因为跨方案检测需要全局视角，必须由主窗口统一指挥。

1. 缓存机制（防脏数据/防页面切换空白）：
   - 主窗口维护一个内存字典 self.conflict_reports_cache = {}。
   - 全局重算后，将所有方案的最新报告存入该缓存。
   - 在主窗口的 showPage(name) 方法中补充逻辑：如果展示的是 NewShortcutSchemePage，
     顺手把缓存里该方案的最新报告喂给它，让页面自身调用渲染方法更新 Textbox。

2. 触发频率控制（性能优化）：
   - 区分“轻量级变更”（改备注、改名）和“重量级变更”（增删改快捷键、切启用状态、切检测模式）。
   - 仅“重量级变更”通过 onExecutorRefresh 通知主窗口执行全量冲突重算（refresh_all_conflict_status），
     避免敲键盘防抖保存备注时频繁读取全盘 JSON 导致界面卡顿。
"""

from tkinter import messagebox

from core.configManager import configDirectory, changeShortcutSchemeConfig, changeShortcutSchemeConfig_Description, \
    copyShortcutSchemeConfig, deleteShortcutSchemeConfig, changeShortcutConfig_enabled, \
    addShortcut, deleteShortcut, resignShortcutIds, copyShortcut, changeShortcutSchemeConfig_conflictDetectionMode
from gui.ShortcutEditWindow import ShortcutEditWindow
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
    def __init__(self, master, schemeName=None, onRenamed=None, onStartupChanged=None, onCopied=None, ondeleted=None,
                 onExecutorRefresh=None, **kwargs):
        # on*ed用于回调
        # ← 新增 on*ed 回调参数
        # ← schemeName 单独拎出来
        super().__init__(master, **kwargs)  # ← kwargs 里只剩 fg_color，不会再报错
        self.schemeName = schemeName  # 保存下来，后续页面内部可以用
        self.onRenamed = onRenamed  # 保存回调
        self.onStartupChanged = onStartupChanged
        self.onCopied = onCopied
        self.onDeleted = ondeleted
        self.onExecutorRefresh = onExecutorRefresh
        self._save_after_id = None  # 防抖计时器ID(用于自动保存快捷键方案备注)

        self.grid_columnconfigure(0, weight=1)  # 让标题水平可伸缩
        self.grid_rowconfigure(0, weight=0)  # 让标题垂直不可伸缩

        # self.grid_columnconfigure(1, weight=1)# 让内容区水平可伸缩
        """后一个框架的宽度由第一个框架决定，指定第二个框架的宽度为1，会导致它们均只占页面的一半宽度"""
        self.grid_rowconfigure(1, weight=0)  # 让描述区垂直不可伸缩

        self.grid_rowconfigure(2, weight=1)  # 让快捷键列表垂直可伸缩

        # 第一个框架用于放置标题和启用状态等
        self.headFrame = ctk.CTkFrame(self, height=80, fg_color="transparent")
        self.headFrame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)  # sticky="ew"表示水平填充，sticky="nsew"表示水平和垂直都填充
        # 第二个框架用于放置快捷键方案描述
        self.descFrame = ctk.CTkFrame(self, height=200, fg_color="transparent")
        self.descFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        # 第三个框架用于放置快捷键列表
        self.shortcutFrame = ctk.CTkScrollableFrame(self)
        self.shortcutFrame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        ctk.CTkLabel(self.headFrame, text=f"{schemeName}", font=("微软雅黑", 25)).pack(side="left")
        btnGroup = ctk.CTkFrame(self.headFrame)
        btnGroup.pack(side="right")
        createNewShortcutButton = ctk.CTkButton(btnGroup, text="+ 新建快捷键", command=self.openaddShortcutDialog)
        createNewShortcutButton.pack(side='right', padx=10)
        renameButton = ctk.CTkButton(btnGroup, text="重命名", width=80, command=self.changeTheShortcutSchemeName)
        renameButton.pack(side="right", padx=5)
        copyButton = ctk.CTkButton(btnGroup, text="复制", width=80, command=self.copyTheShortcutScheme)
        copyButton.pack(side="right", padx=5)
        deleteButton = ctk.CTkButton(btnGroup, text="删除", width=80, command=self.deleteTheShortcutScheme,
                                     fg_color="#A30000", hover_color="#7A0000")
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
            text_color="green" if startupSchemeName == self.schemeName else "orange",  # 这个不行，切换页面颜色不变
            anchor="w"  # 左对齐
        )
        self.startupStatusLabel.pack(fill="x", padx=20, pady=(0, 10), side="left")
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
        self.descTextbox.pack(fill="both", expand=True, padx=5,
                              pady=(0, 5))  # fill="both"表示水平和垂直都填充，expand=True表示扩展以填充父容器的剩余空间
        # 绑定键盘释放事件，触发防抖自动保存
        self.descTextbox.bind("<KeyRelease>", self.onTextChange)
        # 初次加载数据
        self.loadDescription()
        # 渲染快捷键列表
        self.renderShortcutList()

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
            self._refreshExecutor()
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
        self._refreshExecutor()
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
            text=f"当前启用方案: {startupSchemeName}" if startupSchemeName  # 如果有启用方案，显示其名称
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
            self.descTextbox.delete("1.0", "end")  # 清空文本框
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
            self._refreshExecutor()
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
        self._refreshExecutor()
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
        self._refreshExecutor()

    def refreshShortcutStartupDisplay(self, shortcutId):
        """刷新快捷键的启用状态显示"""
        shortcut = getShortcutByShortcutId(self.schemeName, shortcutId)
        if not shortcut:
            return
        button = self.shortcutStartupButtons.get(shortcutId)
        if button is None:
            return
        button.set("启用" if shortcut.get("enabled", False) else "禁用")

    def openaddShortcutDialog(self):
        """打开添加快捷键对话框"""
        dialog = ctk.CTkInputDialog(text="请输入新的快捷键名称:", title="新建快捷键")
        newName = dialog.get_input()  # ← 只调用一次，存起来
        if newName is None or newName.strip() == "":  # ← 用变量判断
            return
        try:
            addShortcut(self.schemeName, newName)
            self.refreshShortcutList()
            self._refreshExecutor()
        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def refreshShortcutList(self):
        """刷新快捷键列表"""
        # 清空现有的快捷键列表
        for widget in self.shortcutFrame.winfo_children():
            widget.destroy()
        self.renderShortcutList()

    def renderShortcutList(self):
        """重建快捷键列表"""
        # 重新加载快捷键列表
        shortcuts = getShortcutBySchemeName(self.schemeName)
        shortcuts.sort(key=self._shortcutSortKey)
        self.shortcutStartupButtons = {}

        # 顶部冲突检测区域（整体卡片）
        headInfoFrame = ctk.CTkFrame(self.shortcutFrame)
        headInfoFrame.pack(fill="x", pady=5, padx=5)

        headInfoFrame.grid_columnconfigure(0, weight=0)  # 标签列，不伸缩
        headInfoFrame.grid_columnconfigure(1, weight=1)  # 选项列，可伸缩


        # 第一行：标签 + 选项按钮
        conflictDetectionLabel = ctk.CTkLabel(
            headInfoFrame,
            text="按键冲突检测（仅启用的快捷键参与检测）:",
            font=("微软雅黑", 14),
            bg_color="transparent"
        )
        conflictDetectionLabel.grid(row=0, column=0, padx=(10, 5), pady=(5, 2), sticky="w")

        # 在 NewShortcutSchemePage.py 的 renderShortcutList 方法中
        conflictDetectionOptions = ctk.CTkSegmentedButton(
            headInfoFrame,
            values=["所有方案与此方案", "当前启用的方案与此方案", "仅此方案内", "关闭"],
            command=lambda mode: self.changeConflictDetectionMode(self.schemeName, mode)
        )
        conflictDetectionOptions.grid(row=0, column=1, padx=5, pady=(5, 2), sticky="w")
        # 从配置文件中获取当前的冲突检测模式
        config = getShortcutSchemeConfigBySchemeName(self.schemeName)
        if config:
            currentMode = config.get("settings", {}).get("conflictDetectionMode", "仅此方案内")
        else:
            currentMode = "仅此方案内"
        conflictDetectionOptions.set(currentMode)


        # 按钮直接放在 headInfoFrame 里，避免按钮组过长导致布局问题
        ctk.CTkButton(headInfoFrame, text="启用所有", width=80,
                      command=self.enableAllShortcuts).grid(row=0, column=2, padx=5, pady=(5, 2), sticky="e")
        ctk.CTkButton(headInfoFrame, text="禁用所有", width=80,
                      command=self.disableAllShortcuts).grid(row=0, column=3, padx=5, pady=(5, 2), sticky="e")
        ctk.CTkButton(headInfoFrame, text="删除所有", width=80,
                      fg_color="#A30000", hover_color="#7A0000", command=self.deleteAllShortcuts).grid(row=0, column=4, padx=5, pady=(5, 2), sticky="e")
        ctk.CTkButton(headInfoFrame, text="搜索快捷键", width=80,
                      command=self.searchShortcuts).grid(row=0, column=5, padx=5, pady=(5, 2), sticky="e")

        # 第二行：检测结果（选项按钮正下方）
        self.conflictResultTextbox = ctk.CTkTextbox(
            headInfoFrame,
            height=100,
            font=("微软雅黑", 13),
            corner_radius=5,
            state="disabled"  # 禁止编辑
        )
        self.conflictResultTextbox.grid(row=1, column=0, columnspan=6, sticky="ew", padx=10, pady=(2, 10))
        #检测结果允许出现在按钮（column=2, column=3, column=4, column=5）下


        for item in shortcuts:
            # 1. 单行卡片外框
            rowFrame = ctk.CTkFrame(self.shortcutFrame, corner_radius=5)
            rowFrame.pack(fill="x", pady=5, padx=5)

            # 左侧信息区容器
            infoFrame = ctk.CTkFrame(rowFrame)
            infoFrame.pack(side="left", fill="x", expand=True, pady=5)
            # 使用 grid 布局
            infoFrame.grid_columnconfigure(0, weight=0, minsize=80)
            infoFrame.grid_columnconfigure(1, weight=0, minsize=100)
            infoFrame.grid_columnconfigure(2, weight=0, minsize=100)
            infoFrame.grid_columnconfigure(3, weight=1)

            # 1. ID
            ctk.CTkLabel(infoFrame, text=str(item.get("id", ""))).grid(row=0, column=0, padx=(10, 5), sticky="w")
            # 2. 名字
            ctk.CTkLabel(infoFrame, text=item.get("name", "")).grid(row=0, column=1, padx=5, sticky="w")
            # 3. 案键
            ctk.CTkLabel(infoFrame, text=item.get("keyCombination", "")).grid(row=0, column=2, padx=5, sticky="w")
            # 4. 备注
            ctk.CTkLabel(infoFrame, text=item.get("description", "")).grid(row=0, column=3, padx=5, sticky="w")

            # 右侧操作区容器（编辑/删除先保留入口，后续再补逻辑）
            actionFrame = ctk.CTkFrame(rowFrame, fg_color="transparent")
            actionFrame.pack(side="right", padx=10, pady=5)

            # 7. 删除按钮（最右侧）
            (ctk.CTkButton(actionFrame, text="删除", width=50, fg_color="#A30000", hover_color="#7A0000",
                           command=lambda shortcutId=item.get("id"): self.deleteShortcut(shortcutId)
                           # command=lambda: self.deleteShortcut(item.get("id"))
                           )
            .pack(
                side="right", padx=(5, 0)
            ))
            # 8.复制按钮
            ctk.CTkButton(actionFrame, text="复制", width=50,
                          command=lambda shortcutId=item.get("id"): self.copyShortcut(shortcutId)
                          ).pack(side="right", padx=5)
            # 6. 编辑按钮
            ctk.CTkButton(actionFrame, text="编辑", width=50,
                          command=lambda shortcutId=item.get("id"): self.editShortcut(shortcutId)
                          ).pack(side="right", padx=5)
            # 5. 状态开关
            shortcutsSelectSegmentedButtonForStartup = ctk.CTkSegmentedButton(
                actionFrame,
                values=["启用", "禁用"],

                command=lambda value, shortcutId=item.get("id"): self.changeShortcutEnabled(shortcutId, value)
            )
            shortcutsSelectSegmentedButtonForStartup.pack(side="right", padx=5)
            shortcutId = item.get("id")
            self.shortcutStartupButtons[shortcutId] = shortcutsSelectSegmentedButtonForStartup
            shortcutsSelectSegmentedButtonForStartup.set("启用" if item.get("enabled", False) else "禁用")



    @staticmethod
    def _shortcutSortKey(shortcut):
        """用于排序快捷键列表，优先按数字ID排序，其次按字符串ID排序"""
        shortcutId = shortcut.get("id", 0)
        if isinstance(shortcutId, int):
            return (0, shortcutId)
        if isinstance(shortcutId, str):
            if shortcutId.isdigit():
                return (0, int(shortcutId))
            suffix = shortcutId.rsplit("_", 1)[-1]
            if suffix.isdigit():
                return (0, int(suffix))
            return (1, shortcutId)
        return (2, str(shortcutId))

    def deleteShortcut(self, shortcutId):
        """删除单个快捷键"""
        confirm = messagebox.askyesno("确认删除", f"确定要删除快捷键 ID 为 '{shortcutId}' 的快捷键吗？此操作不可撤销。")
        if not confirm:
            return
        try:
            deleteShortcut(schemeName=self.schemeName, shortcutId=shortcutId)
            # id重新分配后，刷新整个列表
            resignShortcutIds(schemeName=self.schemeName)
            self.refreshShortcutList()
            self._refreshExecutor()
        except FileNotFoundError as e:
            messagebox.showerror("错误", f"删除快捷键失败: {e}, 请确保方案的配置文件存在和完整。")

    def copyShortcut(self, shortcutId):
        """复制单个快捷键"""
        shortcut = getShortcutByShortcutId(self.schemeName, shortcutId)
        if not shortcut:
            messagebox.showerror("错误", f"未找到快捷键 ID {shortcutId} 的配置。")
            return
        newName = f"{shortcut.get('name', '')}_副本"
        try:
            copyShortcut(self.schemeName,oldShortcutId=shortcutId, newShortcutName=newName)
            resignShortcutIds(schemeName=self.schemeName)
            self.refreshShortcutList()
            self._refreshExecutor()
        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def _refreshExecutor(self):
        if self.onExecutorRefresh:
            self.onExecutorRefresh()

    def editShortcut(self, shortcutId):
        """编辑单个快捷键"""
        self.openEditShortcutWindow(shortcutId)
        pass

    def openEditShortcutWindow(self, shortcutId):
        """打开编辑快捷键的窗口"""
        shortcut = getShortcutByShortcutId(self.schemeName, shortcutId)
        if not shortcut:
            messagebox.showerror("错误", f"未找到快捷键 ID {shortcutId} 的配置。")
            return
        editWindow = ShortcutEditWindow(self, shortcut)
        editWindow.grab_set()
        self.wait_window(editWindow)

        # 窗口关闭后，检查是否点了保存
        if editWindow.saved:
            try:
                from core.configManager import saveShortcutEdit
                saveShortcutEdit(self.schemeName, shortcutId, shortcut)
                self.refreshShortcutList()
                self._refreshExecutor()
            except (FileNotFoundError, ValueError) as e:
                messagebox.showerror("错误", f"保存快捷键失败: {e}")

    # 在 NewShortcutSchemePage.py 的 changeConflictDetectionMode 方法中
    def changeConflictDetectionMode(self, schemeName, mode):
        """改变冲突检测模式"""
        try:
            from core.configManager import changeShortcutSchemeConfig_conflictDetectionMode
            changeShortcutSchemeConfig_conflictDetectionMode(schemeName, mode)
            self._refreshExecutor()  # 通知主窗口重新全盘检测
        except (FileNotFoundError, ValueError) as e:
            messagebox.showerror("错误", f"修改冲突检测模式失败: {e}")

    def render_conflict_report(self, report):
        """根据主窗口传来的冲突报告，使用 Tag 混排渲染 Textbox"""
        if not hasattr(self, 'conflictResultTextbox'):
            return

        tb = self.conflictResultTextbox
        # 配置颜色 Tag
        tb.tag_config("red_tag", foreground="#FF0000")
        tb.tag_config("orange_tag", foreground="#FFA500")
        tb.tag_config("green_tag", foreground="#008000")

        # 解锁文本框进行编辑
        tb.configure(state="normal")
        tb.delete("1.0", "end")

        mode = report.get("mode", "关闭")
        is_enabled = report.get("startupEnabled", False)

        if mode == "关闭":
            # 通过分段按钮判断当前方案是否启用

            if is_enabled:
                tb.insert("end", "⚠️ 方案已启用但冲突检测处于关闭状态\n", "orange_tag")
            else:
                tb.insert("end", "冲突检测已关闭\n")
        elif mode == "当前启用的方案与此方案":
            # 【新增】当没有任何其他已启用方案时给出提醒
            if report.get("no_other_enabled_scheme", False):
                tb.insert("end", "⚠️ 当前没有任何其他已启用的方案，此模式将只检测此方案内部的冲突\n", "orange_tag")
                # 原有逻辑：当选择此模式且方案已启用时显示警告
            elif is_enabled:
                tb.insert("end", "⚠️ 当前已启用方案为此方案，此模式将只检测此方案内部的冲突\n", "orange_tag")

                # 继续处理冲突检测
            has_internal = report.get("has_internal", False)
            has_cross = report.get("has_cross", False)

            # 1. 渲染内部冲突
            if has_internal:
                tb.insert("end", "🔴 发现内部冲突:\n", "red_tag")
                for key, ids in report.get("internal_conflicts", {}).items():
                    tb.insert("end", f" 按键 {key} 被以下 ID 共用: {ids}\n", "red_tag")

            # 2. 渲染跨方案冲突
            if has_cross:
                if has_internal:
                    tb.insert("end", "\n")  # 如果有内部冲突，加个空行隔开
                tb.insert("end", "🟠 发现跨方案冲突:\n", "orange_tag")
                for item in report.get("cross_conflicts", []):
                    tb.insert("end",
                              f" 本方案 ID {item['my_id']} 与方案 '{item['other_scheme']}' 的 ID {item['other_id']} 冲突 ({item['key']})\n",
                              "orange_tag")

            # 3. 无冲突
            if not has_internal and not has_cross:
                tb.insert("end", "✅ 未检测到冲突\n", "green_tag")
        else:
            # 其他模式的处理保持不变
            has_internal = report.get("has_internal", False)
            has_cross = report.get("has_cross", False)

            # 1. 渲染内部冲突
            if has_internal:
                tb.insert("end", "🔴 发现内部冲突:\n", "red_tag")
                for key, ids in report.get("internal_conflicts", {}).items():
                    tb.insert("end", f" 按键 {key} 被以下 ID 共用: {ids}\n", "red_tag")

            # 2. 渲染跨方案冲突
            if has_cross:
                if has_internal:
                    tb.insert("end", "\n")  # 如果有内部冲突，加个空行隔开
                tb.insert("end", "🟠 发现跨方案冲突:\n", "orange_tag")
                for item in report.get("cross_conflicts", []):
                    tb.insert("end",
                              f" 本方案 ID {item['my_id']} 与方案 '{item['other_scheme']}' 的 ID {item['other_id']} 冲突 ({item['key']})\n",
                              "orange_tag")

            # 3. 无冲突
            if not has_internal and not has_cross:
                tb.insert("end", "✅ 未检测到冲突\n", "green_tag")

        # 重新锁定文本框
        tb.configure(state="disabled")

    def enableAllShortcuts(self):
        """启用当前方案的所有快捷键"""
        self._setAllShortcutsStatus(True)

    def disableAllShortcuts(self):
        """禁用当前方案的所有快捷键"""
        self._setAllShortcutsStatus(False)

    def _setAllShortcutsStatus(self, status):
        """统一修改所有快捷键的启用状态（内部方法）"""
        try:
            from core.configManager import saveShortcutSchemeConfig
            # 1. 获取一次配置
            config = getShortcutSchemeConfigBySchemeName(self.schemeName)
            if config is None:
                raise FileNotFoundError(f"找不到方案 '{self.schemeName}' 的配置文件")
            # 2. 在内存中批量修改状态
            for shortcut in config.get("shortcuts", []):
                shortcut["enabled"] = status
            # 3. 一次性保存回 JSON 文件
            saveShortcutSchemeConfig(config, self.schemeName)
            # 4. 刷新整个列表 UI（重建所有快捷键行）
            self.refreshShortcutList()
            # 5. 只触发一次执行器刷新和全局冲突检测
            self._refreshExecutor()

        except (FileNotFoundError, ValueError) as e:
            messagebox.showerror("错误", f"批量修改快捷键状态失败: {e}")

    def deleteAllShortcuts(self):
        """删除当前方案的所有快捷键,这个只有一次提示"""
        confirm = messagebox.askyesno(
            "确认清空",
            f"确定要清空方案 '{self.schemeName}' 中的所有快捷键吗？此操作不可撤销。"
        )
        if not confirm:
            return
        try:
            from core.configManager import saveShortcutSchemeConfig

            # 获取当前方案配置
            config = getShortcutSchemeConfigBySchemeName(self.schemeName)
            if config is None:
                raise FileNotFoundError(f"找不到方案 '{self.schemeName}' 的配置文件")
            # 直接清空快捷键列表
            config["shortcuts"] = []
            # 保存回配置文件
            saveShortcutSchemeConfig(config, self.schemeName)
            # 刷新 UI 和执行器
            self.refreshShortcutList()
            self._refreshExecutor()

        except (FileNotFoundError, ValueError) as e:
            messagebox.showerror("错误", f"清空快捷键失败: {e}, 请确保方案的配置文件存在和完整。")

    def searchShortcuts (self):
        """搜索当前方案的快捷键"""
        #todo 参考编辑快捷键按钮，要有弹窗
        pass



