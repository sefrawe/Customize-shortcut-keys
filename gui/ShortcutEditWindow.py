''' 编辑快捷键弹窗 '''
import customtkinter as ctk
from utils.actionRegistry import (
    getAllActionDisplayNames,
    getActionDefByDisplayName,
    getActionDefByKey,
    ParamSpec
)


class ShortcutEditWindow(ctk.CTkToplevel):
    def __init__(self, parent, shortcut):  # 参数分别为父窗口和要编辑的快捷键对象
        super().__init__(parent)  # 调用父类的构造函数，传入父窗口作为参数
        self.shortcut = shortcut  # 将要编辑的快捷键对象存储在实例变量中
        # 存储当前动态生成的参数控件，用于最后保存时读取值
        self._paramWidgets: dict = {}

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

        # # 动作部分 - 暂时未实现
        # # self.grid_rowconfigure(3, weight=0)
        # self.actionFrame = ctk.CTkFrame(self, height=50)
        # self.actionFrame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        # self.actionLabel = ctk.CTkLabel(self.actionFrame, text="动作:",font=("微软雅黑", 16))
        # self.actionLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        # # 创建动作输入框并插入旧值
        # self.actionEntry = ctk.CTkEntry(self.actionFrame, placeholder_text="请输入新动作", font=("微软雅黑", 16))
        # self.actionEntry.insert(0, shortcutOldAction)  # 将旧动作插入到输入框第0个字符位置
        # self.actionEntry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        # self.actionFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩
        #
        # # 动作参数部分 - 暂时未实现

        # === 动作类型选择部分 (新增) ===
        self.actionFrame = ctk.CTkFrame(self, height=50)
        self.actionFrame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.actionFrame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.actionFrame, text="动作类型:", font=("微软雅黑", 16)).grid(row=0, column=0, sticky="w",
                                                                                     padx=5, pady=5)

        self.actionOption = ctk.CTkOptionMenu(
            self.actionFrame,
            values=getAllActionDisplayNames(),
            command=self._onActionChanged,
            font=("微软雅黑", 14)
        )
        self.actionOption.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # === 动态参数容器 (新增) ===
        self.paramsFrame = ctk.CTkFrame(self, fg_color="transparent")
        self.paramsFrame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        self.paramsFrame.grid_columnconfigure(1, weight=1)

        # === 初始化回填动作数据 ===
        actionDef = getActionDefByKey(shortcutOldAction)
        if actionDef:
            self.actionOption.set(actionDef.displayName)
            # 触发渲染并传入旧参数
            self._onActionChanged(actionDef.displayName, presetParams=shortcutOldActionParams)
        else:
            # 未知动作容错：回退为“（无动作）”
            self.actionOption.set("（无动作）")
            self._onActionChanged("（无动作）")

    def _onActionChanged(self, displayName: str, presetParams: dict | None = None):
        """当下拉框动作改变时，动态重建参数区域"""
        # 1. 清空旧控件
        for widget in self.paramsFrame.winfo_children():
            widget.destroy()
        self._paramWidgets.clear()

        # 2. 获取当前动作定义
        actionDef = getActionDefByDisplayName(displayName)
        if not actionDef:
            return

        # 3. 根据定义生成新控件
        presetParams = presetParams or {}
        for i, spec in enumerate(actionDef.params):
            # 生成标签 (满足动态标签需求)
            ctk.CTkLabel(self.paramsFrame, text=spec.label + ":", font=("微软雅黑", 14)).grid(
                row=i, column=0, sticky="ne", padx=5, pady=5
            )
            # 生成输入控件
            widget = self._buildParamWidget(spec, presetParams.get(spec.key, spec.default))
            widget.grid(row=i, column=1, sticky="nsew", padx=5, pady=5)
            self._paramWidgets[spec.key] = widget

    def _buildParamWidget(self, spec: ParamSpec, initialValue):
        """根据规格生成具体的控件"""
        if spec.widget == "multiline":
            w = ctk.CTkTextbox(self.paramsFrame, font=("微软雅黑", 13), height=80)
            if initialValue:
                w.insert("1.0", str(initialValue))
            return w

        # 默认单行输入框
        w = ctk.CTkEntry(self.paramsFrame, font=("微软雅黑", 13))
        if initialValue:
            w.insert(0, str(initialValue))
        return w

        #保存按钮
        #取消按钮
