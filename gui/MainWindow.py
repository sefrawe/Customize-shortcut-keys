'''
主窗口
'''

import json
from tkinter import messagebox

import customtkinter as ctk

from core.configManager import globalSettingspath, configDirectory, createNewShortcutSchemeConfig, \
    saveShortcutSchemeConfig, changeShortcutSchemeConfig
from gui.HomePages import HomePage
from gui.NewShortcutSchemePage import NewShortcutSchemePage
from gui.SettingsPage import SettingsPage
from utils.shortcutUtils import theNumberOfTargetFilesInTheFolder, getShortcutSchemes, getAllSchemesWithShortcuts, \
    analyzeConflicts

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
        # 新增：持有托盘引用
        self.tray_icon = None

        # 新增：拦截窗口关闭事件，改为隐藏
        self.protocol("WM_DELETE_WINDOW", self.hide_window)


        # 窗口基本设置
        self.title("自定义快捷键工具")
        self.geometry("1000x800")  # 初始窗口大小

        self.minsize(1000, 800)  # 窗口最小大小

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
        self.pages["设置"] = SettingsPage(self.contentFrame, fg_color="transparent",)

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


        # 新增：向执行器注入跨线程确认弹窗回调
        if self.executor:
            self.executor.setConfirmCallback(self.show_confirm_dialog)


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

        color = "white"  # 默认白色

        # 优先级调整：先检查内部冲突（最严重）
        if has_internal:
            color = "#FF0000"  # 红色：内部冲突
        # 其次检查跨方案冲突
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
        # 1. 停止执行器和监听器
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







