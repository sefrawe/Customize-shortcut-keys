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

        # 7. 按钮区 - 只保留搜索和取消按钮
        self.buttonFrame = ctk.CTkFrame(self, fg_color="transparent")
        self.buttonFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(self.buttonFrame, text="搜索", command=self.onSearch).pack(side="left", padx=5)
        ctk.CTkButton(self.buttonFrame, text="取消", fg_color="#A30000", hover_color="#7A0000", command=self.destroy).pack(side="left", padx=5)

        # 初始化时不执行搜索，显示提示信息
        self._show_initial_message()

    def _show_initial_message(self):
        """显示初始提示信息"""
        self.resultTextbox.configure(state="normal")
        self.resultTextbox.delete("1.0", "end")
        self.resultTextbox.insert("end", "请点击「搜索」按钮获取结果")
        self.resultTextbox.configure(state="disabled")

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

        # 3. 收集动作参数搜索条件 (只收集用户填写的)
        param_conditions = {}
        for param_key, widget in self._paramWidgets.items():
            val = ""
            if isinstance(widget, ctk.CTkTextbox):
                val = widget.get("1.0", "end-1c").strip()
            elif isinstance(widget, ctk.CTkOptionMenu):
                val = widget.get()
            elif isinstance(widget, ctk.CTkEntry):
                val = widget.get().strip()

            if val and val != "（不限）":
                param_conditions[param_key] = (widget, val)

        # 4. 判断是否没有任何搜索条件 (全默认状态)
        has_no_conditions = not name and not key and not desc and not actionDef and not param_conditions

        matchedShortcuts = []
        # 5. 遍历快捷键列表进行筛选
        for shortcut in self.config.get("shortcuts", []):
            matched_fields = set()

            # --- 情况 A: 全默认状态，匹配所有 ---
            if has_no_conditions:
                matchedShortcuts.append({"shortcut": shortcut, "matched_fields": matched_fields})
                continue

            # --- 情况 B: 有搜索条件，必须同时满足(AND)所有填写的条件 ---
            is_match = True

            # 5.1 名字匹配
            if name:
                if name in shortcut.get("name", "").lower():
                    matched_fields.add("name")
                else:
                    is_match = False

            # 5.2 快捷键匹配
            if is_match and key:
                norm_key = normalize_key_combination(key)
                norm_sc_key = normalize_key_combination(shortcut.get("keyCombination", ""))
                if norm_sc_key and norm_key in norm_sc_key:
                    matched_fields.add("key")
                else:
                    is_match = False

            # 5.3 备注匹配
            if is_match and desc:
                if desc in shortcut.get("description", "").lower():
                    matched_fields.add("desc")
                else:
                    is_match = False

            # 5.4 动作类型匹配
            if is_match and actionDef:
                if shortcut.get("action", "") == actionDef.key:
                    matched_fields.add("action")
                else:
                    is_match = False

            # 5.5 动作参数匹配
            if is_match and param_conditions:
                sc_params = shortcut.get("actionParams", {})
                for param_key, (widget, val) in param_conditions.items():
                    target_val_raw = sc_params.get(param_key, "")
                    target_val = str(target_val_raw)
                    param_matched = False

                    if isinstance(widget, ctk.CTkOptionMenu) and val in ["已勾选", "未勾选"]:
                        is_checked = str(target_val_raw).lower() in ("true", "1", "yes")
                        if (val == "已勾选" and is_checked) or (val == "未勾选" and not is_checked):
                            param_matched = True
                    elif isinstance(widget, ctk.CTkOptionMenu):
                        if val == target_val:
                            param_matched = True
                    else:
                        if val.lower() in target_val.lower():
                            param_matched = True

                    if param_matched:
                        matched_fields.add(f"param_{param_key}")
                    else:
                        is_match = False
                        break  # 只要有一个参数不匹配，直接跳出参数循环

            # 只有所有填写条件都满足，才加入结果
            if is_match:
                matchedShortcuts.append({"shortcut": shortcut, "matched_fields": matched_fields})

        # 6. 排序
        matchedShortcuts.sort(key=lambda x: self._shortcutSortKey(x["shortcut"]))

        # 7. 渲染结果
        self._renderResults(matchedShortcuts)

    def _renderResults(self, matchedShortcuts):
        """将匹配结果渲染到结果框中，采用多行卡片式布局，带智能高亮"""
        self.resultTextbox.configure(state="normal")
        self.resultTextbox.delete("1.0", "end")

        # --- 1. 配置颜色 Tag ---
        self.resultTextbox.tag_config("key_tag", foreground="#569CD6")  # 键名：淡蓝色
        self.resultTextbox.tag_config("highlight_tag", background="yellow", foreground="black")  # 高亮：黄底黑字

        # --- 2. 收集所有搜索关键词，用于后续高亮 ---
        search_terms = []
        name_val = self.nameEntry.get().strip()
        key_val = self.keyEntry.get().strip()
        desc_val = self.descEntry.get("1.0", "end-1c").strip()
        if name_val: search_terms.append(name_val)
        if key_val: search_terms.append(key_val)
        if desc_val: search_terms.append(desc_val)

        for param_key, widget in self._paramWidgets.items():
            if isinstance(widget, ctk.CTkTextbox):
                val = widget.get("1.0", "end-1c").strip()
            elif isinstance(widget, ctk.CTkOptionMenu):
                val = widget.get()
            elif isinstance(widget, ctk.CTkEntry):
                val = widget.get().strip()
            else:
                val = ""
            if val and val != "（不限）":
                search_terms.append(str(val))

        # --- 3. 辅助函数：插入文本并自动高亮包含的关键词 ---
        # 【修复】：将 matched_fields 作为参数传入，避免错误引用第一条结果的数据
        def insert_text(text, tags=None, is_key=False, field_name=None, current_matched_fields=None):
            start_index = self.resultTextbox.index("end-1c")
            self.resultTextbox.insert("end", text, tags)
            end_index = self.resultTextbox.index("end-1c")

            # 如果是键名，且这个键名对应的字段确实参与了匹配，就高亮
            if is_key and field_name and current_matched_fields:
                if field_name in current_matched_fields:
                    self.resultTextbox.tag_add("highlight_tag", start_index, end_index)

            # 在刚插入的文本范围内搜索关键词并打高亮标签
            for term in search_terms:
                if not term: continue
                pos = self.resultTextbox.search(term, start_index, end_index, nocase=True)
                while pos:
                    term_end = f"{pos}+{len(term)}c"
                    self.resultTextbox.tag_add("highlight_tag", pos, term_end)
                    pos = self.resultTextbox.search(term, term_end, end_index, nocase=True)

        # --- 4. 开始渲染 ---
        if not matchedShortcuts:
            insert_text("未找到匹配的快捷键。")
        else:
            insert_text(f"共找到 {len(matchedShortcuts)} 条匹配\n\n")

            for item in matchedShortcuts:
                sc = item["shortcut"]
                matched_fields = item["matched_fields"]  # 当前项的匹配字段集合

                sc_id = sc.get('id', '')
                sc_name = sc.get('name', '')
                sc_key = sc.get('keyCombination', '')
                sc_desc = sc.get('description', '')
                sc_action_key = sc.get('action', '')

                action_def = getActionDefByKey(sc_action_key)
                if action_def:
                    sc_action_display = action_def.displayName.replace('\n', ' ')
                else:
                    sc_action_display = sc_action_key

                    # 渲染基础信息 (传入 current_matched_fields=matched_fields)
                insert_text("ID: ", "key_tag", is_key=True, field_name="id", current_matched_fields=matched_fields)
                insert_text(f"{sc_id}\n")
                insert_text("名字: ", "key_tag", is_key=True, field_name="name", current_matched_fields=matched_fields)
                insert_text(f"{sc_name}\n")
                insert_text("快捷键: ", "key_tag", is_key=True, field_name="key", current_matched_fields=matched_fields)
                insert_text(f"{sc_key}\n")
                insert_text("备注: ", "key_tag", is_key=True, field_name="desc", current_matched_fields=matched_fields)
                insert_text(f"{sc_desc}\n")
                insert_text("动作类型: ", "key_tag", is_key=True, field_name="action",
                            current_matched_fields=matched_fields)
                insert_text(f"{sc_action_display}\n")

                # 渲染动作参数
                sc_params = sc.get('actionParams', {})
                if not sc_params or not action_def:
                    insert_text("动作参数: ", "key_tag", is_key=True, field_name="params",
                                current_matched_fields=matched_fields)
                    insert_text("（无）\n")
                else:
                    insert_text("动作参数:\n", "key_tag", is_key=True, field_name="params",
                                current_matched_fields=matched_fields)
                    for spec in action_def.params:
                        val = sc_params.get(spec.key, "（未设置）")
                        if spec.widget == "checkbox":
                            if str(val).lower() in ("true", "1", "yes"):
                                val_str = "已勾选"
                            elif str(val).lower() in ("false", "0", "no", ""):
                                val_str = "未勾选"
                            else:
                                val_str = str(val)
                        else:
                            val_str = str(val) if val != "" else "（未设置）"

                        clean_label = spec.label.replace('\n', ' ')
                        insert_text(f" {clean_label}: ", "key_tag", is_key=True, field_name=f"param_{spec.key}",
                                    current_matched_fields=matched_fields)
                        insert_text(f"{val_str}\n")

                insert_text("----------------------------------------\n")

        self.resultTextbox.configure(state="disabled")

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
