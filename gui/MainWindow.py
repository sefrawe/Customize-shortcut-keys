'''
主窗口
'''

import json
from tkinter import messagebox

import customtkinter as ctk

from core.configManager import globalSettingspath, configDirectory, createNewShortcutSchemeConfig, \
    saveShortcutSchemeConfig
from gui.HomePages import HomePage
from gui.NewShortcutSchemePage import NewShortcutSchemePage
from gui.SettingsPage import SettingsPage
from utils.shortcutUtils import theNumberOfTargetFilesInTheFolder, getShortcutSchemes

# print(f"当前快捷键方案数量: {CurrentNumberOfShortcutKeySchemes}")
# 打开本地全局设置json文件
with open(globalSettingspath, "r", encoding="utf-8") as f:
    globalSettings = json.load(f)
# 读取外观模式配置
appearanceMode = globalSettings["appearanceMode"]


# numberOfNavigationBarSections=4  # 导航栏分为4个部分，分别是首页、功能1、功能2、设置

class MainWindow(ctk.CTk):
    """程序主窗口类，继承自CustomTkinter的CTk主窗口"""

    def __init__(self):
        super().__init__()

        # 窗口基本设置
        self.title("自定义快捷键工具")
        self.geometry("1000x800")  # 初始窗口大小
        self.minsize(800, 600)  # 窗口最小大小

        self._set_appearance_mode(appearanceMode)  # 可选: "light", "dark", "system"

        # 在这里添加窗口内容

        # 主布局：分为左右两列。使用grid布局管理器，左侧为导航栏，右侧为内容区，index=0表示左侧导航栏，index=1表示右侧内容区

        self.numberOfNavigationBarItems = theNumberOfTargetFilesInTheFolder(
            configDirectory) + 2  # 2表示除了快捷键方案之外，还有首页和设置两个固定导航项

        # index的含义：grid布局管理器中，row表示行，column表示列，index表示索引，从0开始计数。row=0表示第一行，column=0表示第一列，row=1表示第二行，column=1表示第二列，以此类推。

        self.grid_columnconfigure(0,weight=0)  # 左侧导航栏固定宽度.完整解释：grid_columnconfigure方法用于配置网格列的权重。权重为0表示该列不会随着窗口大小变化而伸缩，而权重为1表示该列会根据窗口大小变化而伸缩。
        self.grid_rowconfigure(0, weight=1)  # 行可伸缩
        # 左侧导航栏（垂直菜单）
        self.nav_frame = ctk.CTkFrame(self, width=150, fg_color="#303030")  # 定义导航栏框架，设置宽度和背景颜色
        '''
        改width的值，导航栏宽度没有变化的原因：
        你使用的是 grid 布局，在 grid 布局中，CTkFrame 的 width 参数会被忽略，
        因为 grid 会根据子组件的内容自动计算列宽，而不是根据你设定的 width 值。
        你的导航栏里只有按钮和 padx=20 的间距，所以实际宽度远小于 400。
        解决方法： 在 nav_frame 上调用 grid_propagate(False)，阻止子组件反向决定 frame 的尺寸，这样 width=400 才会生效
        '''
        # 将导航栏放置在左侧，填充整个高度（sticky="ns"表示上下填充），row=0表示第一行，column=0表示第一列。这句代码的作用是将导航栏放置在主窗口的左侧，并且填充整个高度，使其看起来像一个垂直菜单栏。
        self.nav_frame.grid(row=0, column=0,sticky="ns")
        # 导航栏的第 首页加设置加已有两项快捷键方案加1 行（当前index=4）可以伸缩，从而将按钮推到顶部
        self.nav_frame.grid_rowconfigure(self.numberOfNavigationBarItems,weight=1)

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
            btn.grid(row=i, column=0, pady=2, padx=10,sticky="ew")  # 填满宽度,各属性分别表示：row=i表示按钮所在行，column=0表示按钮所在列，pady=10表示上下间距为10像素，padx=20表示左右间距为20像素，sticky="ew"表示按钮在水平方向上填满整个单元格。
            self.navButtons[item] = btn  # 存储按钮对象

        # 右侧内容区父容器
        self.contentFrame = ctk.CTkFrame(self, fg_color="transparent")  # 定义内容区框架，设置背景颜色为透明
        self.contentFrame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)  # 将内容区放置在右侧，填充整个高度和宽度，并设置内边距为10像素
        self.contentFrame.grid_rowconfigure(0, weight=1)  # 让内容区垂直可伸缩
        self.contentFrame.grid_columnconfigure(0, weight=1)  # 让内容区水平可伸缩
        self.pages = {}
        self.pages["首页"] = HomePage(self.contentFrame, fg_color="transparent")
        # 创建一个首页对象，并存储在self.pages字典中，键为"首页"，值为HomePage对象。第一个参数self.contentFrame表示将页面放置在内容区父容器中，第二个参数fg_color="transparent"表示设置页面背景颜色为透明。
        self.pages["设置"] = SettingsPage(self.contentFrame, fg_color="transparent")

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
            border_color="#555555",  # 边框颜色
            font=("微软雅黑", 16),
            height=40
        )
        self.addProfileBtn.grid(row=self.numberOfNavigationBarItems + 1, column=0, pady=(10, 20), padx=10, sticky="ew")

    # 切换页面函数，参数name表示要显示的页面名称。思路是隐藏所有页面，然后显示选中的页面，并高亮当前选中的导航按钮。
    def showPage(self, name):
        # 隐藏所有页面。遍历self.pages字典，将所有页面隐藏。grid_forget()方法用于从网格中移除组件，但保留其占用的空间。
        for pageName, page in self.pages.items():
            page.grid_forget()
        # 恢复所有导航按钮的默认样式。遍历self.navButtons字典，将所有按钮的背景颜色恢复为透明。
        for btnName, btn in self.navButtons.items():
            btn.configure(fg_color="transparent")
        # 显示选中的页面。将选中的页面显示在内容区父容器中，并使用grid()方法进行布局。sticky="nsew"表示按钮在水平和垂直方向上填满整个单元格。
        self.pages[name].grid(row=0, column=0, sticky="nsew")
        # 高亮当前选中的导航按钮。将选中的导航按钮的背景颜色设置为#3a3a3a。
        self.navButtons[name].configure(fg_color="#3a3a3a")

    def createNewShortcutSchemePage(self, schemeName):
        newPage = NewShortcutSchemePage(
            self.contentFrame,
            fg_color="transparent",
            schemeName=schemeName,
            onCopied=self.handleSchemeCopied,
            ondeleted=self.handleSchemeDeleted,
            onRenamed=self.handleSchemeRenamed,
            onStartupChanged=self.handleSchemeStartupChanged,
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
            self.showPage(newName)
        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def createNavigationBarItemsBasedOnShortcutKeyScheme(self, schemes):
        """根据快捷键方案列表创建导航栏按钮和对应页面"""
        schemes = sorted(schemes, key=lambda x: x["name"])  # sorted() 函数用于对可迭代对象进行排序，返回一个新的列表。
        # key 参数指定一个函数，用于从每个元素中提取用于排序的键。
        # 在这里，lambda x: x["name"] 是一个匿名函数，它接受一个字典 x，并返回该字典中 "name" 键对应的值。
        # 这样，schemes 列表就会根据每个方案的名称进行升序排序。
        for i, scheme in enumerate(schemes):
            #  用 enumerate 拿到索引 i
            schemeName = scheme["name"]
            btn = ctk.CTkButton(
                self.nav_frame,
                text=schemeName,
                command=lambda name=schemeName: self.showPage(name),
                fg_color="transparent",
                hover_color="#3a3a3a",
                text_color="white",
                font=("微软雅黑", 20),
                height=40
            )
            row = 2 + i  # ← row=0是首页, row=1是设置, 方案从 row=2 开始递增
            btn.grid(row=row, column=0, pady=2, padx=10, sticky="ew")
            self.navButtons[schemeName] = btn
            # 创建新方案页面
            self.createNewShortcutSchemePage(schemeName)

    def refreshSchemeButtons(self):
        """刷新方案导航按钮（删除旧的，重新创建）"""
        # 1. 记录旧的弹簧行
        oldSpringRow = self.numberOfNavigationBarItems
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
        self.nav_frame.grid_rowconfigure(oldSpringRow,weight=0)  # grid_rowconfigure方法用于配置网格行的权重。这里将旧弹簧行的权重设置为0，表示该行不会随着窗口大小变化而伸缩，从而避免布局问题。
        # 4. 重新计算
        self.numberOfNavigationBarItems = theNumberOfTargetFilesInTheFolder(configDirectory) + 2
        # 5. 设置新弹簧行
        self.nav_frame.grid_rowconfigure(self.numberOfNavigationBarItems, weight=1)
        # 6. 移动"+ 新建"按钮到新位置
        self.addProfileBtn.grid(row=self.numberOfNavigationBarItems + 1, column=0, pady=(10, 20), padx=10, sticky="ew")
        # 7. 重新创建方案按钮和页面
        self.createNavigationBarItemsBasedOnShortcutKeyScheme(getShortcutSchemes(configDirectory))

    def handleSchemeRenamed(self, oldName, newName):#多出的参数删了就报错
        """改名成功后由子页面回调：刷新导航栏 + 跳转到新页面"""
        self.refreshSchemeButtons()  # 重建所有方案按钮和页面
        self.showPage(newName)  # 跳转到改名后的页面

    def handleSchemeStartupChanged(self):
        """某个方案切换了启用状态后，刷新所有方案页面的状态显示"""
        for name, page in self.pages.items():
            # 只刷新 NewShortcutSchemePage 类型的页面
            if isinstance(page, NewShortcutSchemePage):
                page.refreshStartupDisplay()

    def handleSchemeCopied(self, oldSchemeName,newSchemeName, ):#多出的参数删了就报错
        """复制成功后由子页面回调：刷新导航栏 + 跳转到新页面"""
        self.refreshSchemeButtons()  # 重建所有方案按钮和页面
        self.showPage(oldSchemeName)  # 跳转被复制的页面

    def handleSchemeDeleted(self, deletedSchemeName):#多出的参数删了就报错
        """删除成功后由子页面回调：刷新导航栏 + 跳转到首页"""
        self.refreshSchemeButtons()  # 重建所有方案按钮和页面
        self.showPage("首页")  # 跳转到首页
