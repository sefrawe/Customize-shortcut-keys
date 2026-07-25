'''
主窗口
'''
from hmac import new

import customtkinter as ctk
import json

from gui.SettingsPage import SettingsPage
from gui.HomePages import HomePage

# from gui.SettingsWindow import SettingsWindow

# 打开本地全局设置json文件
with open("./config/Global Settings.json", "r", encoding="utf-8") as f:
    global_settings = json.load(f)
# 读取外观模式配置
appearanceMode=global_settings["appearanceMode"]

# numberOfNavigationBarSections=4  # 导航栏分为4个部分，分别是首页、功能1、功能2、设置

class MainWindow(ctk.CTk):
    """程序主窗口类，继承自CustomTkinter的CTk主窗口"""

    def __init__(self):
        super().__init__()

        # 窗口基本设置
        self.title("自定义快捷键工具")
        self.geometry("800x600")  # 初始窗口大小
        self.minsize(800, 600)  # 窗口最小大小

        self._set_appearance_mode(appearanceMode)  # 可选: "light", "dark", "system"

        # 在这里添加窗口内容

        # 主布局：分为左右两列。使用grid布局管理器，左侧为导航栏，右侧为内容区，index=0表示左侧导航栏，index=1表示右侧内容区

        # index的含义：grid布局管理器中，row表示行，column表示列，index表示索引，从0开始计数。row=0表示第一行，column=0表示第一列，row=1表示第二行，column=1表示第二列，以此类推。

        self.grid_columnconfigure(0, weight=0)  # 左侧导航栏固定宽度.完整解释：grid_columnconfigure方法用于配置网格列的权重。权重为0表示该列不会随着窗口大小变化而伸缩，而权重为1表示该列会根据窗口大小变化而伸缩。
        self.grid_rowconfigure(0, weight=1)  # 行可伸缩
        # 左侧导航栏（垂直菜单）
        self.nav_frame = ctk.CTkFrame(self, width=150, fg_color="#303030") # 定义导航栏框架，设置宽度和背景颜色
        '''
        改width的值，导航栏宽度没有变化的原因：
        你使用的是 grid 布局，在 grid 布局中，CTkFrame 的 width 参数会被忽略，
        因为 grid 会根据子组件的内容自动计算列宽，而不是根据你设定的 width 值。
        你的导航栏里只有按钮和 padx=20 的间距，所以实际宽度远小于 400。
        解决方法： 在 nav_frame 上调用 grid_propagate(False)，阻止子组件反向决定 frame 的尺寸，这样 width=400 才会生效
        '''
        self.nav_frame.grid(row=0, column=0,sticky="ns")# 将导航栏放置在左侧，填充整个高度（sticky="ns"表示上下填充），row=0表示第一行，column=0表示第一列。这句代码的作用是将导航栏放置在主窗口的左侧，并且填充整个高度，使其看起来像一个垂直菜单栏。
        self.nav_frame.grid_rowconfigure(4, weight=1) # 这句功能是让导航栏的第5行（index=4）可以伸缩，从而将按钮推到顶部

        self.grid_columnconfigure(1, weight=1)  # 右侧内容区可伸缩

        # 导航栏内部布局：依次垂直排列按钮
        navItems = ["首页", "功能1", "功能2", "设置"]
        self.navButtons = {}  # 存储按钮对象，方便后续高亮

        for i, item in enumerate(navItems):
            #i,item分别表示索引和导航项名称
            # 创建按钮，绑定切换页面的函数
            btn = ctk.CTkButton(
                self.nav_frame,
                text=item,
                command=lambda name=item: self.showPage(name),
                fg_color="transparent",  # 默认透明背景
                hover_color="#3a3a3a",  # 悬停时背景色
                text_color="white" , # 文字颜色
                font=("微软雅黑", 20),
                height=40

            )
            btn.grid(row=i, column=0, pady=2, padx=10, sticky="ew")  # 填满宽度,各属性分别表示：row=i表示按钮所在行，column=0表示按钮所在列，pady=10表示上下间距为10像素，padx=20表示左右间距为20像素，sticky="ew"表示按钮在水平方向上填满整个单元格。
            self.navButtons[item] = btn  # 存储按钮对象

        # 右侧内容区父容器
        self.contentFrame = ctk.CTkFrame(self, fg_color="transparent")# 定义内容区框架，设置背景颜色为透明
        self.contentFrame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)# 将内容区放置在右侧，填充整个高度和宽度，并设置内边距为10像素

        self.pages={}
        self.pages["首页"] = HomePage(self.contentFrame, fg_color="transparent")
        # 创建一个首页对象，并存储在self.pages字典中，键为"首页"，值为HomePage对象。第一个参数self.contentFrame表示将页面放置在内容区父容器中，第二个参数fg_color="transparent"表示设置页面背景颜色为透明。
        self.pages["功能1"] = HomePage(self.contentFrame, fg_color="transparent")#todo 页面还没做，用HomePage占位
        self.pages["功能2"] = HomePage(self.contentFrame, fg_color="transparent")#todo 页面还没做，用HomePage占位
        self.pages["设置"]=SettingsPage(self.contentFrame, fg_color="transparent")

        self.showPage("首页")  # 默认显示首页

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




