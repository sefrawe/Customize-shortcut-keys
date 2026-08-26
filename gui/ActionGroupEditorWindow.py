""" 动作组编辑窗口 (v7 重构版) """
import threading
from tkinter import messagebox

import customtkinter as ctk

from utils.actionGroupExecutor import ActionGroupPlayer
from utils.actionRegistry import ACTION_REGISTRY, getActionDefByKey, getActionDefByDisplayName


class ActionGroupEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, steps_data_full):
        """
        parent: 主编辑窗对象
        steps_data_full: 包含全局参数和步骤列表的完整字典 {_actionGroupData}
        """
        super().__init__(parent)
        self.title("编辑动作组步骤")
        self.geometry("800x700")
        self.minsize(700, 600)
        self.grab_set()  # 模态阻塞

        self.parent = parent
        self.result = None

        # 直接引用主窗口传来的完整数据，不再深拷贝
        # 因为主界面已经去除了全局参数UI，子弹窗成了修改这些数据的唯一入口
        self._actionGroupData = steps_data_full
        self.steps_data = self._actionGroupData.get("steps", [])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)  # 增加权重，让步骤列表区域占据更多空间
        self.grid_rowconfigure(3, weight=1)  # 底部日志保持较小权重

        # === 1. 顶部全局参数区 ===
        topFrame = ctk.CTkFrame(self, fg_color="transparent")
        topFrame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        topFrame.grid_columnconfigure((0, 2, 4, 6), weight=1)

        ctk.CTkLabel(topFrame, text="单步失败时:", font=("微软雅黑", 13)).grid(row=0, column=0, padx=5)
        self.stopOnErrorOpt = ctk.CTkOptionMenu(topFrame, values=["停止整个动作组", "跳过当前步继续"], font=("微软雅黑", 13))
        self.stopOnErrorOpt.set(self._actionGroupData.get("stopOnError", "停止整个动作组"))
        self.stopOnErrorOpt.grid(row=0, column=1, sticky="ew", padx=5)

        ctk.CTkLabel(topFrame, text="循环次数:", font=("微软雅黑", 13)).grid(row=0, column=2, padx=5)
        self.loopCountEntry = ctk.CTkEntry(topFrame, font=("微软雅黑", 13), width=60)
        self.loopCountEntry.insert(0, str(self._actionGroupData.get("loopCount", "1")))
        self.loopCountEntry.grid(row=0, column=3, sticky="ew", padx=5)

        # ==================== 修复Bug1：超时(秒)输入框不再被覆盖 ====================
        # 原代码中 "预估执行时间" 的 label 和 value 放在了 column=5 和 column=6，
        # 与 maxExecEntry(column=5) 和 confirmAllBox(column=6) 发生了 grid 冲突覆盖。
        # 修复：将 "预估执行时间" 移到独立的 row=1，不再与第一行控件争抢位置。
        ctk.CTkLabel(topFrame, text="超时(秒):", font=("微软雅黑", 13)).grid(row=0, column=4, padx=5)
        self.maxExecEntry = ctk.CTkEntry(topFrame, font=("微软雅黑", 13), width=60)
        self.maxExecEntry.insert(0, str(self._actionGroupData.get("maxExecutionTime", "60")))
        self.maxExecEntry.grid(row=0, column=5, sticky="ew", padx=5)

        self.confirmAllBox = ctk.CTkCheckBox(topFrame, text="执行前统一确认", font=("微软雅黑", 13))
        if self._actionGroupData.get("confirmAllAtOnce", False):
            self.confirmAllBox.select()
        self.confirmAllBox.grid(row=0, column=6, padx=5)

        # 预估最少执行时间（总延迟时间）：第二行横跨整行作为独立信息栏
        # 用一个 label 同时显示标题和数值，避免标题/数值分离显得零散
        self.estimatedTimeLabel = ctk.CTkLabel(
            topFrame,
            text="预估最少执行时间（总延迟时间）: 计算中...",
            font=("微软雅黑", 13), text_color="gray"
        )
        self.estimatedTimeLabel.grid(row=1, column=0, columnspan=7, sticky="w", padx=5, pady=(5, 0))

        # =========================================================================

        # === 2. 中部滚动列表区 ===
        listFrame = ctk.CTkFrame(self, fg_color="transparent")
        listFrame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        listFrame.grid_columnconfigure(0, weight=1)
        listFrame.grid_rowconfigure(1, weight=1)

        headerFrame = ctk.CTkFrame(listFrame, fg_color="transparent")
        headerFrame.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(headerFrame, text="动作步骤列表 (按从上到下顺序执行)", font=("微软雅黑", 14, "bold")).pack(side="left")

        # 添加步骤按钮，绑定限制逻辑
        self.addStepBtn = ctk.CTkButton(headerFrame, text="+ 添加步骤", command=self.addStep, width=120)
        self.addStepBtn.pack(side="right", pady=5)

        self.scrollFrame = ctk.CTkScrollableFrame(listFrame)
        self.scrollFrame.grid(row=1, column=0, sticky="nsew")
        self.scrollFrame.grid_columnconfigure(0, weight=1)

        # === 3. 底部按钮与日志区 ===
        bottomFrame = ctk.CTkFrame(self, fg_color="transparent")
        bottomFrame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkButton(bottomFrame, text="取消", fg_color="#A30000", hover_color="#7A0000", command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(bottomFrame, text="保存步骤", command=self.onSave).pack(side="right", padx=5)
        ctk.CTkButton(bottomFrame, text="▶ 试运行", fg_color="#2B5797", hover_color="#1B3F6B", command=self.onTrialRun).pack(side="left", padx=5)

        logLabel = ctk.CTkLabel(self, text="试运行日志:", font=("微软雅黑", 13, "bold"))
        logLabel.grid(row=3, column=0, sticky="sw", padx=15, pady=(10, 0))

        # v7：移除硬编码颜色，跟随主题默认色
        self.logTextbox = ctk.CTkTextbox(self, height=120, font=("微软雅黑", 12), state="disabled")
        self.logTextbox.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self._renderSteps()

        # 初始计算
        self._calculateEstimatedTime()
        # 绑定输入变化事件
        self.stopOnErrorOpt.configure(command=self._calculateEstimatedTime)
        self.loopCountEntry.bind("<KeyRelease>", lambda e: self._calculateEstimatedTime())
        self.maxExecEntry.bind("<KeyRelease>", lambda e: self._calculateEstimatedTime())

    # ==================== 修复Bug3：新增 _getStepRows 方法 ====================
    # 原代码中多处使用 [w for w in self.scrollFrame.winfo_children() if isinstance(w, ctk.CTkFrame)]
    # 来获取步骤行，但 _renderSteps 里创建的 stats_frame 和 empty_frame 也是 CTkFrame，
    # 导致它们被误包含进列表，index 计算偏移，删除/移动步骤时越界报错。
    #
    # 修复方案：给每个步骤行打上 _is_step = True 标记，
    # stats_frame 和 empty_frame 标记为 False，
    # 统一通过此方法过滤，确保只返回真正的步骤行。
    def _getStepRows(self):
        """只返回真正的步骤行控件，排除 stats_frame 和 empty_frame"""
        return [w for w in self.scrollFrame.winfo_children() if hasattr(w, "_is_step") and w._is_step]
    # ======================================================================

    def _getAvailableActions(self):
        """获取允许在动作组中使用的动作"""
        names = []
        for action in ACTION_REGISTRY:
            if action.key == "" or (action.show_in_action_group and action.key != "actionGroup"):
                clean_name = action.displayName.split('\n')[0]
                names.append(clean_name)
        return names

    # 在 _renderSteps 方法中，在 scrollFrame 前添加统计面板
    def _renderSteps(self):
        # 1. 清空并重新渲染所有步骤行
        for widget in self.scrollFrame.winfo_children():
            widget.destroy()

        # 2. 添加步骤统计面板
        stats_frame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
        stats_frame.pack(fill="x", padx=5, pady=(0, 10))

        # ==================== 修复Bug3：标记为非步骤行 ====================
        # 防止 _getStepRows 误将 stats_frame 当作步骤行
        stats_frame._is_step = False
        # =============================================================

        all_steps = self.steps_data
        enabled_steps = [s for s in all_steps if s.get("enabled", True)]
        disabled_count = len(all_steps) - len(enabled_steps)
        stats_text = f"步骤统计：共 {len(all_steps)} 步 | 启用: {len(enabled_steps)} 步 | 禁用: {disabled_count} 步"
        ctk.CTkLabel(stats_frame, text=stats_text, font=("微软雅黑", 12), text_color="gray").pack()

        # 3. 步数硬限制提示
        if len(self.steps_data) >= 50:
            self.addStepBtn.configure(state="disabled", text="已达50步上限")
        else:
            self.addStepBtn.configure(state="normal", text="+ 添加步骤")

        # 在 _renderSteps 中优化空状态
        if not self.steps_data:
            empty_frame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent", border_width=2, border_color="#555555")
            empty_frame.pack(fill="x", expand=True, pady=50, padx=20)

            # ==================== 修复Bug3：标记为非步骤行 ====================
            # 防止 _getStepRows 误将 empty_frame 当作步骤行
            empty_frame._is_step = False
            # =============================================================

            # 添加图标和更友好的文案
            empty_icon = ctk.CTkLabel(empty_frame, text="📝", font=("Arial", 48))
            empty_icon.pack(pady=10)
            empty_label = ctk.CTkLabel(
                empty_frame,
                text="当前动作组为空\n点击右上方按钮添加步骤",
                font=("微软雅黑", 16), text_color="gray", justify="center"
            )
            empty_label.pack(pady=10)

        # 5. 渲染步骤行
        for i, step in enumerate(self.steps_data):
            self._createStepRow(i, step)

        # 重新计算预估时间
        self._calculateEstimatedTime()

    def _createStepRow(self, index, step_data):
        """创建单行步骤 UI (v7 重构)"""
        rowFrame = ctk.CTkFrame(self.scrollFrame, corner_radius=5)
        rowFrame.pack(fill="x", pady=5, padx=5)
        rowFrame.grid_columnconfigure(2, weight=1)  # 让备注列可伸缩

        # ==================== 修复Bug3：标记为步骤行 ====================
        # 这是真正的步骤行，_getStepRows() 会通过此标记识别它
        rowFrame._is_step = True
        # =========================================================

        # 状态判断：是否启用
        is_enabled = step_data.get("enabled", True)
        widget_state = "normal" if is_enabled else "disabled"

        # 1. 序号
        ctk.CTkLabel(rowFrame, text=str(index+1), width=30, font=("微软雅黑", 14, "bold")).grid(row=0, column=0, padx=5)

        # 2. 动作类型下拉框
        action_menu = ctk.CTkOptionMenu(rowFrame, values=self._getAvailableActions(), font=("微软雅黑", 13), width=150, state=widget_state)
        current_action_key = step_data.get("action", "")
        current_action_def = getActionDefByKey(current_action_key)
        if current_action_def:
            action_menu.set(current_action_def.displayName.split('\n')[0])
        else:
            action_menu.set("（无动作）")
            step_data["action"] = ""  # 容错处理
        action_menu.configure(command=lambda val, rf=rowFrame: self._onStepActionChanged(rf, val))
        action_menu.grid(row=0, column=1, padx=5, pady=5)

        # 3. 备注输入框 (升级为多行 Textbox 并实现自适应撑高)
        note_text = step_data.get("note", "")
        note_entry = ctk.CTkTextbox(rowFrame, font=("微软雅黑", 13), height=28, border_width=1, corner_radius=4)
        note_entry.insert("1.0", note_text)
        note_entry.grid(row=0, column=2, sticky="ew", padx=5, pady=5)
        # 绑定自适应高度事件
        note_entry.bind("<KeyRelease>", lambda e, tb=note_entry: self._adjust_note_height(tb))
        note_entry.configure(state=widget_state)
        # 初次渲染也调整一下高度
        self._adjust_note_height(note_entry, init=True)

        # 4. 启用状态复选框 (绑定状态切换事件)
        enabled_check = ctk.CTkCheckBox(rowFrame, text="启用", font=("微软雅黑", 13), command=lambda rf=rowFrame: self._toggle_step_enabled(rf))
        if is_enabled:
            enabled_check.select()
        enabled_check.grid(row=0, column=3, padx=5)

        # 5. 延迟配置按钮 (中文化映射)
        delay_cfg = step_data.get("delayAfter", {"type": "none", "value": 0})
        delay_type_map = {"none": "无延迟", "fixed": "固定时间", "wait_release": "等待释放"}
        delay_text = delay_type_map.get(delay_cfg.get("type", "none"), "无延迟")
        delay_btn = ctk.CTkButton(rowFrame, text=f"⏱ {delay_text}", width=100, font=("微软雅黑", 13), state=widget_state, command=lambda rf=rowFrame: self._openDelayEditor(rf))
        delay_btn.grid(row=0, column=4, padx=5)

        # 6. 参数配置按钮 (状态化：已配置/未配置)
        is_param_configured = bool(step_data.get("actionParams"))
        param_text = "⚙ 参数 (已配置)" if is_param_configured else "⚙ 参数 (未配置)"
        param_color = "#4ECDC4" if is_param_configured else "gray"  # 已配置高亮青色，未配置灰色
        param_btn = ctk.CTkButton(rowFrame, text=param_text, width=130, font=("微软雅黑", 13), fg_color=param_color, hover_color="#3CB8B0", state=widget_state, command=lambda rf=rowFrame: self._openStepParamEditor(rf))
        param_btn.grid(row=0, column=5, padx=5)

        # 7. 排序与删除按钮组
        btn_frame = ctk.CTkFrame(rowFrame, fg_color="transparent")
        btn_frame.grid(row=0, column=6, padx=5)
        ctk.CTkButton(btn_frame, text="↑", width=30, state=widget_state, command=lambda rf=rowFrame: self._moveStep(rf, -1)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="↓", width=30, state=widget_state, command=lambda rf=rowFrame: self._moveStep(rf, 1)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="删", width=30, fg_color="#A30000", hover_color="#7A0000", command=lambda rf=rowFrame: self._deleteStep(rf)).pack(side="left", padx=1)

        # 存储控件引用
        rowFrame._action_menu = action_menu
        rowFrame._note_entry = note_entry
        rowFrame._enabled_check = enabled_check
        rowFrame._param_btn = param_btn
        rowFrame._delay_btn = delay_btn

    def _adjust_note_height(self, textbox, init=False):
        """自适应调整 Textbox 高度"""
        textbox.update_idletasks()
        # 获取当前内容的行数
        content = textbox.get("1.0", "end-1c")
        # 简单计算换行符数量，加上1作为基础行数
        lines = content.count('\n') + 1
        # 如果内容过长导致换行，需要更复杂的计算，这里用简单的字符数估算
        # CTkTextbox 默认宽度大概能容下20个中文字符
        if len(content) > 20:
            lines += len(content) // 20
        new_height = max(28, (lines * 18) + 12)
        if textbox.cget("height") != new_height:
            textbox.configure(height=new_height)

    def _toggle_step_enabled(self, rowFrame):
        """切换步骤启用状态，并触发视觉降级"""
        # ==================== 修复Bug3：使用 _getStepRows 替代 isinstance 过滤 ====================
        row_frames = self._getStepRows()
        # ==========================================================================
        index = row_frames.index(rowFrame)
        is_enabled = bool(rowFrame._enabled_check.get())
        self.steps_data[index]["enabled"] = is_enabled

        # 状态切换
        state = "normal" if is_enabled else "disabled"
        # 由于 OptionMenu/Textbox 的 disabled 状态可能不接收鼠标，这里只做视觉置灰处理
        # 对于按钮，可以直接改 state
        rowFrame._action_menu.configure(state=state)
        rowFrame._note_entry.configure(state=state)
        rowFrame._delay_btn.configure(state=state)
        rowFrame._param_btn.configure(state=state)
        # 排序和删除按钮也需要处理
        for btn in rowFrame.winfo_children()[-1].winfo_children():
            btn.configure(state=state)

        # 重新渲染以更新视觉效果
        self._renderSteps()

    def _onStepActionChanged(self, rowFrame, value):
        """切换动作类型时，清空旧参数并刷新按钮状态 (移除弹窗)"""
        # ==================== 修复Bug3：使用 _getStepRows 替代 isinstance 过滤 ====================
        row_frames = self._getStepRows()
        # ==========================================================================
        index = row_frames.index(rowFrame)
        action_def = getActionDefByDisplayName(value)
        if action_def:
            self.steps_data[index]["action"] = action_def.key
            self.steps_data[index]["actionParams"] = {}  # 动作变了，参数必须清空
            # v7：直接刷新按钮状态为"未配置"，不弹窗打断
            rowFrame._param_btn.configure(text="⚙ 参数 (未配置)", fg_color="gray")

    def _moveStep(self, rowFrame, direction):
        """上移(-1)或下移(1)"""
        # ==================== 修复Bug3：使用 _getStepRows 替代 isinstance 过滤 ====================
        row_frames = self._getStepRows()
        # ==========================================================================
        index = row_frames.index(rowFrame)
        new_index = index + direction
        if 0 <= new_index < len(self.steps_data):
            self.steps_data[index], self.steps_data[new_index] = self.steps_data[new_index], self.steps_data[index]
            self._renderSteps()

    def _deleteStep(self, rowFrame):
        """删除某行"""
        # ==================== 修复Bug3：使用 _getStepRows 替代 isinstance 过滤 ====================
        # 原代码：row_frames = [w for w in self.scrollFrame.winfo_children() if isinstance(w, ctk.CTkFrame)]
        # 问题：stats_frame 和 empty_frame 也是 CTkFrame，会被误包含
        # 导致 index 比实际步骤数大，del self.steps_data[index] 时 IndexError 越界
        row_frames = self._getStepRows()
        # ==========================================================================
        index = row_frames.index(rowFrame)
        del self.steps_data[index]
        self._renderSteps()

    def addStep(self):
        """添加新步骤 (带50步限制)"""
        if len(self.steps_data) >= 50:
            messagebox.showwarning("上限提示", "已达到单次 50 步上限，无法继续添加！", parent=self)
            return
        self.steps_data.append({"action": "", "actionParams": {}, "note": "", "enabled": True})
        self._renderSteps()
        # 滚动到底部
        self.scrollFrame._parent_canvas.yview_moveto(1.0)

    def _collectUIData(self):
        """保存前收集 UI 上的最新数据"""
        # ==================== 修复Bug3：使用 _getStepRows 替代 isinstance 过滤 ====================
        row_frames = self._getStepRows()
        # ==========================================================================
        for i, rf in enumerate(row_frames):
            self.steps_data[i]["note"] = rf._note_entry.get("1.0", "end-1c").strip()
            self.steps_data[i]["enabled"] = bool(rf._enabled_check.get())

    def onSave(self):
        """保存数据并关闭窗口 (加入超时防呆拒绝逻辑，统一毫秒计算)"""
        self._collectUIData()

        # === 超时时间前端校验 (1~120) ===
        max_exec_str = self.maxExecEntry.get().strip() or "60"
        try:
            max_exec_val = int(max_exec_str)
            if max_exec_val > 120:
                messagebox.showwarning("提示", "总超时限制最大为 120 秒，已自动为您调整为 120 秒。", parent=self)
                max_exec_str = "120"
            elif max_exec_val < 1:
                messagebox.showwarning("提示", "总超时限制最小为 1 秒，已自动为您调整为 1 秒。", parent=self)
                max_exec_str = "1"
        except ValueError:
            messagebox.showwarning("提示", "总超时限制必须为整数，已自动为您调整为默认值 60 秒。", parent=self)
            max_exec_str = "60"

        # === v7 核心防呆：预估总延迟时间 > 总超时时间，直接拒绝保存 ===
        loop_count = int(self.loopCountEntry.get().strip() or "1")
        total_delay_ms = 0
        for step in self.steps_data:
            if step.get("enabled", True):
                delay_cfg = step.get("delayAfter", {})
                delay_type = delay_cfg.get("type", "none")
                delay_val = delay_cfg.get("value", 0)

                # ==================== 修改：统一单位为毫秒 ====================
                # 不再区分 fixed 和 wait_release，因为底层存储的都已经是毫秒
                if delay_type in ("fixed", "wait_release"):
                    total_delay_ms += delay_val
                # ============================================================

        # 预估总耗时 (秒) = (总延迟毫秒 / 1000) * 循环次数
        estimated_total_sec = (total_delay_ms / 1000) * loop_count

        if estimated_total_sec > int(max_exec_str):
            messagebox.showerror(
                "❌ 拒绝保存！",
                f"检测到配置的延迟总时间预估为 {estimated_total_sec:.1f} 秒，\n"
                f"已超过设定的总超时限制 {max_exec_str} 秒。\n\n"
                f"快捷键工具定位为短平快操作，不适合配置长时间等待。\n"
                f"请精简步骤、减少延迟，或适当增加总超时时间。",
                parent=self
            )
            return  # 拦截保存操作

        # 打包返回给主编辑窗
        self._actionGroupData["steps"] = self.steps_data
        self._actionGroupData["stopOnError"] = self.stopOnErrorOpt.get()
        self._actionGroupData["loopCount"] = self.loopCountEntry.get().strip() or "1"
        self._actionGroupData["maxExecutionTime"] = max_exec_str
        self._actionGroupData["confirmAllAtOnce"] = bool(self.confirmAllBox.get())
        self.result = self._actionGroupData
        self.destroy()

    def onTrialRun(self):
        """试运行 (逻辑不变，日志框已改跟随主题)"""
        self._collectUIData()
        if len(self.steps_data) > 50:
            messagebox.showerror("错误", "步骤数量超过绝对上限 50 步！", parent=self)
            return
        # 清空旧日志
        self.logTextbox.configure(state="normal")
        self.logTextbox.delete("1.0", "end")
        self.logTextbox.configure(state="disabled")

        local_interrupt = threading.Event()
        # 试运行上下文：重写 confirm_callback 自动点"是"
        context = {"confirm_callback": lambda msg, holder, evt: (holder.__setitem__(0, True), evt.set())}
        player = ActionGroupPlayer(
            self.steps_data,
            self.stopOnErrorOpt.get(),
            context,
            local_interrupt,
            log_callback=self.appendLog,
            confirm_all=False,
            loop_count=int(self.loopCountEntry.get() or 1),
            max_exec_time=int(self.maxExecEntry.get() or 60)
        )
        threading.Thread(target=player.play, daemon=True).start()

    def appendLog(self, msg: str):
        """跨线程日志输出桥梁"""
        self.after(0, lambda: self._updateLog(msg))

    def _updateLog(self, msg: str):
        self.logTextbox.configure(state="normal")
        self.logTextbox.insert("end", msg + "\n")
        self.logTextbox.see("end")
        self.logTextbox.configure(state="disabled")

    def _openStepParamEditor(self, rowFrame):
        """打开当前步骤的参数配置三级弹窗 (移除成功提示)"""
        # ==================== 修复Bug3：使用 _getStepRows 替代 isinstance 过滤 ====================
        row_frames = self._getStepRows()
        # ==========================================================================
        index = row_frames.index(rowFrame)
        display_name = rowFrame._action_menu.get()
        action_def = getActionDefByDisplayName(display_name)
        if not action_def or action_def.key == "":
            messagebox.showwarning("提示", "请先选择一个有效的动作类型！", parent=self)
            return
        current_params = self.steps_data[index].get("actionParams", {})
        editor = StepParamEditorWindow(self, action_def, current_params)
        self.wait_window(editor)
        # v7：保存后不弹成功提示，直接刷新按钮状态
        if editor.result is not None:
            self.steps_data[index]["actionParams"] = editor.result
            # 自动刷新参数按钮为"已配置"状态
            rowFrame._param_btn.configure(text="⚙ 参数 (已配置)", fg_color="#4ECDC4")

    def _openDelayEditor(self, rowFrame):
        """打开延迟配置小窗"""
        # ==================== 修复Bug3：使用 _getStepRows 替代 isinstance 过滤 ====================
        row_frames = self._getStepRows()
        # ==========================================================================
        index = row_frames.index(rowFrame)
        current_delay = self.steps_data[index].get("delayAfter", {"type": "none", "value": 0})
        editor = DelayEditorWindow(self, current_delay)
        self.wait_window(editor)
        if editor.result is not None:
            self.steps_data[index]["delayAfter"] = editor.result
            # 自动刷新延迟按钮文字
            delay_type_map = {"none": "无延迟", "fixed": "固定时间", "wait_release": "等待释放"}
            delay_text = delay_type_map.get(editor.result.get("type", "none"), "无延迟")
            rowFrame._delay_btn.configure(text=f"⏱ {delay_text}")

    def _calculateEstimatedTime(self):
        """计算并显示预估执行时间 (单位统一为毫秒)"""
        try:
            loop_count = int(self.loopCountEntry.get().strip() or "1")
            total_delay_ms = 0
            for step in self.steps_data:
                if step.get("enabled", True):
                    delay_cfg = step.get("delayAfter", {})
                    delay_type = delay_cfg.get("type", "none")
                    delay_val = delay_cfg.get("value", 0)

                    # ==================== 修改：统一单位为毫秒 ====================
                    # 以前 wait_release 存的是秒，需要 * 1000 转换
                    # 现在无论 fixed 还是 wait_release，底层存储的都直接是毫秒，直接相加即可
                    if delay_type in ("fixed", "wait_release"):
                        total_delay_ms += delay_val
                    # ============================================================

            # 将总毫秒数转换为秒，方便用户阅读
            estimated_sec = (total_delay_ms / 1000) * loop_count
            self.estimatedTimeLabel.configure(text=f"预估最少执行时间（总延迟时间）: {estimated_sec:.1f} 秒")
        except (ValueError, ZeroDivisionError):
            self.estimatedTimeLabel.configure(text="计算错误")


class DelayEditorWindow(ctk.CTkToplevel):
    """延迟配置专用弹窗 (统一单位为毫秒)"""

    def __init__(self, parent, current_delay):
        super().__init__(parent)
        self.title("配置完成后的间隔时间")
        self.geometry("350x250")
        self.minsize(350, 250)
        self.grab_set()
        self.result = None
        self.current_delay = current_delay if isinstance(current_delay, dict) else {"type": "none", "value": 0}

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="间隔类型:", font=("微软雅黑", 13)).grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # ==================== 修改：UI层统一展示为毫秒 ====================
        # 以前: ["无延迟", "固定时间 (毫秒)", "等待按键释放 (秒)"]
        # 现在: ["无延迟", "固定时间 (毫秒)", "等待按键释放 (毫秒)"]
        ui_options = ["无延迟", "固定时间 (毫秒)", "等待按键释放 (毫秒)"]
        logic_options = ["none", "fixed", "wait_release"]
        # =============================================================

        current_ui_idx = logic_options.index(self.current_delay.get("type", "none"))
        self.typeOpt = ctk.CTkOptionMenu(self, values=ui_options, font=("微软雅黑", 13))
        self.typeOpt.set(ui_options[current_ui_idx])
        self.typeOpt.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="数值:", font=("微软雅黑", 13)).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.valEntry = ctk.CTkEntry(self, font=("微软雅黑", 13))

        # ==================== 修改：默认值兼容旧版秒的单位 ====================
        # 如果是旧版数据且类型为 wait_release，以前存的是秒，这里乘 1000 转换为毫秒展示
        default_val = self.current_delay.get("value", 500)
        if self.current_delay.get("type", "none") == "wait_release" and default_val <= 10:
            default_val = default_val * 1000
        # =============================================================

        self.valEntry.insert(0, str(default_val))
        self.valEntry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # 增加一个提示标签，提醒用户单位
        ctk.CTkLabel(self, text="* 数值统一按毫秒计算 (1000毫秒=1秒)", font=("微软雅黑", 11), text_color="gray").grid(
            row=2, column=0, columnspan=2, pady=(0, 10))

        ctk.CTkButton(self, text="保存", command=self.onSave).grid(row=3, column=0, columnspan=2, pady=10)

    def onSave(self):
        ui_val = self.typeOpt.get()
        # 反向映射回底层英文标识符
        if "无延迟" in ui_val:
            logic_type = "none"
        elif "固定时间" in ui_val:
            logic_type = "fixed"
        elif "等待" in ui_val:
            logic_type = "wait_release"
        else:
            logic_type = "none"

        self.result = {
            "type": logic_type,
            "value": int(self.valEntry.get().strip() or 0)
        }
        self.destroy()


