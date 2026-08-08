''' 编辑快捷键弹窗 '''

'''
# ==============================
# 数据驱动的动作编辑系统架构说明
# ==============================
# 核心思想：通过"动作注册表"实现动作定义与UI、执行逻辑的解耦，所有动作以数据形式管理，
# 新增/修改动作无需改动核心代码，只需在注册表中添加/更新定义即可，极大提升扩展性。
#
# 1. 动作注册表（ActionRegistry）
#    - 存储所有动作的元数据（动作key、显示名称、参数规格）。
#    - 作为全局单例，提供动作定义的查询接口（如通过key或显示名称获取动作）。
#    - 示例：注册"粘贴文本"动作时，只需定义参数（文本内容）和显示名称，无需修改UI或执行代码。
#
# 2. 动态UI生成（ShortcutEditWindow）
#    - 根据注册表的动作定义，动态生成参数输入控件（如单行输入框、多行文本框）。
#    - 当用户切换动作类型时，自动清空旧参数并生成新参数的控件，实现UI与动作的动态绑定。
#    - 参数规格（ParamSpec）定义了控件的类型、默认值、必填状态，确保UI与数据的一致性。
#
# 3. 执行逻辑解耦（Executor）
#    - 执行器通过动作key从注册表获取动作定义，根据参数规格执行对应操作。
#    - 动作执行逻辑与UI完全分离，新增动作只需实现执行函数，无需修改执行器代码。
#    - 例如："粘贴文本"动作的执行函数接收参数（文本内容），通过剪贴板API实现粘贴。
#
# 4. 扩展性设计
#    - 新增动作：只需在注册表中添加ActionDef，定义参数规格和执行逻辑即可。
#    - 修改动作：更新注册表中的动作定义，UI和执行逻辑会自动适配。
#    - 删除动作：从注册表中移除对应定义，无需清理代码。
#
# 优势：
# - 代码复用：动作定义、UI生成、执行逻辑复用同一套数据结构。
# - 易维护：动作的元数据集中管理，修改时只需关注注册表。
# - 高扩展：支持任意类型的动作（如打开URL、发送邮件、执行脚本），只需符合注册表规范。
#
# 使用示例：
# 1. 注册动作：ActionRegistry.register(ActionDef(...))
# 2. 生成UI：根据动作定义动态创建参数控件。
# 3. 执行动作：通过动作key获取定义，传入参数执行操作。
#
# 注意事项：
# - 动作key需全局唯一，避免冲突。
# - 参数规格需与执行逻辑的参数一一对应。
# - 动作定义需包含必要的元数据（如显示名称、参数规格），确保UI和执行的正确性。
# ==============================

'''
from tkinter import messagebox

import customtkinter as ctk
from utils.actionRegistry import (
    getAllActionDisplayNames,
    getActionDefByDisplayName,
    getActionDefByKey,
    ParamSpec
)
#todo:快捷键录入：当前快捷键输入框是手动打字的，可以改成"按下组合键自动填入"（临时挂载 pynput 监听器）



