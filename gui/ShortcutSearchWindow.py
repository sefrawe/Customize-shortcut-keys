'''
快捷键搜索窗口
'''
from utils.actionRegistry import getAllActionDisplayNames, getActionDefByDisplayName, ParamSpec
from utils.actionRegistry import getAllActionDisplayNames, getActionDefByDisplayName, getActionDefByKey, ParamSpec
from utils.shortcutUtils import normalize_key_combination

""" ==========================================================
    【快捷键搜索功能 - 设计规范与实现文档】
    ==========================================================
    一、 搜索范围与数据源
    ----------------------------------------------------------
    - 范围：仅限当前方案内部的快捷键。
    - 数据源：使用打开窗口时传入的 config 字典中的 shortcuts 列表。
    - 空条件行为：当所有搜索条件均为空时，默认返回/展示全部快捷键。

    二、 搜索逻辑与匹配规则
    ----------------------------------------------------------
    - 核心逻辑：多条件之间采用 AND（且）逻辑，所有条件同时满足才会被命中。
    - 各维度匹配规则如下：

      1. 名字
         - 控件：nameEntry
         - 规则：子串包含，不区分大小写。

      2. 快捷键
         - 控件：keyEntry
         - 规则：归一化后子串包含。
         - 强制要求：必须对【用户输入的搜索词】和【目标 keyCombination】
           都调用 normalize_key_combination() 后再进行匹配，
           以解决 "ctrl+alt" 搜不到 "alt+ctrl+1" 的问题。

      3. 备注
         - 控件：descEntry (修复重名)
         - 规则：子串包含，不区分大小写。允许换行，换行符 \n 正常参与匹配。

      4. 动作类型
         - 控件：actionOption
         - 规则：精确匹配 ActionDef.key。
         - 特殊处理：下拉框首项增加 "（不限）" 选项。
           · 选 "（不限）" 时：跳过动作类型及动作参数维度的匹配。
           · 选 "（无动作）" 时：被视为一个具体的动作，匹配 action == ""。

      5. 动作参数
         - 控件：动态生成的参数输入区
         - 规则：仅对用户填写的字段做子串包含匹配，未填写的字段忽略。
         - 依赖：动作类型选 "（不限）" 时，整体忽略此维度。

    三、 结果渲染规范
    ----------------------------------------------------------
    - 命中数提示：结果框最顶部插入一行小字 "共找到 N 条匹配"。
    - 结果项内容：依次展示 ID、名字、快捷键、备注、动作类型、动作参数。
    - 排版换行：允许换行展示，文本框使用 wrap="word"，不做单行截断。
    - 参数格式化：actionParams 以 "key: value" 的形式拼接为可读字符串
      (如 "text: myemail@example.com")。
    - 排序规则：命中结果沿用 NewShortcutSchemePage._shortcutSortKey 的逻辑按 ID 排序。
    - 无结果展示：仅显示 "未找到匹配的快捷键。"

    四、 UI 交互与命名修复
    ----------------------------------------------------------
    1. 变量重命名修复：
       - 备注输入框重命名为：self.descEntry
       - 结果展示框重命名为：self.resultTextbox (与主页 conflictResultTextbox 风格统一)

    2. 动作下拉框初始化：
       - values = ["（不限）"] + getAllActionDisplayNames()
       - 初始化默认设为 "（不限）"

    3. 新增重置按钮：
       - 在底部按钮区增加 "重置" 按钮。
       - 行为：清空所有输入框、将动作下拉框重置为 "（不限）" 并清空动态参数区，
         然后重新执行一次空搜索（展示全部）。

    4. 回车触发搜索：
       - nameEntry 和 keyEntry 绑定 <Return> 事件触发 onSearch。
       - 备注 Textbox 中回车为换行，不绑定触发。
    ==========================================================
"""


import customtkinter as ctk



