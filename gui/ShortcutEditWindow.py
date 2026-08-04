''' 编辑快捷键弹窗 '''
import customtkinter as ctk

class ShortcutEditWindow(ctk.CTkToplevel):
    def __init__(self, parent, shortcut):  # 参数分别为父窗口和要编辑的快捷键对象
        super().__init__(parent)  # 调用父类的构造函数，传入父窗口作为参数
        self.shortcut = shortcut  # 将要编辑的快捷键对象存储在实例变量中

        # 从快捷键对象中获取旧值
        shortcutId = shortcut.get("id", 0)
        shortcutOldName = shortcut.get("name", "")
        shortcutOldDescription = shortcut.get("description", "")
        shortcutOldCombination = shortcut.get("keyCombination", "")
        shortcutOldAction = shortcut.get("action", "")
        shortcutOldActionParams = shortcut.get("actionParams", "")

        # 设置窗口标题和尺寸
        self.title("编辑快捷键 id:{}".format(shortcutId))  # 设置窗口标题，显示要编辑的快捷键的id
        self.minsize(600, 400)  # 设置窗口最小尺寸为600x400
        self.geometry("600x400")  # 设置窗口初始尺寸为600x400

        # 配置窗口网格布局
        # 第一列权重为1，使其在窗口变长时宽度随之变化
        self.grid_columnconfigure(0, weight=1)
        # 第一行权重为0，使其在窗口变长时高度不随之变化
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)

        # 名字部分
        self.nameFrame = ctk.CTkFrame(self, height=50)
        self.nameFrame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        self.nameLabel = ctk.CTkLabel(self.nameFrame, text="名字:",font=("微软雅黑", 16))
        self.nameLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # 创建名字输入框并插入旧值
        self.nameEntry = ctk.CTkEntry(self.nameFrame, placeholder_text="请输入新名字", font=("微软雅黑", 16))
        self.nameEntry.insert(0, shortcutOldName)  # 将旧名字插入到输入框第0个字符位置
        self.nameEntry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.nameFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩

        # 快捷键部分
        self.keyFrame = ctk.CTkFrame(self, height=50)
        self.keyFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        self.keyLabel = ctk.CTkLabel(self.keyFrame, text="快捷键:",font=("微软雅黑", 16))
        self.keyLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # 创建快捷键输入框并插入旧值
        self.keyEntry = ctk.CTkEntry(self.keyFrame, placeholder_text="请输入新快捷键", font=("微软雅黑", 16))
        self.keyEntry.insert(0, shortcutOldCombination)  # 将旧快捷键插入到输入框第0个字符位置
        self.keyEntry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.keyFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩

        # 备注部分 - 使用多行文本框
        self.descriptionFrame = ctk.CTkFrame(self, height=50)
        self.descriptionFrame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)


        self.descriptionLabel = ctk.CTkLabel(self.descriptionFrame, text="备注:",font=("微软雅黑", 16))
        self.descriptionLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # 创建多行文本框并插入旧值
        self.descriptionEntry = ctk.CTkTextbox(
            self.descriptionFrame,
            font=("微软雅黑", 14),
            wrap="word",        # 自动换行：让文本在单词边界处自动换行
            height=100           # 最小高度：设置文本框的最小高度为5行
        )
        self.descriptionEntry.insert("1.0", shortcutOldDescription)  # 插入文本：多行文本框使用"1.0"作为插入位置
        self.descriptionEntry.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)  # 填满整个单元格
        self.descriptionFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩


        # 动作部分 - 暂时未实现
        # 动作参数部分 - 暂时未实现
        #保存按钮
        #取消按钮
