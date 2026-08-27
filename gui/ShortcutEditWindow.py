''' 编辑快捷键弹窗 '''
''' 
# ==============================
# 数据驱动的动作编辑系统架构说明
# ==============================
# 核心思想：通过"动作注册表"实现动作定义与UI、执行逻辑的解耦，所有动作以数据形式管理，
# 新增/修改动作无需改动核心代码，只需在注册表中添加/更新定义即可，极大提升扩展性。
#
# 1. 动作注册表（ActionRegistry）
# - 存储所有动作的元数据（动作key、显示名称、参数规格）。
# - 作为全局单例，提供动作定义的查询接口（如通过key或显示名称获取动作）。
# - 示例：注册"粘贴文本"动作时，只需定义参数（文本内容）和显示名称，无需修改UI或执行代码。
#
# 2. 动态UI生成（ShortcutEditWindow）
# - 根据注册表的动作定义，动态生成参数输入控件（如单行输入框、多行文本框）。
# - 当用户切换动作类型时，自动清空旧参数并生成新参数的控件，实现UI与动作的动态绑定。
# - 参数规格（ParamSpec）定义了控件的类型、默认值、必填状态，确保UI与数据的一致性。
#
# 3. 执行逻辑解耦（Executor）
# - 执行器通过动作key从注册表获取动作定义，根据参数规格执行对应操作。
# - 动作执行逻辑与UI完全分离，新增动作只需实现执行函数，无需修改执行器代码。
# - 例如："粘贴文本"动作的执行函数接收参数（文本内容），通过剪贴板API实现粘贴。
#
# 4. 扩展性设计
# - 新增动作：只需在注册表中添加ActionDef，定义参数规格和执行逻辑即可。
# - 修改动作：更新注册表中的动作定义，UI和执行逻辑会自动适配。
# - 删除动作：从注册表中移除对应定义，无需清理代码。
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
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
from core.configManager import loadWindowSettings, center_window
from utils.actionRegistry import (
    getAllActionDisplayNames,
    getActionDefByDisplayName,
    getActionDefByKey
)
from utils.keyValidator import validate_key_combination


class ShortcutEditWindow(ctk.CTkToplevel):
    def __init__(self, parent, shortcut, executor=None):
        # 参数分别为父窗口和要编辑的快捷键对象
        super().__init__(parent)
        # 调用父类的构造函数，传入父窗口作为参数
        self.shortcut = shortcut
        # 将要编辑的快捷键对象存储在实例变量中
        # 存储当前动态生成的参数控件，用于最后保存时读取值
        self._paramWidgets: dict = {}
        self.saved = False  # 标记是否保存了修改，初始为False
        self.executor = executor  # 执行器，获取坐标要暂停监听，所以这里传入

        # 从快捷键对象中获取旧值
        shortcutId = shortcut.get("id", 0)
        shortcutOldName = shortcut.get("name", "")
        shortcutOldDescription = shortcut.get("description", "")
        shortcutOldCombination = shortcut.get("keyCombination", "")
        shortcutOldAction = shortcut.get("action", "")
        shortcutOldActionParams = shortcut.get("actionParams", "")

        # 设置窗口标题和尺寸
        self.title("编辑快捷键：id={}。此窗口涉及修改配置文件，不允许最小化和对软件进行其他操作".format(
            shortcutId))
        # 设置窗口标题，显示要编辑的快捷键的id
        # 固定编辑窗口的最小尺寸
        self.minsize(600, 400)

        # 读取全局配置，决定编辑窗口的初始大小和状态
        win_settings = loadWindowSettings().get("editWindow", {})
        is_maximized = win_settings.get("maximized", False)
        win_width = win_settings.get("width", 600)
        win_height = win_settings.get("height", 400)
        if is_maximized:
            # 弹窗最大化
            self.state("zoomed")
        else:
            # 按配置居中显示
            center_window(self, win_width, win_height)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)  # 滚动区域占满
        self.grid_rowconfigure(1, weight=0)  # 底部按钮固定

        self.scrollFrame = ctk.CTkScrollableFrame(self)
        self.scrollFrame.grid(row=0, column=0, sticky="nsew")
        self.scrollFrame.grid_columnconfigure(0, weight=1)

        # 名字部分
        self.nameFrame = ctk.CTkFrame(self.scrollFrame, height=50)
        self.nameFrame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.nameLabel = ctk.CTkLabel(self.nameFrame, text="名字:", font=("微软雅黑", 16))
        self.nameLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        # 创建名字输入框并插入旧值
        self.nameEntry = ctk.CTkEntry(self.nameFrame, placeholder_text="请输入新名字", font=("微软雅黑", 16))
        self.nameEntry.insert(0, shortcutOldName)
        # 将旧名字插入到输入框第0个字符位置
        self.nameEntry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.nameFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩

        # 快捷键部分
        self.keyFrame = ctk.CTkFrame(self.scrollFrame, height=50)
        self.keyFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.keyLabel = ctk.CTkLabel(self.keyFrame, text="快捷键:", font=("微软雅黑", 16))
        self.keyLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        # 创建快捷键输入框并插入旧值
        self.keyEntry = ctk.CTkEntry(self.keyFrame, placeholder_text="请输入新快捷键", font=("微软雅黑", 16))
        self.keyEntry.insert(0, shortcutOldCombination)
        # 将旧快捷键插入到输入框第0个字符位置
        self.keyEntry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.keyFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩

        # 备注部分 - 使用多行文本框
        self.descriptionFrame = ctk.CTkFrame(self.scrollFrame, height=50)
        self.descriptionFrame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self.descriptionLabel = ctk.CTkLabel(self.descriptionFrame, text="备注:", font=("微软雅黑", 16))
        self.descriptionLabel.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        # 创建多行文本框并插入旧值
        self.descriptionEntry = ctk.CTkTextbox(
            self.descriptionFrame, font=("微软雅黑", 14), wrap="word", height=100
        )
        self.descriptionEntry.insert("1.0", shortcutOldDescription)
        # 插入文本：多行文本框使用"1.0"作为插入位置
        self.descriptionEntry.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        # 填满整个单元格
        self.descriptionFrame.grid_columnconfigure(1, weight=1)  # 让输入框列可伸缩

        self.actionFrame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
        self.actionFrame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.actionFrame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.actionFrame, text="动作类型:", font=("微软雅黑", 16)).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.actionOption = ctk.CTkOptionMenu(
            self.actionFrame,
            values=getAllActionDisplayNames(),
            command=self._onActionChanged,
            font=("微软雅黑", 14)
        )
        self.actionOption.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # ==================== 设计26：新增动作提示 hint 框 ====================
        # 放在动作下拉框下方，参数区域上方
        self.hintTextbox = ctk.CTkTextbox(
            self.scrollFrame, font=("微软雅黑", 12), height=120, corner_radius=5, wrap="word"
        )
        # 默认不显示，等 _onActionChanged 触发时根据有无内容再 grid
        # =============================================================

        # 动态参数容器 (原本是 row=4，现在因为插入了 hint，改成 row=5)
        self.paramsFrame = ctk.CTkFrame(self.scrollFrame)
        self.paramsFrame.grid(row=5, column=0, sticky="nsew", padx=10, pady=5)
        self.paramsFrame.grid_columnconfigure(1, weight=1)

        # 初始化回填动作数据
        actionDef = getActionDefByKey(shortcutOldAction)
        if actionDef:
            self.actionOption.set(actionDef.displayName)
            # 触发渲染并传入旧参数
            self._onActionChanged(actionDef.displayName, presetParams=shortcutOldActionParams)
        else:
            # 未知动作容错：回退为"（无动作）"
            self.actionOption.set("（无动作）")
            self._onActionChanged("（无动作）")

        # 底部按钮区
        self.buttonFrame = ctk.CTkFrame(self, fg_color="transparent")
        self.buttonFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(self.buttonFrame, text="保存", command=self.onSave).pack(side="left", padx=5)
        self.getCoordBtn = ctk.CTkButton(
            self.buttonFrame, text="获取鼠标坐标", command=self.start_coord_capture,
            font=("微软雅黑", 14),
        )
        self.getCoordBtn.pack(side="left", padx=5)
        ctk.CTkButton(self.buttonFrame, text="取消", fg_color="#A30000", hover_color="#7A0000", command=self.destroy).pack(side="left", padx=5)

    def _buildParamWidget(self, spec, initialValue):
        """根据规格生成具体的控件"""
        if spec.widget == "multiline":
            w = ctk.CTkTextbox(self.paramsFrame, font=("微软雅黑", 13), height=80)
            if initialValue:
                w.insert("1.0", str(initialValue))
            return w
        elif spec.widget == "combobox":
            w = ctk.CTkOptionMenu(self.paramsFrame, values=spec.options, font=("微软雅黑", 13))
            if initialValue:
                w.set(str(initialValue))
            else:
                w.set(spec.options[0] if spec.options else "")
            return w
        elif spec.widget == "checkbox":
            w = ctk.CTkCheckBox(self.paramsFrame, text="", font=("微软雅黑", 13))
            if initialValue:
                w.select()
            return w
        elif spec.widget == "slider":
            container = ctk.CTkFrame(self.paramsFrame, fg_color="transparent")
            val_label = ctk.CTkLabel(container, text=str(int(float(initialValue))), font=("微软雅黑", 13, "bold"), width=40)
            val_label.pack(side="right", padx=(5, 0))
            slider = ctk.CTkSlider(container, from_=spec.from_, to=spec.to, command=lambda val, l=val_label: l.configure(text=str(int(val))))
            slider.set(float(initialValue))
            slider.pack(side="left", fill="x", expand=True)
            container._slider = slider
            return container
        # ==================== 新增：动态方案下拉框 ====================
        elif spec.widget == "dynamic_combobox_schemes":
            from utils.shortcutUtils import getShortcutSchemesNames
            from core.configManager import configDirectory
            # ==================== 设计25修改：下拉框加上"（无）"选项 ====================
            # 在所有方案名前面加上"（无）"，代表禁用所有方案
            current_schemes = ["（无）"] + getShortcutSchemesNames(configDirectory)
            w = ctk.CTkComboBox(self.paramsFrame, values=current_schemes, font=("微软雅黑", 13))
            # 回填旧值
            if initialValue:
                w.set(str(initialValue))
            else:
                w.set("（无）")  # 如果旧值为空，默认选中"（无）"
            return w
            # ========================================================
        else:
            # 默认单行输入框
            w = ctk.CTkEntry(self.paramsFrame, font=("微软雅黑", 13), placeholder_text=spec.placeholder)
            if initialValue:
                w.insert(0, str(initialValue))
            return w

    def _onActionChanged(self, displayName: str, presetParams: dict | None = None):
        """当下拉框动作改变时，动态重建参数区域"""
        # 1. 清空旧控件
        for widget in self.paramsFrame.winfo_children():
            widget.destroy()
        self._paramWidgets.clear()
        # ★ 重置 paramsFrame 内部 grid 权重（清理动作组遗留配置）
        self.paramsFrame.grid_columnconfigure(0, weight=0)
        self.paramsFrame.grid_rowconfigure(0, weight=0)
        self.paramsFrame.grid_columnconfigure(1, weight=1)  # 恢复常规动作的列权重

        # 2. 获取动作定义
        actionDef = getActionDefByDisplayName(displayName)
        if not actionDef:
            return

        # hint 提示框固定 row=4
        if actionDef.hint:
            self.hintTextbox.configure(state="normal")
            self.hintTextbox.delete("1.0", "end")
            self.hintTextbox.insert("1.0", actionDef.hint)
            self.hintTextbox.configure(state="disabled")
            self.hintTextbox.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 5))
        else:
            self.hintTextbox.grid_forget()

        # 动作组特殊处理
        if actionDef.key == "actionGroup":
            self._buildActionGroupUI(presetParams)
            return

        # 3. 常规动作：生成参数控件
        presetParams = presetParams or {}
        for i, spec in enumerate(actionDef.params):
            ctk.CTkLabel(self.paramsFrame, text=spec.label + ":", font=("微软雅黑", 14)).grid(
                row=i, column=0, sticky="ne", padx=5, pady=5
            )
            widget = self._buildParamWidget(spec, presetParams.get(spec.key, spec.default))
            widget.grid(row=i, column=1, sticky="nsew", padx=5, pady=5)
            self._paramWidgets[spec.key] = widget
        # ★ 固定 row=5，不再抢 row=4
        self.paramsFrame.grid(row=5, column=0, sticky="ew", padx=10, pady=5)

    def openActionGroupEditor(self):
        """打开动作组步骤编辑子窗口"""
        # 延迟导入避免循环依赖
        from gui.ActionGroupEditorWindow import ActionGroupEditorWindow
        # 获取当前暂存的完整数据传给子弹窗
        editor = ActionGroupEditorWindow(self, self._actionGroupData)
        self.wait_window(editor)
        # 子窗口关闭后，无论结果如何，都把 _actionGroupData 同步回来（子弹窗内部会管理深拷贝）
        # 我们需要确保主窗口拿到的是最新的全局配置和步骤列表
        if editor.result is not None:
            self._actionGroupData = editor.result
        # ★ 关键：子弹窗修改后，同步更新主界面的概览展示
        # 注意：主界面上已经没有全局参数的输入框了，所以不需要再手动 set 那些控件了
        self._updateStepSummary()

    def _buildActionGroupUI(self, presetParams: dict | None = None):
        """
        专门为"动作组"动作构建的特殊 UI

        布局演变记录：
        - v7 极简版：概览在上 + 编辑按钮在下（信息展示与编辑分离的第一版）
        - TODO30a：反转为 「编辑按钮在上 + 概览在下」
          理由：概览是主要阅读区，放下方能吃满剩余高度，窗口越大看得越多；
          编辑按钮属于低频入口，一行常驻顶部即可，不该挤占阅读区。
          本次仅调换两个组件的 grid 行号和对应权重，样式零改动。

        ==================== 修复布局：拉满父组件宽度 ====================
        （这段列权重修复沿用 v7 版，与新布局无关，保留防回归）
        """
        if not isinstance(presetParams, dict):
            presetParams = {}
        if "steps" not in presetParams:
            presetParams["steps"] = []
        presetParams.setdefault("stopOnError", "停止整个动作组")
        presetParams.setdefault("loopCount", "1")
        presetParams.setdefault("maxExecutionTime", "60")
        presetParams.setdefault("confirmAllAtOnce", False)
        self._actionGroupData = presetParams

        # 清空旧控件（切换动作类型回来时可能已有遗留）
        for widget in self.paramsFrame.winfo_children():
            widget.destroy()

        # ★ 固定 row=5（与常规动作参数区/hint 框的行位规划一致，勿动）
        self.paramsFrame.grid(row=5, column=0, sticky="nsew", padx=10, pady=5)

        # ==================== 修复布局：确保列权重正确传递 ====================
        # 常规动作分支遗留了 grid_columnconfigure(1, weight=1)，
        # 若不清回来，本容器在 column=0 会无法横向拉满。
        self.paramsFrame.grid_columnconfigure(0, weight=1)
        self.paramsFrame.grid_columnconfigure(1, weight=0)
        # =====================================================================

        # paramsFrame 自身只有这一行内容，纵向拉伸权全部交给它
        self.paramsFrame.grid_rowconfigure(0, weight=1)

        contentFrame = ctk.CTkFrame(self.paramsFrame, fg_color="transparent")
        contentFrame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        contentFrame.grid_columnconfigure(0, weight=1)

        # ==================== TODO30a：上下结构反转 ====================
        # row=0 编辑按钮区：weight=0 固定高度，常驻顶部不被挤压
        contentFrame.grid_rowconfigure(0, weight=0)
        # row=1 概览文本框：weight=1 吃掉剩余全部高度
        contentFrame.grid_rowconfigure(1, weight=1)

        # 上方：编辑按钮（左对齐，样式与交换前完全一致）
        editBtnFrame = ctk.CTkFrame(contentFrame, fg_color="transparent")
        # sticky="ew" 让容器横向拉满；底部留 5px 与概览区呼吸间隔
        editBtnFrame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        editBtnFrame.grid_columnconfigure(0, weight=1)  # 内部列可伸缩
        ctk.CTkButton(
            editBtnFrame,
            text="⚙ 编辑动作组步骤",
            command=self.openActionGroupEditor,
            font=("微软雅黑", 14),
            height=30
        ).pack(side="left", padx=5)

        # 下方：只读概览文本框
        self.stepSummaryTextbox = ctk.CTkTextbox(
            contentFrame,
            height=500,
            font=("微软雅黑", 13),
            corner_radius=5,
            state="disabled",
            fg_color="transparent"
        )
        # sticky="nsew" 四向填满分配的格子；间距与上方按钮区呼应
        self.stepSummaryTextbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))

        self._updateStepSummary()

    def _updateStepSummary(self):
        """v8：更新步骤概览文本框（层级缩进 + 每步分隔线）"""
        if not hasattr(self, "stepSummaryTextbox") or not self.stepSummaryTextbox.winfo_exists():
            return

        self.stepSummaryTextbox.configure(state="normal")
        self.stepSummaryTextbox.delete("1.0", "end")

        # --- 1. 配置颜色 Tag ---
        self.stepSummaryTextbox.tag_config("key_tag", foreground="#569CD6")  # 键名：淡蓝色
        self.stepSummaryTextbox.tag_config("val_tag", foreground="#DCDCAA")  # 值：淡黄色
        self.stepSummaryTextbox.tag_config("warn_tag", foreground="#FFA500")  # 警告：橙色
        self.stepSummaryTextbox.tag_config("title_tag", foreground="#4ECDC4")  # 标题：青色
        # ==================== 新增：分隔线专用颜色 Tag（灰色，弱化视觉）====================
        self.stepSummaryTextbox.tag_config("sep_tag", foreground="#606060")
        # ============================================================================

        # ==================== 新增：定义缩进常量 ====================
        # L1（一级缩进）：用于全局配置/预估区的键值对，以及步骤序号行
        INDENT_L1 = "    "
        # L2（二级缩进）：用于步骤详情下的备注、按键、次数、延迟、参数等（与步骤名对齐）
        INDENT_L2 = "         "
        # 分隔线（用户指定样式）
        SEPARATOR = "-------------------------------------"
        # =========================================================

        # --- 2. 展示全局选项（一级缩进）---
        self.stepSummaryTextbox.insert("end", "【全局配置】\n", "title_tag")
        loop_count = self._actionGroupData.get("loopCount", "1")
        max_exec = self._actionGroupData.get("maxExecutionTime", "60")

        self.stepSummaryTextbox.insert("end", f"{INDENT_L1}单步失败策略: ", "key_tag")
        self.stepSummaryTextbox.insert("end", f"{self._actionGroupData.get('stopOnError', '停止整个动作组')}\n",
                                       "val_tag")
        self.stepSummaryTextbox.insert("end", f"{INDENT_L1}循环执行次数: ", "key_tag")
        self.stepSummaryTextbox.insert("end", f"{loop_count} 次\n", "val_tag")
        self.stepSummaryTextbox.insert("end", f"{INDENT_L1}总超时限制: ", "key_tag")
        self.stepSummaryTextbox.insert("end", f"{max_exec} 秒\n", "val_tag")
        self.stepSummaryTextbox.insert("end", f"{INDENT_L1}执行前统一确认: ", "key_tag")
        is_confirm = self._actionGroupData.get("confirmAllAtOnce", False)
        self.stepSummaryTextbox.insert("end", f"{'是' if is_confirm else '否'}\n\n", "val_tag")

        # --- 3. 展示步数规模透明化（一级缩进）---
        all_steps = self._actionGroupData.get("steps", [])
        enabled_steps = [s for s in all_steps if s.get("enabled", True)]
        single_count = len(enabled_steps)
        total_estimated = single_count * int(loop_count if str(loop_count).isdigit() else 1)

        self.stepSummaryTextbox.insert("end", "【步数预估】\n", "title_tag")
        self.stepSummaryTextbox.insert("end", f"{INDENT_L1}单次执行步数: ", "key_tag")
        self.stepSummaryTextbox.insert("end", f"{single_count} 步\n", "val_tag")
        self.stepSummaryTextbox.insert("end", f"{INDENT_L1}预估总执行步数: ", "key_tag")
        self.stepSummaryTextbox.insert("end", f"{total_estimated} 步\n", "val_tag")

        # --- 计算预估最少执行时间（总延迟时间，统一毫秒）---
        total_delay_ms = 0
        for step in enabled_steps:
            delay_cfg = step.get("delayAfter", {})
            delay_type = delay_cfg.get("type", "none")
            delay_val = delay_cfg.get("value", 0)
            # 无论 fixed 还是 wait_release，底层存储的都已经是毫秒，直接相加
            if delay_type in ("fixed", "wait_release"):
                total_delay_ms += delay_val

        estimated_min_sec = (total_delay_ms / 1000) * int(loop_count if str(loop_count).isdigit() else 1)
        self.stepSummaryTextbox.insert("end", f"{INDENT_L1}预估最少执行时间: ", "key_tag")
        self.stepSummaryTextbox.insert("end", f"{estimated_min_sec:.1f} 秒 (仅含延迟)\n", "val_tag")
        self.stepSummaryTextbox.insert("end", f"{INDENT_L1}(注：单次执行步骤上限为 50 步)\n\n", "warn_tag")

        # --- 4. 展示步骤详情（隐藏禁用步骤，二级缩进 + 分隔线）---
        self.stepSummaryTextbox.insert("end", "【步骤详情】\n", "title_tag")
        if not enabled_steps:
            self.stepSummaryTextbox.insert("end", f"{INDENT_L1}暂无启用的步骤，请点击下方按钮编辑。\n", "warn_tag")
        else:
            # 延迟类型中文映射字典
            delay_type_map = {"none": "无", "fixed": "固定", "wait_release": "等待释放"}

            for i, step in enumerate(enabled_steps):
                # 步骤序号行（一级缩进）
                self.stepSummaryTextbox.insert("end", f"{INDENT_L1}{i + 1}. ", "key_tag")

                # 获取动作显示名
                action_key = step.get("action", "")
                action_def = getActionDefByKey(action_key)
                display_name = action_def.displayName.split('\n')[0] if action_def else action_key
                self.stepSummaryTextbox.insert("end", f"{display_name}\n", "val_tag")

                # 二级缩进展示备注
                note = step.get("note", "")
                if note:
                    self.stepSummaryTextbox.insert("end", f"{INDENT_L2}备注: {note}\n")

                # 二级缩进展示延迟信息
                delay_cfg = step.get("delayAfter", {})
                delay_type = delay_cfg.get("type", "none")
                delay_val = delay_cfg.get("value", 0)
                if delay_type != "none":
                    delay_text = f"{delay_type_map.get(delay_type, '未知')} {delay_val} 毫秒"
                    self.stepSummaryTextbox.insert("end", f"{INDENT_L2}延迟: ", "key_tag")
                    self.stepSummaryTextbox.insert("end", f"{delay_text}\n", "val_tag")

                # 二级缩进展示参数
                params = step.get("actionParams", {})
                if params and action_def:
                    for spec in action_def.params:
                        val = params.get(spec.key, "")
                        if val:
                            clean_label = spec.label.replace('\n', ' ')
                            self.stepSummaryTextbox.insert("end", f"{INDENT_L2}{clean_label}: ", "key_tag")
                            # 简单处理多行文本，只取第一行展示
                            val_str = str(val).split('\n')[0]
                            self.stepSummaryTextbox.insert("end", f"{val_str}\n", "val_tag")

                # ==================== 新增：每步结束后加分隔线 ====================
                # 最后一步后面不加，避免末尾出现孤零零的分隔线
                if i < len(enabled_steps) - 1:
                    self.stepSummaryTextbox.insert("end", f"{INDENT_L1}{SEPARATOR}\n", "sep_tag")
                # ==============================================================

        # --- 5. 末尾汇总禁用步骤 ---
        disabled_count = len(all_steps) - single_count
        if disabled_count > 0:
            self.stepSummaryTextbox.insert("end",
                                           f"\n(共有 {len(all_steps)} 步，其中 {disabled_count} 步已禁用，此处未展示)\n",
                                           "warn_tag")

        self.stepSummaryTextbox.configure(state="disabled")

    def onSave(self):
        """点击保存按钮时触发：收集数据、校验、回写、关闭"""
        # 1. 收集基本数据
        newName = self.nameEntry.get().strip()
        newKey = self.keyEntry.get().strip()
        newDesc = self.descriptionEntry.get("1.0", "end-1c").strip()

        # ==================== 新增：快捷键格式校验 ====================
        # 统一接收校验结果：是否合法、提示信息、清理后的标准数据
        is_valid, msg, cleaned_key = validate_key_combination(newKey)
        if not is_valid:
            # 弹窗询问是否强制保存
            confirm = messagebox.askyesno(
                "格式不合法",
                f"{msg}\n\n不合法的配置可能无法被正常触发。\n是否仍要强制保存？"
            )
            if not confirm:
                # 用户选择"否"，返回编辑状态，不关闭窗口
                return
            # 用户选择"是"，使用清理过的数据继续往下走
            newKey = cleaned_key
        else:
            # 校验通过，使用标准化后的数据
            newKey = cleaned_key
        # ============================================================

        # 2. 收集动作数据
        displayName = self.actionOption.get()
        actionDef = getActionDefByDisplayName(displayName)
        newAction = actionDef.key if actionDef else ""
        newActionParams = {}
        if actionDef:
            if actionDef.key == "actionGroup":
                # 直接从暂存区 _actionGroupData 读取全局参数（子弹窗内部已管理并校验过）
                newActionParams["stopOnError"] = self._actionGroupData.get("stopOnError", "停止整个动作组")
                newActionParams["loopCount"] = str(self._actionGroupData.get("loopCount", "1"))
                newActionParams["maxExecutionTime"] = str(self._actionGroupData.get("maxExecutionTime", "60"))
                newActionParams["confirmAllAtOnce"] = bool(self._actionGroupData.get("confirmAllAtOnce", False))
                # 收集步骤数据
                newActionParams["steps"] = self._actionGroupData.get("steps", [])
            else:
                # 常规动作的收集逻辑
                for key, widget in self._paramWidgets.items():
                    spec = next((p for p in actionDef.params if p.key == key), None)
                    # 根据控件类型读取值
                    if isinstance(widget, ctk.CTkTextbox):
                        val = widget.get("1.0", "end-1c").strip()
                    elif isinstance(widget, ctk.CTkCheckBox):
                        val = bool(widget.get())
                    elif isinstance(widget, ctk.CTkFrame) and hasattr(widget, '_slider'):
                        val = str(int(widget._slider.get()))
                    else:
                        val = widget.get().strip()
                    # ==================== 设计25修改：把"（无）"转为空字符串存储 ====================
                    if val == "（无）":
                        val = ""
                    # =====================================================================
                    if spec and spec.required and spec.widget != "checkbox" and not val:
                        messagebox.showerror("错误", f"参数 '{spec.label}' 不能为空！")
                        return
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

    # ==================== 坐标获取功能 ====================
    def start_coord_capture(self):
        if not self.executor:
            messagebox.showerror("错误", "未获取到执行器实例，无法暂停全局监听")
            return
        self.executor.stop()
        self._coord_count = 0
        self.capture_top = ctk.CTkToplevel(self)
        self.capture_top.geometry("320x120")
        self.capture_top.title("获取坐标模式")
        self.capture_top.attributes("-topmost", True)
        self.capture_top.protocol("WM_DELETE_WINDOW", lambda: None)
        self.capture_label = ctk.CTkLabel(
            self.capture_top,
            text="移动鼠标到目标位置\n按空格或Enter记录到备注，按 Esc 结束",
            font=("微软雅黑", 14)
        )
        self.capture_label.pack(pady=10)
        self.capture_listener = pynput_keyboard.Listener(on_press=self._on_capture_key_press)
        self.capture_listener.start()
        self._poll_mouse_pos()

    def _poll_mouse_pos(self):
        if hasattr(self, 'capture_top') and self.capture_top.winfo_exists():
            x, y = pynput_mouse.Controller().position
            self.capture_label.configure(
                text="移动鼠标到目标位置\n按 空格 或 Enter 记录到备注，按 Esc 结束\n当前坐标: ({}, {})".format(x, y)
            )
            self.after(50, self._poll_mouse_pos)

    def _on_capture_key_press(self, key):
        if key == pynput_keyboard.Key.enter or key == pynput_keyboard.Key.space:
            x, y = pynput_mouse.Controller().position
            self.after(0, lambda: self._insert_coord_to_desc(x, y))
        elif key == pynput_keyboard.Key.esc:
            self.after(0, self.stop_coord_capture)

    def _insert_coord_to_desc(self, x, y):
        self._coord_count += 1
        current_text = self.descriptionEntry.get("1.0", "end-1c")
        if current_text and not current_text.endswith("\n"):
            self.descriptionEntry.insert("end-1c", "\n")
        self.descriptionEntry.insert("end-1c", "坐标{}, x：{}, y：{}\n".format(self._coord_count, x, y))

    def stop_coord_capture(self):
        if hasattr(self, 'capture_listener') and self.capture_listener:
            self.capture_listener.stop()
            self.capture_listener = None
        if hasattr(self, 'capture_top') and self.capture_top.winfo_exists():
            self.capture_top.destroy()
        if self.executor:
            self.executor.start()
