'''
主窗口
'''

import json
from tkinter import messagebox

import customtkinter as ctk

from core.configManager import globalSettingspath, configDirectory, createNewShortcutSchemeConfig, \
    saveShortcutSchemeConfig, changeShortcutSchemeConfig,loadWindowSettings, center_window
from gui.HomePages import HomePage
from gui.NewShortcutSchemePage import NewShortcutSchemePage
from gui.SettingsPage import SettingsPage
from utils.shortcutUtils import theNumberOfTargetFilesInTheFolder, getShortcutSchemes, getAllSchemesWithShortcuts, \
    analyzeConflicts, getStartupEnabledShortcutScheme

import threading

# print(f"当前快捷键方案数量: {CurrentNumberOfShortcutKeySchemes}")
# 打开本地全局设置json文件
with open(globalSettingspath, "r", encoding="utf-8") as f:
    globalSettings = json.load(f)
# 读取外观模式配置
appearanceMode = globalSettings["appearanceMode"]


# numberOfNavigationBarSections=4  # 导航栏分为4个部分，分别是首页、功能1、功能2、设置

class MainWindow(ctk.CTk):
    """程序主窗口类，继承自CustomTkinter的CTk主窗口"""

    def __init__(self, executor=None):
        super().__init__()
        self.executor = executor

        self.conflict_reports_cache = {}

        # ==================== 34 号修改：is_listening_paused 改为只读 property ==
        # 原实例属性 self.is_listening_paused = False 一行【必须删除】：
        #   1) 实例属性会遮蔽类级 property 使其失效；
        #   2) property 无 setter，若保留这行赋值会直接 AttributeError。
        # 暂停标志的真相源下沉为 executor.isPaused（见 core/executor.py），
        # 本类的 is_listening_paused 改为只读 property 委托读取——托盘
        # （trayIcon.py）与设置页（SettingsPage.py）现有的
        # getattr(xxx, 'is_listening_paused', False) 读取点零改动、语义不变。
        # ======================================================================
        # 新增：持有托盘引用
        self.tray_icon = None
        # ==================== 34 号新增：托盘状态签名轮询状态位 =================
        # _lastStatusSignature：上一次推送时的状态签名（None = 从未推送，
        # 首拍必推送一次，把托盘菜单/图标从"启动时构建的旧快照"纠到当前真值）。
        self._lastStatusSignature = None
        self._pollStatusAfterId = None
        
        # 新增：持有托盘引用
        self.tray_icon = None

        # 新增：拦截窗口关闭事件，改为隐藏
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.title("自定义快捷键工具")
        # 固定主窗口的最小尺寸，防止用户在设置里填了过小的值导致 UI 崩溃
        self.minsize(1000, 800)

        # 读取全局配置，决定主窗口的初始大小和状态
        win_settings = loadWindowSettings().get("mainWindow", {})
        is_maximized = win_settings.get("maximized", True)
        win_width = win_settings.get("width", 1000)
        win_height = win_settings.get("height", 800)

        if is_maximized:
            # 延迟100ms最大化，避免在某些系统上启动时被覆盖
            self.after(100, lambda: self.state("zoomed"))
        else:
            # 调用居中工具函数，按用户配置的宽高显示在屏幕中央
            center_window(self, win_width, win_height)

        self._set_appearance_mode(appearanceMode)  # 可选: "light", "dark", "system"

        self.after(100, self.refresh_all_conflict_status)

        # 在这里添加窗口内容

        # 主布局：分为左右两列。使用grid布局管理器，左侧为导航栏，右侧为内容区，index=0表示左侧导航栏，index=1表示右侧内容区

        self.numberOfNavigationBarItems = theNumberOfTargetFilesInTheFolder(
            configDirectory) + 2  # 2表示除了快捷键方案之外，还有首页和设置两个固定导航项

        # index的含义：grid布局管理器中，row表示行，column表示列，index表示索引，从0开始计数。row=0表示第一行，column=0表示第一列，row=1表示第二行，column=1表示第二列，以此类推。

        self.grid_columnconfigure(0,
                                  weight=0)  # 左侧导航栏固定宽度.完整解释：grid_columnconfigure方法用于配置网格列的权重。权重为0表示该列不会随着窗口大小变化而伸缩，而权重为1表示该列会根据窗口大小变化而伸缩。
        self.grid_rowconfigure(0, weight=1)  # 行可伸缩
        # 左侧导航栏（垂直菜单）
        self.nav_frame = ctk.CTkScrollableFrame(self, width=160, fg_color="#303030")  # 定义导航栏框架，设置宽度和背景颜色
        '''
        改width的值，导航栏宽度没有变化的原因：
        你使用的是 grid 布局，在 grid 布局中，CTkFrame 的 width 参数会被忽略，
        因为 grid 会根据子组件的内容自动计算列宽，而不是根据你设定的 width 值。
        你的导航栏里只有按钮和 padx=20 的间距，所以实际宽度远小于 400。
        解决方法： 在 nav_frame 上调用 grid_propagate(False)，阻止子组件反向决定 frame 的尺寸，这样 width=400 才会生效
        '''
        # 将导航栏放置在左侧，填充整个高度（sticky="ns"表示上下填充），row=0表示第一行，column=0表示第一列。这句代码的作用是将导航栏放置在主窗口的左侧，并且填充整个高度，使其看起来像一个垂直菜单栏。
        self.nav_frame.grid(row=0, column=0, sticky="ns")
        # 导航栏的第 首页加设置加已有两项快捷键方案加1 行（当前index=4）可以伸缩，从而将按钮推到顶部

        """
        导航栏换成可滚动的了
        CTkScrollableFrame 本身是一个可滚动的容器，它会根据内部内容的高度自动调整显示区域，并显示滚动条。
        原来的弹簧行（weight=1）是为了让“+新建”按钮始终在导航栏底部，
        但换成滚动容器后，这个弹簧会被滚动逻辑覆盖，导致“+新建”按钮的位置可能不再固定在最底部。
        """
        # self.nav_frame.grid_rowconfigure(self.numberOfNavigationBarItems, weight=1)

        self.grid_columnconfigure(1, weight=1)  # 右侧内容区可伸缩

        # 导航栏内部布局：依次垂直排列按钮
        # navItems = ["首页", "设置","测试页面", "新建页面"]
        navItems = ["首页", "设置"]
        self.navButtons = {}  # 存储按钮对象，方便后续高亮

        for i, item in enumerate(navItems):
            # i,item分别表示索引和导航项名称
            # 创建按钮，绑定切换页面的函数
            btn = ctk.CTkButton(
                self.nav_frame,
                text=item,
                command=lambda name=item: self.showPage(name),
                fg_color="transparent",  # 默认透明背景
                hover_color="#3a3a3a",  # 悬停时背景色
                text_color="white",  # 文字颜色
                font=("微软雅黑", 20),
                height=40

            )
            btn.grid(row=i, column=0, pady=2, padx=10,
                     sticky="ew")  # 填满宽度,各属性分别表示：row=i表示按钮所在行，column=0表示按钮所在列，pady=10表示上下间距为10像素，padx=20表示左右间距为20像素，sticky="ew"表示按钮在水平方向上填满整个单元格。
            self.navButtons[item] = btn  # 存储按钮对象

        # 右侧内容区父容器
        self.contentFrame = ctk.CTkFrame(self, fg_color="transparent")  # 定义内容区框架，设置背景颜色为透明
        self.contentFrame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)  # 将内容区放置在右侧，填充整个高度和宽度，并设置内边距为10像素
        self.contentFrame.grid_rowconfigure(0, weight=1)  # 让内容区垂直可伸缩
        self.contentFrame.grid_columnconfigure(0, weight=1)  # 让内容区水平可伸缩
        self.pages = {}
        self.pages["首页"] = HomePage(self.contentFrame, fg_color="transparent" )
        # 创建一个首页对象，并存储在self.pages字典中，键为"首页"，值为HomePage对象。第一个参数self.contentFrame表示将页面放置在内容区父容器中，第二个参数fg_color="transparent"表示设置页面背景颜色为透明。
        # ==================== 32 号新增：注入自身引用 ====================
        # 设置页"软件控制与状态"区需要调用本窗口控制方法并读取
        # is_listening_paused 标志。
        self.pages["设置"] = SettingsPage(self.contentFrame, fg_color="transparent", main_window=self)

        self.showPage("首页")  # 默认显示首页

        self.createNavigationBarItemsBasedOnShortcutKeyScheme(getShortcutSchemes(configDirectory))

        # 新增：底部“新建方案”按钮
        # 放在第6行 (index=5)，因为它上面的 row=4 是 weight=1 的弹簧，所以它会被推到最下面
        self.addProfileBtn = ctk.CTkButton(
            self.nav_frame,
            text="+ 新建快捷键方案",
            command=self.openAddProfileDialog,  # 绑定点击事件
            fg_color="transparent",  # 透明背景，让它看起来像辅助功能
            hover_color="#3a3a3a",
            text_color="white",
            border_width=1,  # 加个边框突出“新建”动作
            # border_color="#555555",  # 边框颜色
            font=("微软雅黑", 16),
            height=40
        )
        self.addProfileBtn.grid(row=2, column=0, pady=(10, 20), padx=10, sticky="ew")

        # 新增：向执行器注入跨线程回调 —— 注意三行必须在同一个守卫块内，
        # 漏掉任何一个都会造成该通道静默降级（本项目已经踩过一次坑）
        if self.executor:
            self.executor.setConfirmCallback(self.show_confirm_dialog)
            self.executor.setAppControlCallback(self._app_control_callback)
            # ★ Bug 修复：此前一直缺失的 tip 注入。生效后所有依赖 showTip 的
            #   错误路径（含新的动作组执行报告）从 print 虚空变为真正可见。
            self.executor.setTipCallback(self.showExecutorTip)

        # 500ms after 轮询（见 _pollStatus）。放主窗口而非设置页：页面可能
        # 未显示（grid_forget）甚至 --minimized 启动，MainWindow 级轮询
        # 全场景存活。回调本体 widget-free（只读 executor + 托盘），异常
        # 全兜底，窗口销毁竞态下最坏是静默空转；mainloop 退出即自然消亡，
        # quit_app 里另有显式取消（同 SettingsPage.destroy 的纪律）。
        self._startStatusPolling()

    # 切换页面函数，参数name表示要显示的页面名称。思路是隐藏所有页面，然后显示选中的页面，并高亮当前选中的导航按钮。
    def showPage(self, name):
        # 隐藏所有页面
        for pageName, page in self.pages.items():
            page.grid_forget()

        # 恢复所有导航按钮的默认样式
        for btnName, btn in self.navButtons.items():
            btn.configure(fg_color="transparent")

        # 显示选中的页面
        self.pages[name].grid(row=0, column=0, sticky="nsew")
        # 高亮当前选中的导航按钮
        self.navButtons[name].configure(fg_color="#3a3a3a")

        # ★ 新增：如果是方案页面，把缓存里最新的冲突报告喂给它 ★
        if isinstance(self.pages[name], NewShortcutSchemePage):
            report = self.conflict_reports_cache.get(name)
            if report:
                # 调用页面的渲染方法 (第四步会去 NewShortcutSchemePage 里实现这个方法)
                self.pages[name].render_conflict_report(report)

    def createNewShortcutSchemePage(self, schemeName):
        newPage = NewShortcutSchemePage(
            self.contentFrame,
            fg_color="transparent",
            schemeName=schemeName,
            onCopied=self.handleSchemeCopied,
            ondeleted=self.handleSchemeDeleted,
            onRenamed=self.handleSchemeRenamed,
            onStartupChanged=self.handleSchemeStartupChanged,
            onExecutorRefresh=self.refreshExecutor,
            executor=self.executor,
        )
        self.pages[schemeName] = newPage

    def openAddProfileDialog(self):
        dialog = ctk.CTkInputDialog(text="请输入新的快捷键方案名称:", title="新建方案")
        newName = dialog.get_input()  # ← 只调用一次，存起来
        if newName is None or newName.strip() == "":  # ← 用变量判断
            return
        try:
            newConfig = createNewShortcutSchemeConfig(newName)
            saveShortcutSchemeConfig(newConfig, newName)
            self.refreshSchemeButtons()
            self.refreshExecutor()
            self.showPage(newName)
        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def createNavigationBarItemsBasedOnShortcutKeyScheme(self, schemes):
        """根据快捷键方案列表创建导航栏按钮和对应页面"""
        schemes = sorted(schemes, key=lambda x: x["name"])
        for i, scheme in enumerate(schemes):
            schemeName = scheme["name"]

            # 创建自定义按钮容器（Frame）
            btn_frame = ctk.CTkFrame(
                self.nav_frame,
                fg_color="transparent",
                height=40,
                corner_radius=5,
                border_width=1,
            )
            btn_frame.grid(row=3 + i, column=0, pady=2, padx=10, sticky="ew")
            btn_frame.grid_columnconfigure(0, weight=1)

            # 添加文本标签（支持换行）
            label = ctk.CTkLabel(
                btn_frame,
                text=schemeName,
                font=("微软雅黑", 16),
                wraplength=130,
                text_color="white",

                anchor="w"
            )
            label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
            label.bind("<Button-1>", lambda e, name=schemeName: self.showPage(name))

            # 绑定点击事件（模拟按钮点击）
            btn_frame.bind("<Button-1>", lambda e, name=schemeName: self.showPage(name))
            # 存储标签对象（用于高亮）
            # ★ 新增：存储 label 引用，方便后续改颜色 ★
            if not hasattr(self, 'navLabels'):
                self.navLabels = {}

            self.navLabels[schemeName] = label
            # 存储按钮对象（用于高亮）
            self.navButtons[schemeName] = btn_frame

            # ★ 补上这一行：创建对应的方案页面 ★
            self.createNewShortcutSchemePage(schemeName)

    def refreshSchemeButtons(self):
        """刷新方案导航按钮（删除旧的，重新创建）"""
        # 1. 记录旧的弹簧行
        # oldSpringRow = self.numberOfNavigationBarItems
        # 2. 删除旧的方案按钮和页面（保留首页、设置）
        fixedButtons = ["首页", "设置"]
        keysToDelete = [k for k in list(self.navButtons.keys()) if k not in fixedButtons]
        # 使用列表推导式创建了一个新的列表 keysToDelete，
        # 其中包含了 self.navButtons 字典中所有键（按钮名称），但排除了固定按钮 "首页" 和 "设置"。
        # 具体来说，list(self.navButtons.keys()) 会返回 self.navButtons 字典中所有键的列表，
        # 然后通过 if k not in fixedButtons 条件过滤掉固定按钮，最终得到需要删除的按钮名称列表。
        for key in keysToDelete:
            self.navButtons[key].destroy()  # 销毁旧按钮
            del self.navButtons[key]
            if key in self.pages:
                self.pages[key].destroy()  # 销毁旧页面
                del self.pages[key]
        # 3. 重置旧弹簧行权重
        # self.nav_frame.grid_rowconfigure(oldSpringRow,weight=0)  # grid_rowconfigure方法用于配置网格行的权重。这里将旧弹簧行的权重设置为0，表示该行不会随着窗口大小变化而伸缩，从而避免布局问题。
        # 4. 重新计算
        self.numberOfNavigationBarItems = theNumberOfTargetFilesInTheFolder(configDirectory) + 2
        # 5. 设置新弹簧行
        # self.nav_frame.grid_rowconfigure(self.numberOfNavigationBarItems, weight=1)
        # 6. 移动"+ 新建"按钮到新位置
        self.addProfileBtn.grid(row=2, column=0, pady=(10, 20), padx=10, sticky="ew")
        # 7. 重新创建方案按钮和页面
        self.createNavigationBarItemsBasedOnShortcutKeyScheme(getShortcutSchemes(configDirectory))

    def handleSchemeRenamed(self, oldName, newName):  # 多出的参数删了就报错
        """改名成功后由子页面回调：刷新导航栏 + 跳转到新页面"""
        self.refreshSchemeButtons()  # 重建所有方案按钮和页面
        self.refreshExecutor()
        self.showPage(newName)  # 跳转到改名后的页面

    def handleSchemeStartupChanged(self):
        """某个方案切换了启用状态后，刷新所有方案页面的状态显示"""
        for name, page in self.pages.items():
            # 只刷新 NewShortcutSchemePage 类型的页面
            if isinstance(page, NewShortcutSchemePage):
                page.refreshSchemeStartupDisplay()
        self.refreshExecutor()

    def handleSchemeCopied(self, oldSchemeName, newSchemeName, ):  # 多出的参数删了就报错
        """复制成功后由子页面回调：刷新导航栏 + 跳转到新页面"""
        self.refreshSchemeButtons()  # 重建所有方案按钮和页面
        self.refreshExecutor()
        self.showPage(oldSchemeName)  # 跳转被复制的页面

    def handleSchemeDeleted(self, deletedSchemeName):  # 多出的参数删了就报错
        """删除成功后由子页面回调：刷新导航栏 + 跳转到首页"""
        self.refreshSchemeButtons()  # 重建所有方案按钮和页面
        self.refreshExecutor()
        self.showPage("首页")  # 跳转到首页

    def refreshExecutor(self):
        # ==================== 32 号新增：双层守卫的外层 ====================
        # 内层权威防线在 executor.sync() 本体（isExecuting 早退）。本层同步
        # 早退：执行期间连全盘冲突重算也不做，保持"执行期间零全局刷新"的
        # 单一语义；执行结束后下一次任何 UI 触发都会补上（与 sync 静默跳过
        # 的既定口径一致）。
        if self.executor and self.executor.isExecuting:
            return
        # 方案或快捷键变更后，先刷新执行器再决定要不要保持监听
        if self.executor:
            self.executor.sync()
        # ★ 新增：执行全局冲突状态重算 ★
        self.refresh_all_conflict_status()

    def refresh_all_conflict_status(self):
        """读取所有方案数据，生成最新的冲突报告，存入缓存，并通知当前页面更新"""
        all_schemes_data = getAllSchemesWithShortcuts(configDirectory)
        self.conflict_reports_cache = {}

        for scheme in all_schemes_data:
            scheme_name = scheme["name"]
            mode = scheme.get("conflictDetectionMode", "关闭")
            is_enabled = scheme.get("startupEnabled", False)

            report = analyzeConflicts(scheme_name, mode, all_schemes_data)
            report["startupEnabled"] = is_enabled  # 补充状态给 UI 决策用
            self.conflict_reports_cache[scheme_name] = report

            # 更新左侧导航栏 Label 颜色
            self.update_navbar_color(scheme_name, report)

        # 更新当前打开的页面
        for name, page in self.pages.items():
            if isinstance(page, NewShortcutSchemePage) and page.winfo_ismapped():
                report = self.conflict_reports_cache.get(name)
                if report:
                    page.render_conflict_report(report)
                break

    # 在 MainWindow.py 的 update_navbar_color 方法中
    def update_navbar_color(self, scheme_name, report):
        """根据冲突报告和优先级规则，更新导航栏 Label 的文字颜色"""
        label = getattr(self, 'navLabels', {}).get(scheme_name)
        if not label:
            return

        is_enabled = report.get("startupEnabled", False)
        mode = report.get("mode", "关闭")
        has_internal = report.get("has_internal", False)
        has_cross = report.get("has_cross", False)
        # ==================== 31/33 号新增：保留组合冲突，优先级最高 ==========
        # 硬失效事实（保存了也永不触发），与内部冲突同用红色但排最前，
        # 让手改 JSON 的人第一眼看见。
        has_reserved = report.get("has_reserved", False)
        # ===================================================================
        color = "white"  # 默认白色
        if has_reserved:
            color = "#FF0000"  # 红色：与软件保留停止组合冲突（永不触发）
        elif has_internal:
            color = "#FF0000"  # 红色：内部冲突
        elif has_cross:
            color = "#FFA500"  # 橙色：跨方案冲突
        # 然后检查已启用但检测关闭的警告
        elif mode == "关闭" and is_enabled:
            color = "#FFA500"  # 橙色：已启用但未开检测
        # 最后检查健康状态
        elif is_enabled:
            color = "#008000"  # 绿色：健康

        label.configure(text_color=color)

    def showExecutorTip(self, title, text):
        """给执行器用的提示窗口回调。"""
        self.after(0, lambda: messagebox.showinfo(title, text))


    def show_confirm_dialog(self, message: str, result_holder: list, event: threading.Event):
        """
        供子线程调用的确认弹窗。
        通过 self.after(0, ...) 将弹窗操作抛回 Tkinter 主线程执行，
        弹窗结束后将结果存入 result_holder 并唤醒子线程。
        """
        def _ask():
            # 在主线程中弹出确认框
            result = messagebox.askyesno("执行确认", message)
            # 将结果存入可变容器
            result_holder[0] = result
            # 唤醒阻塞的子线程
            event.set()

        # 抛回主线程执行
        self.after(0, _ask)

    def soft_stop_action_group(self):
        """供托盘调用的平滑停止动作组功能"""
        if self.executor and self.executor.is_busy:
            # 检查是否已经发送过软停止信号，防止重复发送
            if self.executor.action_group_soft_stop_event.is_set():
                messagebox.showinfo("提示", "已经发送过平滑停止信号了，请耐心等待当前步骤完成。")
            else:
                self.executor.action_group_soft_stop_event.set()
                messagebox.showinfo("提示", "已发送平滑停止信号，动作组将在当前步骤完成后自动停止。")
        else:
            messagebox.showinfo("提示", "当前没有正在执行的动作组。")

    def _app_control_callback(self, command: str, target_scheme: str = ""):
        """ 供子线程调用的软件控制回调。 这是一个“桥梁”方法，接收到子线程的指令后，
        立刻通过 self.after(0, ...) 将实际工作抛回 Tkinter 主线程的事件队列中排队执行，保证线程安全。
        """
        # ==================== 修改：传递 target_scheme ====================
        self.after(0, lambda: self._handle_app_control(command, target_scheme))
        # =================================================================

    def _handle_app_control(self, command: str, target_scheme: str = ""):
        """
        [仅在主线程执行] 实际处理各项软件控制指令。
        Tkinter 的 after 机制保证了此方法内部的代码是串行执行的，无需额外加锁。
        """
        if command == "显示主窗口":
            self.show_window()
        elif command == "隐藏主窗口":
            self.hide_window()
        elif command == "刷新执行器":
            # 相当于触发了全局联动刷新
            self.refreshExecutor()
        elif command == "退出软件":
            self.quit_app()
        elif command in ("切换到上一个方案", "切换到下一个方案"):
            # 1. 获取所有方案，按名字字母排序（与左侧导航栏顺序一致）
            all_schemes = getShortcutSchemes(configDirectory)
            if not all_schemes:
                return  # 没有任何方案，无法切换

            sorted_schemes = sorted(all_schemes, key=lambda x: x["name"])
            names_list = [s["name"] for s in sorted_schemes]

            # 2. 找到当前启用的方案
            current_enabled = getStartupEnabledShortcutScheme(configDirectory)
            current_name = current_enabled["name"] if current_enabled else None

            # 3. 计算目标方案的索引
            if current_name not in names_list:
                # 当前没有启用方案，或者方案名不在列表中，默认切到第一个
                target_index = 0
            else:
                current_index = names_list.index(current_name)
                if command == "切换到上一个方案":
                    target_index = (current_index - 1) % len(names_list)
                else:  # 切换到下一个方案
                    target_index = (current_index + 1) % len(names_list)

            target_name = names_list[target_index]

            # 4. 复用托盘切换方案的方法：互斥修改配置并刷新UI和执行器
            self.switch_scheme_from_tray(target_name)

        # ==================== 设计25修改：支持通过空字符串禁用所有方案 ====================
        elif command == "启用指定方案":
            # 如果 target_scheme 为空字符串，代表用户在下拉框选择了"（无）"，即禁用所有方案
            # switch_scheme_from_tray(None) 会互斥地禁用所有方案
            scheme_to_enable = target_scheme if target_scheme else None
            self.switch_scheme_from_tray(scheme_to_enable)
        # =====================================================================

    # ==================== 34 号新增：is_listening_paused 只读 property =========
    @property
    def is_listening_paused(self):
        """监听暂停标志（只读）。

        真相源是 executor.isPaused；本 property 仅是委托转发，保持
        MainWindow.is_listening_paused 这个既有读取口径不变（托盘与设置页
        均以 getattr(main_window, 'is_listening_paused', False) 方式读取，
        property 与 getattr 完全兼容）。executor 为 None（理论上仅存在于
        极早期窗口构建瞬间）时退化为 False。
        """
        if self.executor is None:
            return False
        return bool(getattr(self.executor, 'isPaused', False))
    # ==========================================================================

    # ==================== 34 号新增：托盘状态签名轮询 ===========================
    def _startStatusPolling(self):
        """启动 500ms 状态轮询（首拍 500ms 后触发）。"""
        self._pollStatusAfterId = self.after(500, self._pollStatus)

    def _pollStatus(self):
        """轮询回调：签名变了才推送托盘（图标 + 菜单），然后续下一拍。

        为什么"变化才推"而不是每次都推：
          - pystray update_menu() 是 HMENU 销毁重建 + NIM_MODIFY，有真实开销；
          - 更重要的是把推送语义收敛到一个判据——未来任何新增的状态变化点
            只要纳入签名元组就自动被覆盖，不会出现"某条路径忘了推送"的
            新坑（本 bug 的教训）。

        为什么轮询而不是在状态翻转处直调托盘：
          - is_busy 的翻转发生在 executor 执行子线程，从那里碰 pystray
            违反"托盘操作收口主线程"的既定纪律；
          - after 轮询天然把所有线程的状态变化收口到主线程统一观察。

        签名字段取舍（新增状态时在此扩元组即可）：
          - isPaused / isListening：状态行"监听"文案 + 图标变灰；
          - is_busy：状态行"执行"文案 + 停止项显隐 + 退出项置灰；
          - 方案名：状态行"监听中 · 方案: X"；
          - soft_stop_event.is_set()：托盘"平滑停止"项的 visible 条件
            （发过一次软停信号后该项隐藏）。
        """
        try:
            sig = self._computeStatusSignature()
            if sig != self._lastStatusSignature:
                self._lastStatusSignature = sig
                self._pushTrayUpdate()
        except Exception:
            # 轮询永不因单拍异常中断；widget-free + 全兜底，销毁竞态下静默空转
            pass
        finally:
            try:
                self._pollStatusAfterId = self.after(500, self._pollStatus)
            except Exception:
                # 窗口已销毁（退出流程）：不再续拍，轮询自然终止
                pass

    def _computeStatusSignature(self):
        """从 executor 读出当前状态签名（纯只读，GIL 下各字段读取原子）。"""
        executor = self.executor
        if executor is None:
            return (False, False, False, None, False)
        soft_set = False
        try:
            soft_set = executor.action_group_soft_stop_event.is_set()
        except Exception:
            pass
        scheme = executor.getActiveSchemeInfo()
        scheme_name = scheme.get("name") if scheme else None
        return (
            bool(getattr(executor, 'isPaused', False)),
            bool(getattr(executor, 'isListening', False)),
            bool(getattr(executor, 'is_busy', False)),
            scheme_name,
            soft_set,
        )

    def _pushTrayUpdate(self):
        """把当前状态立即推给托盘（图标 + 菜单）。仅主线程调用。"""
        if self.tray_icon is None:
            return
        try:
            self.tray_icon.refresh_visual_state()
        except Exception as e:
            print(f"[托盘] 状态推送失败: {e}")
    # ==========================================================================


    def set_tray_icon(self, tray_icon):
        """绑定托盘管理器实例"""
        self.tray_icon = tray_icon

    def hide_window(self):
        """隐藏窗口而不是销毁"""
        self.withdraw()

    def show_window(self):
        """安全地显示并激活窗口"""
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app(self):
        """彻底退出程序的通道"""
        # ==================== 32 号新增：忙碌守卫（与托盘对齐）============
        # 托盘"退出程序"菜单项 enabled=lambda: not is_busy；本方法层守卫让
        # 设置页按钮与 appControlSafe 的"退出软件"指令获得同款保护：动作组
        # 执行中退出 = 监听器销毁 = 停止组合陪葬，且正劫持鼠标的动作组被腰斩。
        if self.executor and self.executor.is_busy:
            messagebox.showwarning(
                "繁忙",
                "动作组正在执行中，无法退出软件！\n请先用停止组合 / 托盘 / 设置页停止动作组。",
            )
            return
        # ==================== 34 号新增：停掉托盘状态签名轮询 ==================
        # 回调本体 widget-free、异常全兜底，理论上留着也无害（mainloop 退出
        # 即亡），但显式取消更干净——与 SettingsPage.destroy 的 after_cancel
        # 同款纪律，不依赖防御。
        if getattr(self, '_pollStatusAfterId', None) is not None:
            try:
                self.after_cancel(self._pollStatusAfterId)
            except Exception:
                pass
            self._pollStatusAfterId = None
        # ======================================================================

        # ==================================================================
        # 1. 停止执行器和监听器
        # ……以下原样不动……

        if self.executor:
            self.executor.stop()
        # 2. 停止托盘图标
        if self.tray_icon:
            self.tray_icon.icon.stop()
        # 3. 销毁主窗口
        self.destroy()

    def switch_scheme_from_tray(self, target_scheme_name):
        """
        供托盘调用的方案切换逻辑。
        参数 target_scheme_name:
            - 如果是具体方案名，则启用该方案，并互斥禁用其他所有方案。
            - 如果是 None，则禁用所有方案。
        """
        # 拦截动作组执行期间的切换操作
        if self.executor and self.executor.is_busy:
            messagebox.showwarning("繁忙", "动作组正在执行中，无法切换方案！\n请等待执行完毕或使用“强制停止动作组”。")
            return
        # 1. 读取所有方案，互斥修改配置
        all_schemes = getShortcutSchemes(configDirectory)
        for scheme in all_schemes:
            name = scheme["name"]
            if name == target_scheme_name:
                # 目标方案：如果未启用，则启用
                if not scheme["startupEnabled"]:
                    changeShortcutSchemeConfig(schemeName=name, newStartupEnabled=True)
            else:
                # 非目标方案：如果已启用，则禁用
                if scheme["startupEnabled"]:
                    changeShortcutSchemeConfig(schemeName=name, newStartupEnabled=False)

        # 2. 触发全局联动刷新
        # handleSchemeStartupChanged 内部已经调用了 refreshExecutor()
        # 而 refreshExecutor() 内部又调用了 refresh_all_conflict_status()
        # 所以一行代码，配置写入、执行器重载、UI状态刷新、冲突重算全搞定了
        self.handleSchemeStartupChanged()
        # 方案切换改变签名中的"当前方案名"（状态行文案）与可能的 isListening；
        # handleSchemeStartupChanged → refreshExecutor → executor.sync() 已在
        # 本调用栈内同步完成，此处标志必为新值，直接推送即可。
        self._pushTrayUpdate()

    def toggle_listening_status(self):
        """切换全局键盘监听状态（供托盘 / 设置页调用）"""
        # ==================== 31/32 号新增：忙碌守卫（逃生口保全）==========
        # 动作组执行中暂停监听 = 销毁 listener = 停止组合陪葬，软件失去唯一
        # 的键盘逃生口（此时鼠标已被劫持，托盘和 GUI 都点不到）。与"忙碌
        # 禁暂停"互为因果：守卫在 ⇔ 逃生口在 —— 此逻辑链不可拆除。托盘菜单
        # 项未置灰是故意的，方法层守卫天然覆盖全部入口。
        if self.executor and self.executor.is_busy:
            messagebox.showwarning(
                "繁忙",
                "动作组正在执行中，无法暂停监听！\n"
                "监听器是停止组合（键盘急停）的唯一载体，暂停后将失去唯一的键盘逃生口。\n"
                "请先用停止组合或托盘停止动作组。",
            )
            return
        # ==================================================================
        if self.is_listening_paused:
            # 当前是暂停状态，需要恢复。
            # 34 号：原 executor.restart() 直调改为 resume() —— isPaused 复位
            # 收口进 executor，本方法不再手工维护标志（property 只读，写不了
            # 也不需要写了）；无启用方案时 resume 内部会弹提示。
            if self.executor:
                self.executor.resume()
        else:
            # 当前是正常状态，需要暂停（pause = stop + 立意图标志）
            if self.executor:
                self.executor.pause()

        # ==================== 34 号新增：直推托盘 ==============================
        # 此处标志已翻转（pause/resume 同步改 executor 字段），立即推送一次，
        # 保证"点完立即再展开托盘"显示的就是新状态；兜底的 ≤500ms 轮询拍
        # 会因签名比对相同而跳过，不重复推。Bug#34 的"滞后一拍"由此根治。
        self._pushTrayUpdate()
        # ======================================================================

    def force_stop_action_group(self):
        """供托盘 / 设置页调用的强制停止动作组功能"""
        if self.executor and self.executor.is_busy:
            self.executor.action_group_interrupt_event.set()
            # 文案修订（31 号）：硬停在最近的检查点（延迟分片/鼠标插值步）
            # 立即响应，"当前步骤完成后"是平滑停止的语义，原句张冠李戴。
            messagebox.showinfo("提示", "已发送强制停止信号，动作组将在最近的检查点立即终止。")
        else:
            messagebox.showinfo("提示", "当前没有正在执行的动作组。")