class ShortcutEditWindow(ctk.CTkToplevel):
    def __init__(self, parent, shortcut):  # 参数分别为父窗口和要编辑的快捷键对象
        super().__init__(parent)  # 调用父类的构造函数，传入父窗口作为参数
        self.shortcut = shortcut  # 将要编辑的快捷键对象存储在实例变量中
        # 存储当前动态生成的参数控件，用于最后保存时读取值
        self._paramWidgets: dict = {}

        self.saved = False  # 标记是否保存了修改，初始为False

        # 从快捷键对象中获取旧值
        shortcutId = shortcut.get("id", 0)
        shortcutOldName = shortcut.get("name", "")
        shortcutOldDescription = shortcut.get("description", "")
        shortcutOldCombination = shortcut.get("keyCombination", "")
        shortcutOldAction = shortcut.get("action", "")
        shortcutOldActionParams = shortcut.get("actionParams", "")

        # 设置窗口标题和尺寸
        self.title("编辑快捷键：id={}。此窗口涉及修改配置文件，不允许最小化和对软件进行其他操作".format(shortcutId))  # 设置窗口标题，显示要编辑的快捷键的id
        self.minsize(600, 400)  # 设置窗口最小尺寸为600x400
        self.geometry("600x400")  # 设置窗口初始尺寸为600x400

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)  # 滚动区域占满
        self.grid_rowconfigure(1, weight=0)  # 底部按钮固定
        self.scrollFrame = ctk.CTkScrollableFrame(self)
        self.scrollFrame.grid(row=0, column=0, sticky="nsew")
        self.scrollFrame.grid_columnconfigure(0, weight=1)

        # 名字部分
        self.nameFrame = ctk.CTkFrame(self.scrollFrame, height=50)
        self.nameFrame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.nameLabel = ctk.CTkLabel(self.nameFrame, text="名字:",font=("微软雅黑", 16))
        self.nameLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        # 创建名字输入框并插入旧值
        self.nameEntry = ctk.CTkEntry(self.nameFrame, placeholder_text="请输入新名字", font=("微软雅黑", 16))
        self.nameEntry.insert(0, shortcutOldName)  # 将旧名字插入到输入框第0个字符位置
        self.nameEntry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.nameFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩

        # 快捷键部分
        self.keyFrame = ctk.CTkFrame(self.scrollFrame, height=50)
        self.keyFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.keyLabel = ctk.CTkLabel(self.keyFrame, text="快捷键:",font=("微软雅黑", 16))
        self.keyLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        # 创建快捷键输入框并插入旧值
        self.keyEntry = ctk.CTkEntry(self.keyFrame, placeholder_text="请输入新快捷键", font=("微软雅黑", 16))
        self.keyEntry.insert(0, shortcutOldCombination)  # 将旧快捷键插入到输入框第0个字符位置
        self.keyEntry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.keyFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩

        # 备注部分 - 使用多行文本框
        self.descriptionFrame = ctk.CTkFrame(self.scrollFrame, height=50)
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

        self.actionFrame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
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

        #动态参数容器
        self.paramsFrame =ctk.CTkFrame(self.scrollFrame, height=50)

        self.paramsFrame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        self.paramsFrame.grid_columnconfigure(1, weight=1)

        #初始化回填动作数据
        actionDef = getActionDefByKey(shortcutOldAction)
        if actionDef:
            self.actionOption.set(actionDef.displayName)
            # 触发渲染并传入旧参数
            self._onActionChanged(actionDef.displayName, presetParams=shortcutOldActionParams)
        else:
            # 未知动作容错：回退为“（无动作）”
            self.actionOption.set("（无动作）")
            self._onActionChanged("（无动作）")

            #底部按钮区
        self.buttonFrame = ctk.CTkFrame(self, fg_color="transparent")
        self.buttonFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkButton(self.buttonFrame, text="保存", command=self.onSave).pack(side="left", padx=5)#side可以填"left"、"right"、"top"、"bottom"，默认是"top"
        ctk.CTkButton(self.buttonFrame, text="取消", fg_color="#A30000", hover_color="#7A0000",
                      command=self.destroy).pack(side="left", padx=5)

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

    def onSave(self):
        """点击保存按钮时触发：收集数据、校验、回写、关闭"""
        # 1. 收集基本数据
        newName = self.nameEntry.get().strip()
        newKey = self.keyEntry.get().strip()
        newDesc = self.descriptionEntry.get("1.0", "end-1c").strip()# 获取多行文本框的内容，去掉末尾换行符

        # 2. 收集动作数据
        displayName = self.actionOption.get()
        actionDef = getActionDefByDisplayName(displayName)
        newAction = actionDef.key if actionDef else ""
        newActionParams = {}

        if actionDef:
            for key, widget in self._paramWidgets.items():
                # 根据控件类型读取值
                if isinstance(widget, ctk.CTkTextbox):
                    val = widget.get("1.0", "end-1c").strip()
                else:  # CTkEntry
                    val = widget.get().strip()

                # 查找当前参数的规格定义，用于校验必填
                spec = next((p for p in actionDef.params if p.key == key), None)
                if spec and spec.required and not val:
                    messagebox.showerror("错误", f"参数 '{spec.label}' 不能为空！")
                    return  # 阻止关闭

                newActionParams[key] = val

        # 3. 回写到 shortcut 字典
        self.shortcut["name"] = newName
        self.shortcut["keyCombination"] = newKey
        self.shortcut["description"] = newDesc
        self.shortcut["action"] = newAction
        self.shortcut["actionParams"] = newActionParams

        # 4. 标记已保存并关闭窗口
        self.saved = True
        self.destroy()