class StepParamEditorWindow(ctk.CTkToplevel):
    """动作组步骤参数配置三级弹窗 (保持不变)"""
    def __init__(self, parent, action_def, current_params):
        super().__init__(parent)
        self.title(f"配置参数: {action_def.displayName.split(chr(10))[0]}")
        self.geometry("500x400")
        self.minsize(400, 300)
        self.grab_set()
        self.action_def = action_def
        self.result = None
        self._paramWidgets = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scrollFrame = ctk.CTkScrollableFrame(self)
        self.scrollFrame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.scrollFrame.grid_columnconfigure(1, weight=1)

        start_row = 0
        if action_def.hint:
            hint_text = ctk.CTkTextbox(self.scrollFrame, font=("微软雅黑", 12), height=120, wrap="word")
            hint_text.insert("1.0", action_def.hint)
            hint_text.configure(state="disabled")
            hint_text.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 10))
            start_row = 1

        if not action_def.params:
            ctk.CTkLabel(self.scrollFrame, text="该动作没有需要配置的参数。", font=("微软雅黑", 14)).grid(row=start_row, column=0, columnspan=2, pady=50)
        else:
            for i, spec in enumerate(action_def.params):
                current_row = start_row + i
                ctk.CTkLabel(self.scrollFrame, text=spec.label + ":", font=("微软雅黑", 14)).grid(row=current_row, column=0, sticky="ne", padx=5, pady=5)
                widget = self._buildParamWidget(spec, current_params.get(spec.key, spec.default))
                widget.grid(row=current_row, column=1, sticky="nsew", padx=5, pady=5)
                self._paramWidgets[spec.key] = widget

        btnFrame = ctk.CTkFrame(self, fg_color="transparent")
        btnFrame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(btnFrame, text="取消", fg_color="#A30000", hover_color="#7A0000", command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btnFrame, text="保存", command=self.onSave).pack(side="right", padx=5)

    def _buildParamWidget(self, spec, initialValue):
        """根据规格生成具体的控件"""
        if spec.widget == "multiline":
            w = ctk.CTkTextbox(self.scrollFrame, font=("微软雅黑", 13), height=80)
            if initialValue:
                w.insert("1.0", str(initialValue))
            return w
        elif spec.widget == "combobox":
            w = ctk.CTkOptionMenu(self.scrollFrame, values=spec.options, font=("微软雅黑", 13))
            if initialValue:
                w.set(str(initialValue))
            else:
                w.set(spec.options[0] if spec.options else "")
            return w
        elif spec.widget == "checkbox":
            w = ctk.CTkCheckBox(self.scrollFrame, text="", font=("微软雅黑", 13))
            if initialValue:
                w.select()
            return w
        elif spec.widget == "slider":
            container = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
            val_label = ctk.CTkLabel(container, text=str(int(float(initialValue))), font=("微软雅黑", 13, "bold"), width=40)
            val_label.pack(side="right", padx=(5, 0))
            slider = ctk.CTkSlider(container, from_=spec.from_, to=spec.to, command=lambda val, l=val_label: l.configure(text=str(int(val))))
            slider.set(float(initialValue))
            slider.pack(side="left", fill="x", expand=True)
            container._slider = slider
            return container
        elif spec.widget == "dynamic_combobox_schemes":
            from utils.shortcutUtils import getShortcutSchemesNames
            from core.configManager import configDirectory
            current_schemes = ["（无）"] + getShortcutSchemesNames(configDirectory)
            w = ctk.CTkComboBox(self.scrollFrame, values=current_schemes, font=("微软雅黑", 13))
            if initialValue:
                w.set(str(initialValue))
            else:
                w.set("（无）")
            return w
        else:
            w = ctk.CTkEntry(self.scrollFrame, font=("微软雅黑", 13), placeholder_text=spec.placeholder)
            if initialValue:
                w.insert(0, str(initialValue))
            return w

    def onSave(self):
        collected = {}
        for key, widget in self._paramWidgets.items():
            spec = next((p for p in self.action_def.params if p.key == key), None)
            if isinstance(widget, ctk.CTkTextbox):
                val = widget.get("1.0", "end-1c").strip()
            elif isinstance(widget, ctk.CTkCheckBox):
                val = bool(widget.get())
            elif isinstance(widget, ctk.CTkFrame) and hasattr(widget, '_slider'):
                val = str(int(widget._slider.get()))
            else:
                val = widget.get().strip()
            if val == "（无）":
                val = ""
            if spec and spec.required and spec.widget != "checkbox" and not val:
                messagebox.showerror("错误", f"参数 '{spec.label}' 不能为空！", parent=self)
                return
            collected[key] = val
        self.result = collected
        self.destroy()