class ShortcutSearchWindow(ctk.CTkToplevel):
    def __init__(self, parent, config):
        # 参数分别为父窗口和要编辑的快捷键方案的配置
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self._paramWidgets: dict = {}

        self.geometry("600x600")
        self.minsize(400, 400)
        self.title("搜索快捷键：根据名字、快捷键组合、备注、动作类型、动作参数进行搜索")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scrollFrame = ctk.CTkFrame(self)
        self.scrollFrame.grid(row=0, column=0, sticky="nsew")

        # 1. 名字输入框
        ctk.CTkLabel(self.scrollFrame, text="名字:", font=("微软雅黑", 16)).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.nameEntry = ctk.CTkEntry(self.scrollFrame, placeholder_text="请输入名字", font=("微软雅黑", 16))
        self.nameEntry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.scrollFrame.grid_columnconfigure(1, weight=1)
        self.nameEntry.bind("<Return>", lambda e: self.onSearch())

        # 2. 快捷键输入框
        ctk.CTkLabel(self.scrollFrame, text="快捷键:", font=("微软雅黑", 16)).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.keyEntry = ctk.CTkEntry(self.scrollFrame, placeholder_text="请输入快捷键", font=("微软雅黑", 16))
        self.keyEntry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.keyEntry.bind("<Return>", lambda e: self.onSearch())

        # 3. 备注输入框（修复命名冲突：原 descriptionEntry -> descEntry）
        ctk.CTkLabel(self.scrollFrame, text="备注:", font=("微软雅黑", 16)).grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        self.descEntry = ctk.CTkTextbox(self.scrollFrame, font=("微软雅黑", 14), wrap="word", height=100)
        self.descEntry.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)

        # 4. 动作类型下拉框（新增"（不限）"选项）
        ctk.CTkLabel(self.scrollFrame, text="动作类型:", font=("微软雅黑", 16)).grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.actionOption = ctk.CTkOptionMenu(
            self.scrollFrame,
            values=["（不限）"] + getAllActionDisplayNames(),
            command=self._onActionChanged,
            font=("微软雅黑", 14)
        )
        self.actionOption.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        self.actionOption.set("（不限）")  # 默认设为不限

        # 5. 动态参数容器
        ctk.CTkLabel(self.scrollFrame, text="动作参数:", font=("微软雅黑", 16)).grid(row=4, column=0, sticky="ne", padx=5, pady=5)
        self.paramsFrame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
        self.paramsFrame.grid(row=4, column=1, sticky="nsew", padx=5, pady=5)
        self.paramsFrame.grid_columnconfigure(1, weight=1)

        # 6. 结果显示区（修复命名冲突：原 descriptionEntry -> resultTextbox）
        ctk.CTkLabel(self.scrollFrame, text="搜索结果:", font=("微软雅黑", 16)).grid(row=5, column=0, sticky="nw", padx=5, pady=5)
        self.resultTextbox = ctk.CTkTextbox(self.scrollFrame, font=("微软雅黑", 14), wrap="word")
        self.resultTextbox.grid(row=5, column=1, sticky="nsew", padx=5, pady=5)
        self.scrollFrame.grid_rowconfigure(5, weight=1)  # 让结果框占据剩余空间
        self.resultTextbox.configure(state="disabled")

        # 7. 按钮区（新增"重置"按钮）
        self.buttonFrame = ctk.CTkFrame(self, fg_color="transparent")
        self.buttonFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(self.buttonFrame, text="搜索", command=self.onSearch).pack(side="left", padx=5)
        ctk.CTkButton(self.buttonFrame, text="取消", fg_color="#A30000", hover_color="#7A0000", command=self.destroy).pack(side="left", padx=5)
        ctk.CTkButton(self.buttonFrame, text="重置", command=self.onReset).pack(side="left", padx=5)

        # 初始化时执行一次空搜索，展示全部快捷键
        self.onSearch()

    def onSearch(self):
        """点击搜索按钮时触发：收集数据、执行匹配、渲染结果"""
        # 1. 收集基本数据 (统一转小写，便于不区分大小写匹配)
        name = self.nameEntry.get().strip().lower()
        key = self.keyEntry.get().strip()
        desc = self.descEntry.get("1.0", "end-1c").strip().lower()

        # 2. 获取动作条件
        actionDisplayName = self.actionOption.get()
        actionDef = None
        if actionDisplayName != "（不限）":
            actionDef = getActionDefByDisplayName(actionDisplayName)

        # 3. 遍历快捷键列表进行筛选
        matchedShortcuts = []
        for shortcut in self.config.get("shortcuts", []):
            # 3.1 名字匹配 (子串包含)
            if name and name not in shortcut.get("name", "").lower():
                continue

            # 3.2 快捷键匹配 (归一化后子串包含)
            if key:
                norm_key = normalize_key_combination(key)
                norm_sc_key = normalize_key_combination(shortcut.get("keyCombination", ""))
                if not norm_sc_key or norm_key not in norm_sc_key:
                    continue

            # 3.3 备注匹配 (子串包含)
            if desc and desc not in shortcut.get("description", "").lower():
                continue

            # 3.4 动作类型匹配 (精确匹配)
            if actionDef is not None:
                if shortcut.get("action", "") != actionDef.key:
                    continue

                # 3.5 动作参数匹配 (仅对用户填写的字段做包含匹配)
                params_matched = True
                for param_key, widget in self._paramWidgets.items():
                    if isinstance(widget, ctk.CTkTextbox):
                        val = widget.get("1.0", "end-1c").strip()
                    else:
                        val = widget.get().strip()

                    if val:  # 只处理用户填了的字段
                        target_val = str(shortcut.get("actionParams", {}).get(param_key, ""))
                        if val.lower() not in target_val.lower():
                            params_matched = False
                            break

                if not params_matched:
                    continue

            # 所有条件满足，加入结果集
            matchedShortcuts.append(shortcut)

        # 4. 排序
        matchedShortcuts.sort(key=self._shortcutSortKey)

        # 5. 渲染结果
        self._renderResults(matchedShortcuts)



    def onReset(self):
        """重置所有搜索条件并重新执行空搜索"""
        self.nameEntry.delete(0, "end")
        self.keyEntry.delete(0, "end")
        self.descEntry.delete("1.0", "end")
        self.actionOption.set("（不限）")  # 会自动触发 _onActionChanged 清空参数区
        self.onSearch()  # 立即执行一次空搜索

    def _renderResults(self, matchedShortcuts):
        """将匹配结果渲染到结果框中"""
        self.resultTextbox.configure(state="normal")
        self.resultTextbox.delete("1.0", "end")

        if not matchedShortcuts:
            self.resultTextbox.insert("end", "未找到匹配的快捷键。")
        else:
            self.resultTextbox.insert("end", f"共找到 {len(matchedShortcuts)} 条匹配\n\n")
            for sc in matchedShortcuts:
                sc_id = sc.get('id', '')
                sc_name = sc.get('name', '')
                sc_key = sc.get('keyCombination', '')
                sc_desc = sc.get('description', '')

                # 动作类型转显示名，找不到用原始 key
                sc_action_key = sc.get('action', '')
                action_def_temp = getActionDefByKey(sc_action_key)
                sc_action_display = action_def_temp.displayName if action_def_temp else sc_action_key

                # 动作参数格式化
                sc_params = sc.get('actionParams', {})
                params_str = ", ".join([f"{k}: {v}" for k, v in sc_params.items()]) if sc_params else ""

                self.resultTextbox.insert("end",
                                          f"ID: {sc_id}\n"
                                          f"名字: {sc_name}\n"
                                          f"快捷键: {sc_key}\n"
                                          f"备注: {sc_desc}\n"
                                          f"动作类型: {sc_action_display}, 动作参数: {params_str}\n"
                                          "----------------------------------------\n"
                                          )

        self.resultTextbox.configure(state="disabled")

    @staticmethod
    def _shortcutSortKey(shortcut):
        """用于排序快捷键列表，优先按数字ID排序，其次按字符串ID排序 (从主页复制，避免循环导入)"""
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
