""" 动作组编辑窗口 (v7 重构版) """
import threading
from tkinter import messagebox

import copy

import customtkinter as ctk

from utils.actionGroupExecutor import ActionGroupPlayer
from utils.actionRegistry import ACTION_REGISTRY, getActionDefByKey, getActionDefByDisplayName

from core.configManager import loadWindowSettings, center_window

class ActionGroupEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, steps_data_full):
        """ ... """
        super().__init__(parent)
        self.title("编辑动作组步骤（此窗口涉及修改配置文件，不允许最小化和对软件进行其他操作）")

        # ==================== 修改：读取全局配置设置窗口大小 ====================
        self.minsize(700, 600)  # 固定最小尺寸，防止UI崩溃
        win_settings = loadWindowSettings().get("actionGroupWindow", {})
        is_maximized = win_settings.get("maximized", False)
        win_width = win_settings.get("width", 800)
        win_height = win_settings.get("height", 700)

        if is_maximized:
            self.state("zoomed")
        else:
            # 按配置居中显示
            center_window(self, win_width, win_height)
        # ==============================================================

        self.grab_set()  # 模态阻塞

        self.parent = parent
        self.result = None

        # 1. _originalDataRef：父窗口真数据的引用，仅 onSave 时原地写回
        # 2. _initialData：窗口刚打开时的快照，供"重置"按钮恢复用
        # 3. _actionGroupData：工作副本，本窗口所有编辑只改这份
        # 好处：点"取消"直接 destroy 即可，数据从未碰过原件，天然回滚
        self._originalDataRef = steps_data_full
        self._initialData = copy.deepcopy(steps_data_full)
        self._actionGroupData = copy.deepcopy(steps_data_full)
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
        ctk.CTkButton(bottomFrame, text="↺ 重置", fg_color="#555555", hover_color="#404040",command=self._onReset).pack(side="left", padx=5)

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

    def _flushNoteTextboxes(self):
        """TODO30b 核心：把界面上所有备注框的最新内容刷回 steps_data。

        背景：
        备注的唯一真相源曾经是界面控件——用户敲的字只存在于当前行的
        Textbox 里，而 _renderSteps 会销毁全部行并从 steps_data 重建。
        任何触发重渲染的操作(添加/复制/删除/移动...)都会用旧数据
        覆盖未同步的新输入，造成"新建一步就把别步备注弄丢"。

        【调用纪律】本方法要求此刻 控件行序 == steps_data 下标序：
        - ✅ 渲染过程中调用(_renderSteps 内部)：此时还没销毁控件，天然对齐
        - ✅ 增/删/移动操作的开头调用：数据还没被改动，仍然对齐
        - ❌ 数据已被换序/增删之后调用：错位写入(这正是上面调用纪律存在的原因)

        其他约定：
        1. 只回写 note，不回写 enabled —— 启用前必填参数校验依赖
           "_toggle_step_enabled 先校验后写数据"的顺序，在此处顺带写回
           勾选状态会绕过该校验，形成旁路。
        2. 行取自 _getStepRows()，stats_frame/empty_frame 已被标记排除，
           列表序与数据下标天然一一对应，无需 id 匹配。
        """
        for i, rf in enumerate(self._getStepRows()):
            # 防御性断点：正常流程两者等长；防手改 JSON 等异常态越界
            if i >= len(self.steps_data):
                break
            self.steps_data[i]["note"] = rf._note_entry.get("1.0", "end-1c").strip()


    def _getMissingRequiredParams(self, step_data):
        """
        检查某步骤的必填参数是否齐全
        返回缺失项的中文名列表（空列表 = 配置齐全，允许启用）
        """
        action_def = getActionDefByKey(step_data.get("action", ""))

        # 情况1：还没选动作类型（新步骤占位状态），直接视为未配置
        if not action_def or not action_def.key:
            return ["动作类型（尚未选择）"]

        # 情况2：遍历注册表中标记为 required 的参数
        missing = []
        params = step_data.get("actionParams", {})
        for spec in action_def.params:
            # 与 StepParamEditorWindow 的校验口径保持一致：checkbox 类型不参与空值判断
            if spec.required and spec.widget != "checkbox":
                val = str(params.get(spec.key, "")).strip()
                if not val:
                    missing.append(spec.label.replace('\n', ' '))
        return missing


    def _getAvailableActions(self):
        """获取允许在动作组中使用的动作"""
        names = []
        for action in ACTION_REGISTRY:
            if action.key == "" or (action.show_in_action_group and action.key != "actionGroup"):
                clean_name = action.displayName.split('\n')[0]
                names.append(clean_name)
        return names

    def _renderSteps(self, flush_notes=True):
        """重建整个步骤列表区域。

        flush_notes 参数 (TODO30b)：
        - True (默认)：渲染前先把所有行备注框的未保存输入刷回数据，
          让布尔类路径(启用切换/切动作类型)免费获得丢字保护。
        - False：跳过回写，仅供两类调用方使用——
          ① 增删移动类操作：它们已在改数据【之前】自行 flush 过，
             此时控件与数据可能错位，绝不能二次盲写；
          ② _onReset：语义就是丢弃本次修改， flush 反而会把
             残留文本写进刚恢复的干净快照，让重置在备注项上失效。
        """
        # ── TODO30b：唯一渲染期回写口 ──────────────────────────────
        if flush_notes:
            self._flushNoteTextboxes()
        # ───────────────────────────────────────────────────────────

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
        rowFrame._is_step = True
        # =========================================================

        # ==================== 修复死锁：编辑控件不再随"启用状态"锁定 ====================
        # 原逻辑：未启用的步骤，下拉框/备注/延迟/参数按钮全部被置为 disabled，
        # 而新步骤现在默认 enabled=False，导致死循环：
        #   想启用 → 提示先配置参数 → 参数按钮是灰的点不了 → 永远无法启用
        # 修复：编辑控件永远保持 normal，"启用"复选框只控制该步骤是否参与执行
        is_enabled = step_data.get("enabled", True)
        # ========================================================================

        # 1. 序号
        ctk.CTkLabel(rowFrame, text=str(index + 1), width=30, font=("微软雅黑", 14, "bold")).grid(row=0, column=0,
                                                                                                  padx=5)

        # 2. 动作类型下拉框（不再传 state，永远可编辑）
        action_menu = ctk.CTkOptionMenu(rowFrame, values=self._getAvailableActions(), font=("微软雅黑", 13), width=150)
        current_action_key = step_data.get("action", "")
        current_action_def = getActionDefByKey(current_action_key)
        if current_action_def:
            action_menu.set(current_action_def.displayName.split('\n')[0])
        else:
            action_menu.set("（无动作）")
            step_data["action"] = ""  # 容错处理
        action_menu.configure(command=lambda val, rf=rowFrame: self._onStepActionChanged(rf, val))
        action_menu.grid(row=0, column=1, padx=5, pady=5)

        # 3. 备注输入框（永远可编辑）
        note_text = step_data.get("note", "")
        note_entry = ctk.CTkTextbox(rowFrame, font=("微软雅黑", 13), height=28, border_width=1, corner_radius=4)
        note_entry.insert("1.0", note_text)
        note_entry.grid(row=0, column=2, sticky="ew", padx=5, pady=5)
        note_entry.bind("<KeyRelease>", lambda e, tb=note_entry: self._adjust_note_height(tb))
        self._adjust_note_height(note_entry, init=True)

        # 4. 启用状态复选框（保持不变）
        enabled_check = ctk.CTkCheckBox(rowFrame, text="启用", font=("微软雅黑", 13),
                                        command=lambda rf=rowFrame: self._toggle_step_enabled(rf))
        if is_enabled:
            enabled_check.select()
        enabled_check.grid(row=0, column=3, padx=5)

        # 5. 延迟配置按钮（永远可点击）
        delay_cfg = step_data.get("delayAfter", {"type": "none", "value": 0})
        delay_type_map = {"none": "无延迟", "fixed": "固定时间", "wait_release": "等待释放"}
        delay_text = delay_type_map.get(delay_cfg.get("type", "none"), "无延迟")
        delay_btn = ctk.CTkButton(rowFrame, text=f"⏱ {delay_text}", width=100, font=("微软雅黑", 13),
                                  command=lambda rf=rowFrame: self._openDelayEditor(rf))
        delay_btn.grid(row=0, column=4, padx=5)

        # 6. 参数配置按钮（永远可点击）
        is_param_configured = bool(step_data.get("actionParams"))
        param_text = "⚙ 参数 (已配置)" if is_param_configured else "⚙ 参数 (未配置)"
        param_color = "#4ECDC4" if is_param_configured else "gray"
        param_btn = ctk.CTkButton(rowFrame, text=param_text, width=130, font=("微软雅黑", 13),
                                  fg_color=param_color, hover_color="#3CB8B0",
                                  command=lambda rf=rowFrame: self._openStepParamEditor(rf))
        param_btn.grid(row=0, column=5, padx=5)

        # 7. 排序与删除按钮组（永远可点击）
        btn_frame = ctk.CTkFrame(rowFrame, fg_color="transparent")
        btn_frame.grid(row=0, column=6, padx=5)
        ctk.CTkButton(btn_frame, text="↑", width=30, command=lambda rf=rowFrame: self._moveStep(rf, -1)).pack(
            side="left", padx=1)
        ctk.CTkButton(btn_frame, text="↓", width=30, command=lambda rf=rowFrame: self._moveStep(rf, 1)).pack(
            side="left", padx=1)
        ctk.CTkButton(btn_frame, text="复制", width=30, command=lambda rf=rowFrame: self._copyStep(rf)).pack(side="left",padx=1)
        ctk.CTkButton(btn_frame, text="删除", width=30, fg_color="#A30000", hover_color="#7A0000",command=lambda rf=rowFrame: self._deleteStep(rf)).pack(side="left", padx=1)

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
        """切换步骤启用状态 (只改数据 + 刷新统计栏，不再锁定编辑控件)"""
        row_frames = self._getStepRows()
        index = row_frames.index(rowFrame)
        is_enabled = bool(rowFrame._enabled_check.get())

        # 启用前必填参数校验（保持不变）
        if is_enabled:
            missing = self._getMissingRequiredParams(self.steps_data[index])
            if missing:
                messagebox.showwarning(
                    "无法启用",
                    "该步骤存在未配置的必填项，无法启用：\n\n"
                    + "\n".join(f"• {m}" for m in missing)
                    + "\n\n请先点击「⚙ 参数」补全配置，再回来勾选启用。",
                    parent=self
                )
                rowFrame._enabled_check.deselect()
                return

        self.steps_data[index]["enabled"] = is_enabled

        # TODO30b：原先这里手动同步了单行 note 才敢渲染，现已废弃——
        # 布尔翻转不动列表结构，控件↔数据仍对齐，交由 _renderSteps
        # 默认 flush 统一处理(还能顺带保护其他行的未保存备注)。
        self._renderSteps()

    def _onStepActionChanged(self, rowFrame, value):
        """切换动作类型时，清空旧参数并刷新按钮状态 (移除弹窗)"""
        row_frames = self._getStepRows()
        index = row_frames.index(rowFrame)
        action_def = getActionDefByDisplayName(value)
        if action_def:
            self.steps_data[index]["action"] = action_def.key
            self.steps_data[index]["actionParams"] = {}  # 动作变了，参数必须清空

        # 参数刚被清空，若该步骤此前处于启用状态，
        # 会绕过"启用前校验"直接以空参数执行，所以这里强制禁用
        was_enabled = self.steps_data[index].get("enabled", False)
        self.steps_data[index]["enabled"] = False

        # v7：直接刷新按钮状态为"未配置"，不弹窗打断
        rowFrame._param_btn.configure(text="⚙ 参数 (未配置)", fg_color="gray")

        # 仅当步骤原本启用才需整行重建（同步勾选等视觉状态）；
        # 未启用则不必重渲染，避免打断用户在其他行正在进行的输入。
        # TODO30b 两处清理：
        # ① 原"强制禁用后需要重新渲染…"重复注释 ×2 已去重
        # ② 原来只有 was_enabled 分支里手动补写单行 note，现由
        #    _renderSteps 默认 flush 全量接管，条件遗漏不再可能。
        if was_enabled:
            self._renderSteps()

    def _moveStep(self, rowFrame, direction):
        """上移(-1)或下移(1)"""
        # ==== TODO30b：必须先于任何数据变更 flush ====
        # 下面马上要对 steps_data 做交换，交换后再 flush 就会错位
        # (A行的备注写进B的数据槽)，所以趁控件↔数据还严格对齐先回写。
        self._flushNoteTextboxes()

        row_frames = self._getStepRows()
        index = row_frames.index(rowFrame)
        new_index = index + direction
        if 0 <= new_index < len(self.steps_data):
            self.steps_data[index], self.steps_data[new_index] = \
                self.steps_data[new_index], self.steps_data[index]
            # 本函数已在开头自行 flush，此处必须关掉渲染期的二次盲写
            self._renderSteps(flush_notes=False)

    def _copyStep(self, rowFrame):
        """复制当前行步骤一份，插入到其正下方。(原有规格注释见原文件，此略)"""
        # ==== TODO30b：insert 会让插入点之后的下标全体偏移 ====
        # 必须趁复制发生前回写；这样刚敲了半截的备注也会被
        # deepcopy 进复制体——符合"所见即所得"，是预期行为。
        self._flushNoteTextboxes()

        row_frames = self._getStepRows()
        index = row_frames.index(rowFrame)

        if len(self.steps_data) >= 50:
            messagebox.showwarning("上限提示", "已达到单次 50 步上限，无法继续复制！", parent=self)
            return

        new_step = copy.deepcopy(self.steps_data[index])
        self.steps_data.insert(index + 1, new_step)
        self._renderSteps(flush_notes=False)  # 理由同 _moveStep

    def _deleteStep(self, rowFrame):
        """删除某行"""
        # ==== TODO30b：del 会缩短数据表，之后 flush 会整体错位 ====
        # 且删除点的 flush 必须发生在删除前，否则该行本身的未保存
        # 备注随手一起消失(用户可能只是想删行，不想连带丢别的行的字)。
        self._flushNoteTextboxes()

        row_frames = self._getStepRows()
        index = row_frames.index(rowFrame)
        del self.steps_data[index]
        self._renderSteps(flush_notes=False)  # 理由同 _moveStep

    def addStep(self):
        """添加新步骤 (带50步限制)"""
        if len(self.steps_data) >= 50:
            messagebox.showwarning("上限提示", "已达到单次 50 步上限，无法继续添加！", parent=self)
            return
        # ==== TODO30b：append 本身不打乱既有下标，但顺手在此统一 ====
        # 四个结构型操作口径一致：都"先flush→再动数据→关渲染期flush"，
        # 未来维护者不需要逐个记忆哪个安全哪个危险。
        self._flushNoteTextboxes()

        self.steps_data.append({"action": "", "actionParams": {}, "note": "", "enabled": False})
        self._renderSteps(flush_notes=False)
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


        # 打包返回给主编辑窗（先把顶部控件值收集进工作副本）
        self._actionGroupData["steps"] = self.steps_data
        self._actionGroupData["stopOnError"] = self.stopOnErrorOpt.get()
        self._actionGroupData["loopCount"] = self.loopCountEntry.get().strip() or "1"
        self._actionGroupData["maxExecutionTime"] = max_exec_str
        self._actionGroupData["confirmAllAtOnce"] = bool(self.confirmAllBox.get())
        # 保持对象引用不变，父窗口其他地方持有的引用无感知地拿到最新数据
        self._originalDataRef.clear()
        self._originalDataRef.update(self._actionGroupData)
        self.result = self._originalDataRef
        self.destroy()

    def _onReset(self):
        """重置：丢弃本次打开窗口以来的所有未保存修改，恢复到打开时的状态"""
        # （原有的确认弹窗注释保持原样不动）
        # if not messagebox.askyesno(...): return

        # 1. 从快照恢复工作数据（注意重新取 steps 引用，避免指向旧列表）
        self._actionGroupData = copy.deepcopy(self._initialData)
        self.steps_data = self._actionGroupData.get("steps", [])

        # 2. 同步恢复顶部全局配置控件的显示（原代码不变，省略）

        # 3. 重新渲染步骤列表
        # ==== TODO30b：此处必须 flush_notes=False ====
        # 此刻 self.steps_data 已指向刚恢复的快照副本，屏幕上的旧行
        # 属于"即将销毁的残影"；若默认 flush，会把残影里的文字写进
        # 干净的快照，导致"重置后备注居然还在"的事故。
        # 重置语义 = 全盘丢弃，故显式豁免。
        self._renderSteps(flush_notes=False)

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
