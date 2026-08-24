''' 快捷键搜索窗口 '''

from core.configManager import loadWindowSettings, center_window
from utils.actionRegistry import getAllActionDisplayNames, getActionDefByDisplayName, getActionDefByKey, ParamSpec
from utils.shortcutUtils import normalize_key_combination

import customtkinter as ctk

class ShortcutSearchWindow(ctk.CTkToplevel):
    def __init__(self, parent, config):
        # 参数分别为父窗口和要编辑的快捷键方案的配置
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self._paramWidgets: dict = {} # 存储动态生成的参数控件，用于搜索时读取值

        # 固定搜索窗口的最小尺寸
        self.minsize(400, 400)

        # 读取全局配置，决定搜索窗口的初始大小和状态
        win_settings = loadWindowSettings().get("searchWindow", {})
        is_maximized = win_settings.get("maximized", False)
        win_width = win_settings.get("width", 600)
        win_height = win_settings.get("height", 600)

        if is_maximized:
            self.state("zoomed")
        else:
            center_window(self, win_width, win_height)

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

        # 3. 备注输入框
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
        self.actionOption.set("（不限）") # 默认设为不限

        # 5. 动态参数容器
        ctk.CTkLabel(self.scrollFrame, text="动作参数:", font=("微软雅黑", 16)).grid(row=4, column=0, sticky="ne", padx=5, pady=5)
        self.paramsFrame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
        self.paramsFrame.grid(row=4, column=1, sticky="nsew", padx=5, pady=5)
        self.paramsFrame.grid_columnconfigure(1, weight=1)

        # 6. 结果显示区
        ctk.CTkLabel(self.scrollFrame, text="搜索结果:", font=("微软雅黑", 16)).grid(row=5, column=0, sticky="nw", padx=5, pady=5)
        self.resultTextbox = ctk.CTkTextbox(self.scrollFrame, font=("微软雅黑", 14), wrap="word")
        self.resultTextbox.grid(row=5, column=1, sticky="nsew", padx=5, pady=5)
        self.scrollFrame.grid_rowconfigure(5, weight=1) # 让结果框占据剩余空间
        self.resultTextbox.configure(state="disabled")

        # 7. 按钮区
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

            # 3.5 动作参数匹配 (仅对用户填写的字段做匹配)
            params_matched = True
            for param_key, widget in self._paramWidgets.items():
                # --- 1. 判断控件类型并安全取值 ---
                val = ""
                if isinstance(widget, ctk.CTkTextbox):
                    val = widget.get("1.0", "end-1c").strip()
                elif isinstance(widget, ctk.CTkOptionMenu):
                    val = widget.get() # combobox 或 checkbox
                elif isinstance(widget, ctk.CTkEntry):
                    val = widget.get().strip() # entry 或 slider(退化)

                # --- 2. 跳过空值和"（不限）" ---
                if not val or val == "（不限）":
                    continue

                # --- 3. 获取目标快捷键中该参数的值 ---
                target_val_raw = shortcut.get("actionParams", {}).get(param_key, "")
                target_val = str(target_val_raw)

                # --- 4. 根据控件类型决定匹配规则 ---
                if isinstance(widget, ctk.CTkOptionMenu) and val in ["已勾选", "未勾选"]:
                    # checkbox 三态匹配：兼容布尔值或字符串 "True"/"1" 等
                    is_checked = str(target_val_raw).lower() in ("true", "1", "yes")
                    if (val == "已勾选" and not is_checked) or (val == "未勾选" and is_checked):
                        params_matched = False
                        break
                elif isinstance(widget, ctk.CTkOptionMenu):
                    # combobox 精确匹配
                    if val != target_val:
                        params_matched = False
                        break
                else:
                    # entry, multiline, slider 子串包含匹配
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
        self.actionOption.set("（不限）") # 会自动触发 _onActionChanged 清空参数区
        self.onSearch() # 立即执行一次空搜索

    def _renderResults(self, matchedShortcuts):
        """将匹配结果渲染到结果框中，采用多行卡片式布局"""
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
                action_def = getActionDefByKey(sc_action_key)
                sc_action_display = action_def.displayName if action_def else sc_action_key

                # 渲染基础信息
                self.resultTextbox.insert("end",
                                          f"ID: {sc_id}\n"
                                          f"名字: {sc_name}\n"
                                          f"快捷键: {sc_key}\n"
                                          f"备注: {sc_desc}\n"
                                          f"动作类型: {sc_action_display}\n"
                                          )

                # 渲染动作参数
                sc_params = sc.get('actionParams', {})
                if not sc_params or not action_def:
                    self.resultTextbox.insert("end", "动作参数: （无）\n")
                else:
                    self.resultTextbox.insert("end", "动作参数:\n")
                    # 遍历 ActionDef 里的 ParamSpec 来获取 label，使展示更规范
                    for spec in action_def.params:
                        val = sc_params.get(spec.key, "（未设置）")

                        # 格式化 checkbox 类型的值，方便阅读
                        if spec.widget == "checkbox":
                            if str(val).lower() in ("true", "1", "yes"):
                                val_str = "已勾选"
                            elif str(val).lower() in ("false", "0", "no", ""):
                                val_str = "未勾选"
                            else:
                                val_str = str(val)
                        else:
                            # 对于空的参数值，统一显示 （未设置）
                            val_str = str(val) if val != "" else "（未设置）"

                        self.resultTextbox.insert("end", f"  {spec.label}: {val_str}\n")

                self.resultTextbox.insert("end", "----------------------------------------\n")

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

        # 3. 插入提示语 (如果是具体动作，非"（不限）")
        # 注意："（不限）" 不会触发这个分支，因为 getActionDefByDisplayName("（不限）") 返回 None
        ctk.CTkLabel(
            self.paramsFrame,
            text="提示：参数标注的「必填」为代码复用结果，搜索时可忽略",
            font=("微软雅黑", 10),
            text_color="gray"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(2, 5))

        # 4. 根据定义生成新控件 (从 row=1 开始)
        presetParams = presetParams or {}
        for i, spec in enumerate(actionDef.params):
            current_row = i + 1
            # 生成标签 (满足动态标签需求)
            ctk.CTkLabel(self.paramsFrame, text=spec.label + ":", font=("微软雅黑", 14)).grid(
                row=current_row, column=0, sticky="ne", padx=5, pady=2
            )
            # 生成输入控件
            widget = self._buildParamWidget(spec, presetParams.get(spec.key, spec.default))
            widget.grid(row=current_row, column=1, sticky="nsew", padx=5, pady=2)
            self._paramWidgets[spec.key] = widget

    def _buildParamWidget(self, spec: ParamSpec, initialValue):
        """根据规格生成具体的控件，适配搜索场景的特殊需求"""
        # 多行文本框
        if spec.widget == "multiline":
            w = ctk.CTkTextbox(self.paramsFrame, font=("微软雅黑", 13), height=80)
            # 搜索框默认不回填 initialValue，保持空白表示不过滤
            return w

        # 下拉框 (combobox)
        elif spec.widget == "combobox":
            # 搜索下拉框首项加 "（不限）"，表示不过滤此参数
            options = ["（不限）"] + spec.options
            w = ctk.CTkOptionMenu(self.paramsFrame, values=options, font=("微软雅黑", 13))
            w.set("（不限）")
            return w

        # 复选框 (checkbox) - 退化为三态下拉框
        elif spec.widget == "checkbox":
            # 三态：不限 / 找勾选的 / 找没勾选的
            options = ["（不限）", "已勾选", "未勾选"]
            w = ctk.CTkOptionMenu(self.paramsFrame, values=options, font=("微软雅黑", 13))
            w.set("（不限）")
            return w

        # 滑块 - 退化为文本输入
        elif spec.widget == "slider":
            # 滑块适合设定值，不适合搜索值，退化为文本输入，提示范围
            w = ctk.CTkEntry(self.paramsFrame, font=("微软雅黑", 13), placeholder_text=f"输入数值({spec.from_}-{spec.to})")
            return w

        # 默认单行输入框
        else:
            w = ctk.CTkEntry(self.paramsFrame, font=("微软雅黑", 13), placeholder_text=spec.placeholder)
            return w
