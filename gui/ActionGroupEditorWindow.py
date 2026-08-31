""" 动作组编辑窗口"""
import threading
from tkinter import messagebox

import copy

import customtkinter as ctk

from utils.actionGroupExecutor import ActionGroupPlayer
from utils.actionRegistry import ACTION_REGISTRY, getActionDefByKey, getActionDefByDisplayName

from core.configManager import loadWindowSettings, center_window
from utils.appIcon import applyAppIcon


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
        # 试运行运行中会被置灰（见 _setReorderBtnState）；窗口打开本身是模态的，
        # 与参数编辑/延迟编辑天然互斥，无需额外守卫
        self.reorderBtn = ctk.CTkButton(
            headerFrame, text="⇅ 调整顺序", command=self.openReorderWindow, width=110
        )
        # side="right" 在 addStepBtn 之后 pack，最终排在"添加步骤"左侧
        self.reorderBtn.pack(side="right", padx=(0, 5), pady=5)
        # ==================== 36 号新增：统一设置延迟入口 ====================
        # 批量操作按钮聚在左侧，"+ 添加步骤"保持最右
        self.unifiedDelayBtn = ctk.CTkButton(
            headerFrame, text="⏱ 统一延迟", command=self.openUnifiedDelayEditor, width=110
        )
        self.unifiedDelayBtn.pack(side="right", padx=(0, 5), pady=5)

        self.scrollFrame = ctk.CTkScrollableFrame(listFrame)
        self.scrollFrame.grid(row=1, column=0, sticky="nsew")
        self.scrollFrame.grid_columnconfigure(0, weight=1)

        # === 3. 底部按钮与日志区 ===
        bottomFrame = ctk.CTkFrame(self, fg_color="transparent")
        bottomFrame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkButton(bottomFrame, text="取消", fg_color="#A30000", hover_color="#7A0000", command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(bottomFrame, text="完成", command=self.onSave).pack(side="right", padx=5)
        # ==================== 31 号新增：试运行按钮（双态）====================
        # 状态机：▶ 试运行 →（点击启动）→ ⏹ 停止试运行 →（线程结束，after 轮询恢复）
        # 双态共用一个按钮的理由：试运行会劫持鼠标，紧张时刻还要在界面上
        # 找另一个"停止"按钮是反人性的；原地变色变文案 = 视觉锚点不动。
        self.trialRunBtn = ctk.CTkButton(
            bottomFrame, text="▶ 试运行",
            fg_color="#2B5797", hover_color="#1B3F6B",
            command=self.onTrialRun
        )
        self.trialRunBtn.pack(side="left", padx=5)
        # 试运行运行时状态：
        # _trial_running / _trial_thread 只由 GUI 线程读写；
        # _trial_interrupt 是 GUI 线程与玩家线程的共享句柄（Event 本身线程安全）。
        self._trial_running = False
        self._trial_interrupt: threading.Event | None = None
        self._trial_thread: threading.Thread | None = None
        # 按钮两种形态集中定义，防止恢复/激活两处魔法值漂移
        self._trial_btn_idle = {"text": "▶ 试运行", "fg_color": "#2B5797", "hover_color": "#1B3F6B"}
        self._trial_btn_active = {"text": "⏹ 停止试运行", "fg_color": "#A30000", "hover_color": "#7A0000"}
        # ====================================================================
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
        applyAppIcon(self)

    def destroy(self):
        """窗口销毁前的兜底：试运行还在跑就先发停止信号（31 号新增）。

        背景：本窗口没有屏蔽右上角关闭按钮（无 WM_DELETE_WINDOW 协议），
        用户完全可能在试运行（正劫持鼠标）中直接关窗。不兜底的话：
        玩家线程变孤儿继续劫持鼠标，且日志回调往已销毁的窗口投递。
        发信号后玩家在下一个检查点（≤50ms 延迟分片 / mouseMoveTo 插值步 /
        步间）自然退出；executor 槽位注销由线程侧 finally 完成，
        不依赖本窗口存活。取消按钮 / onSave / 右上角关闭三条路径
        全部经过本方法，一处兜底全覆盖。
        """
        if self._trial_running and self._trial_interrupt is not None:
            self._trial_interrupt.set()
        super().destroy()


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
        """试运行入口（31 号改造：双态按钮 + 全局停止组合接线）。

        双态语义：
          空闲态点击 → 启动试运行（守卫 → 首行警告 → 注册 → 起线程 → 运行态）
          运行态点击 → set local_interrupt（强制停止），随后等线程自然退出，
                       after 轮询恢复按钮 —— GUI 线程绝不 join 子线程。
        """
        # ── 运行态：本按钮此刻就是"⏹ 停止试运行" ──
        if self._trial_running:
            if self._trial_interrupt is not None:
                self._trial_interrupt.set()  # 幂等：重复 set 无害
            return

        # ── 空闲态：启动前守卫 ──
        # 守卫：正式动作组执行中禁止试运行（设计定稿第二节）。
        # 理由有二：a) 两者都模拟按键/劫持鼠标，并发 = 状态机互相污染；
        # b) 停止组合的路由一级（is_busy）优先于二级（试运行），并发时
        #    试运行将无法被全局组合停止 —— 守卫从入口消灭该边界场景。
        #    （顺带修掉旧版"连点试运行开多线程"的现存问题——运行态分支
        #    已把第二次点击吃掉，到不了这里。）
        executor = self._getExecutor()
        if executor is not None and (executor.is_busy or executor.isExecuting):
            messagebox.showwarning(
                "无法试运行",
                "当前有动作组正在执行。\n请等待其结束（或用停止组合 / 托盘停止）后再试运行。",
                parent=self
            )
            return

        self._collectUIData()
        if len(self.steps_data) > 50:
            messagebox.showerror("错误", "步骤数量超过绝对上限 50 步！", parent=self)
            return

        # ── 启动 ──
        # 清空旧日志
        self.logTextbox.configure(state="normal")
        self.logTextbox.delete("1.0", "end")
        self.logTextbox.configure(state="disabled")

        local_interrupt = threading.Event()

        # ==================== 31 号新增：日志首行固定输出 ====================
        # ① 回声警告（只提示不修）：试运行不改 executor 状态，全局快捷键
        #    仍在监听，模拟按键可能触发其他快捷键 —— "能用正是试运行的意义"。
        # ② 停止通道教学。注意：试运行只注册了一个中断事件，所以两条全局
        #    停止组合在试运行期间【都等效于强制停止】（软/硬之分只属于
        #    真实动作组）。
        self._updateLog("⚠ 试运行期间全局快捷键仍在监听，模拟按键可能触发其他快捷键，请留意")
        self._updateLog("  停止方式：再点一次本按钮（⏹），或按全局停止组合（试运行中两条组合均等效于强制停止）")
        self._updateLog(" 试运行基于启动瞬间的步骤快照执行，期间的修改不影响本次运行")

        # ====================================================================

        # 试运行上下文：重写 confirm_callback 自动点"是"（原逻辑不动）
        # ==================== 31 号新增：注入 interrupt_event ====================
        # 激活 mouseMoveTo 平滑移动循环里的硬停检查点（utils/actionHandlers
        # 第一轮已埋，此前试运行没传事件所以不生效）。该事件与注册给
        # executor 的是同一个对象 → 全局停止组合（路由二级）set 的就是它，
        # "点按钮"与"按组合"两条路汇于同一信号，语义天然一致。
        context = {
            "confirm_callback": lambda msg, holder, evt: (holder.__setitem__(0, True), evt.set()),
            "interrupt_event": local_interrupt,
        }
        # ========================================================================

        # ==================== 31 号新增：注册到 executor（路由二级）====================
        # 注册后，全局停止组合在"无动作组执行"时会 set 本事件 —— 试运行
        # 劫持鼠标时按钮点不到，键盘组合是逃生口。注销在本窗口线程体的
        # finally（见 _trialThreadBody），窗口销毁也不影响。
        if executor is not None:
            executor.register_trial_interrupt(local_interrupt)
        # ========================================================================

        player = ActionGroupPlayer(
            copy.deepcopy(self.steps_data),  # ★ 37 号：传启动瞬间的快照而非活引用 ——
            # 修复"试运行期间增删/移动步骤会错乱正在
            # 跑的迭代"的现存隐患，顺序同理被隔离
            self.stopOnErrorOpt.get(),
            context,
            local_interrupt,
            log_callback=self.appendLog,
            confirm_all=False,
            loop_count=int(self.loopCountEntry.get() or 1),
            max_exec_time=int(self.maxExecEntry.get() or 60)
        )

        self._trial_interrupt = local_interrupt
        self._trial_running = True
        self._setReorderBtnState("disabled")  # 37 号：试运行期间锁定排序入口

        self._setTrialButton(self._trial_btn_active)

        self._trial_thread = threading.Thread(
            target=self._trialThreadBody, args=(player, executor), daemon=True
        )
        self._trial_thread.start()
        # after 轮询线程存活（照抄坐标捕获 _poll_mouse_pos 的先例模式），
        # 而不是给 player 加 on_finish 回调 —— 播放器保持零改动。
        t = self._trial_thread
        self.after(200, lambda: self._pollTrialThread(t))

    def _trialThreadBody(self, player, executor):
        """试运行线程体：包一层 try/finally 保证注销（31 号硬要求）。

        finally 必须注销：无论正常结束 / 被停止 / 抛异常，都要清掉 executor
        的单槽引用 —— 否则残留的旧事件会让后续空闲期的停止组合误入路由
        二级（无害但不干净，且语义错位）。注销走的是本线程持有的引用，
        不经过 GUI，窗口已销毁也照常执行。
        """
        try:
            player.play()
        finally:
            if executor is not None:
                executor.unregister_trial_interrupt()

    def _pollTrialThread(self, thread):
        """after 轮询：线程活着就排下一拍，死了就恢复按钮（GUI 线程回调）。"""
        # 防御：窗口可能在试运行中被关掉 —— Tcl 仍会派发已排期的 after
        # 回调，但控件已不存在；直接退出，收尾由线程侧 finally 完成。
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if thread is not None and thread.is_alive():
            self.after(200, lambda: self._pollTrialThread(thread))
            return
        self._onTrialFinished()

    def _onTrialFinished(self):
        """试运行结束（正常 / 停止 / 异常）后恢复按钮。只由 after 回调调用。"""
        self._trial_running = False
        self._trial_interrupt = None
        self._trial_thread = None
        self._setTrialButton(self._trial_btn_idle)
        self._setReorderBtnState("normal")   # 37 号：试运行结束，恢复排序入口


    def _setTrialButton(self, spec):
        """按钮状态的统一写入口，防止多处 configure 漂移。"""
        try:
            self.trialRunBtn.configure(**spec)
        except Exception:
            # 窗口已销毁的最后防线（正常流程被 _pollTrialThread 守卫挡住）
            pass

    def _setReorderBtnState(self, state: str):
        """排序入口按钮的统一写入口（试运行启动/结束两处调用）。
        包一层防御：试运行线程可能晚于窗口销毁才结束，
        与 _setTrialButton 的 try/except 同款理由。"""
        try:
            if hasattr(self, "reorderBtn") and self.reorderBtn.winfo_exists():
                self.reorderBtn.configure(state=state)
        except Exception:
            pass


    def _getExecutor(self):
        """沿 Tk master 链向上找 MainWindow 持有的 executor（31 号新增）。

        为什么不走构造函数传入：本窗口由上游编辑窗打开，改构造签名要连改
        调用方；而 MainWindow.executor 是全局稳定锚点（托盘同款依赖），
        沿 master 链上溯必然经过它。找不到时返回 None —— 两个依赖点
        （忙碌守卫 / 注册）均已判空降级：试运行照常可跑、⏹ 按钮照常可停
        （local 停止不依赖 executor），只是失去全局停止组合通道与忙碌守卫。
        层数上限 10 防异常嵌套下绕圈。
        """
        widget = self.master
        for _ in range(10):
            if widget is None:
                return None
            executor = getattr(widget, "executor", None)
            if executor is not None:
                return executor
            widget = getattr(widget, "master", None)
        return None

    def appendLog(self, msg: str):
        """跨线程日志输出桥梁

        31 号加固：试运行窗口可能先于玩家线程被关闭（窗口没有屏蔽右上角
        关闭按钮）。旧实现直接 self.after —— 控件销毁后 after 抛 TclError，
        会在玩家线程里炸断 play()。包一层防御：窗口没了就丢弃日志
        （玩家侧 finally 仍会正常注销 executor 槽位，资源不泄漏）。
        """
        try:
            self.after(0, lambda: self._updateLog(msg))
        except Exception:
            pass

    def _updateLog(self, msg: str):
        # 已排期的 after 回调可能在窗口销毁后才执行，同样要设防
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
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

    # ==================== 37 号新增：步骤排序功能 ====================

    def openReorderWindow(self):
        """打开步骤排序专用弹窗。
        数据流纪律（设计定稿第六节铁律①②在此，③④在下方与排序窗内）：
        ① 先 flush 备注，再拍快照 —— 编辑窗里未回写的备注不能丢在快照之外；
        ② 快照 deepcopy —— 排序窗全程持有独立副本，与父窗后续任何操作互不干扰。"""
        if not self.steps_data:
            messagebox.showinfo("提示", "当前动作组没有步骤，无需排序。", parent=self)
            return
        self._flushNoteTextboxes()                  # 铁律①：控件序==数据下标序，此刻 flush 安全
        snapshot = copy.deepcopy(self.steps_data)   # 铁律②：独立快照
        win = ReorderStepsWindow(self, snapshot, apply_callback=self._applyReorderResult)
        self.wait_window(win)

    def _applyReorderResult(self, new_order: list):
        """排序窗「完成」的回写口（排序窗 finalize 时调用，本方法在主线程执行）。"""
        # 铁律②（写回侧）：原地切片赋值 —— steps_data 是 _actionGroupData["steps"]
        # 的别名，原地写回让所有既有引用（含 ShortcutEditWindow 侧持有的同一字典）
        # 同步看到新顺序，不依赖 onSave 重新赋值 key 的隐式巧合。
        self.steps_data[:] = new_order
        # 铁律③：此刻父窗的旧行还是旧顺序，默认 flush 会把旧序第 i 行的备注
        # 写进新序第 i 槽 —— 备注全部错位。与 _moveStep 的 flush_notes=False 同款理由。
        self._renderSteps(flush_notes=False)

    # ==================== 36 号新增：统一设置延迟 ====================
    def openUnifiedDelayEditor(self):
        """统一设置所有步骤的「完成后延迟」（36 号）。

        交互流：弹 DelayEditorWindow（与单步延迟编辑共用同一套 UI/毫秒单位/
        旧数据兼容逻辑）→ 弹一次覆盖确认 → 全量写回 → 逐行刷新延迟按钮
        文字 + 重算预估时间。全程不重建行控件。

        设计取舍：
        · 复用 DelayEditorWindow 而非另写弹窗：类型映射、统一毫秒、旧版
          秒→毫秒兼容全在里面，零新 UI 代码；「会覆盖 N 步」的关键信息
          由确认弹窗承载，兼做破坏性批量操作的防呆口。
        · 确认弹窗不可省：这是本窗口唯一的批量覆盖写，一次点击抹掉所有
          步骤的既有延迟，askyesno 给用户最后一眼核对数值与影响面。
        · 不整体重渲染、只刷 _delay_btn 文字：延迟不属于行结构变化，
          重渲染会销毁全部行、打断用户正在敲的备注。与 _openDelayEditor
          单步保存后只改按钮文字的既有口径一致。
          —— 因此这里【不需要】_flushNoteTextboxes：备注框从头到尾没被动过。
        · 逐步 deepcopy：绝不能把同一个 delayAfter 字典对象赋给所有步骤
          （共享可变引用 = 复制步骤一节点名的坑），各步独立持副本，
          未来任何单步编辑/复制都不会串扰。
        · 含已禁用步骤：语义就是"全部"，禁用步骤一并更新，将来重新启用
          时与其余步骤行为一致，不产生隐蔽差异。
        · 不加试运行置灰（与 reorderBtn 不同）：试运行跑的是启动瞬间的
          deepcopy 快照（37 号第七节），此刻改延迟不影响正在跑的轮次。
        """
        if not self.steps_data:
            messagebox.showinfo("提示", "当前动作组没有步骤，无需设置延迟。", parent=self)
            return

        editor = DelayEditorWindow(self, {"type": "none", "value": 0})
        self.wait_window(editor)
        if editor.result is None:
            return  # 用户取消

        new_delay = editor.result
        delay_text = self._delayTypeToText(new_delay)
        value_text = "" if new_delay.get("type") == "none" \
            else f"（{new_delay.get('value', 0)} 毫秒）"

        # if not messagebox.askyesno(
        #         "确认统一设置延迟",
        #         f"将把全部 {len(self.steps_data)} 个步骤（含已禁用）的\n"
        #         f"「完成后延迟」统一设置为：{delay_text}{value_text}\n\n"
        #         f"每个步骤原有的延迟设置都会被覆盖，是否继续？",
        #         parent=self,
        # ):
        #     return

        for step in self.steps_data:
            step["delayAfter"] = copy.deepcopy(new_delay)

        self._refreshAllDelayButtons()
        self._calculateEstimatedTime()  # 没走 _renderSteps，预估时间需手动刷新

    def _delayTypeToText(self, delay_cfg: dict) -> str:
        """delayAfter 配置 → 中文文案。把散落三处的映射字典收拢成单点，
        _createStepRow / _openDelayEditor 里的旧副本可后续顺手迁移。"""
        delay_type_map = {"none": "无延迟", "fixed": "固定时间", "wait_release": "等待释放"}
        return delay_type_map.get(delay_cfg.get("type", "none"), "无延迟")

    def _refreshAllDelayButtons(self):
        """逐行刷新延迟按钮文字（不重建任何行控件）。
        行框取自 _getStepRows()，列表序与 steps_data 下标天然一一对应
        （TODO30b 的 _is_step 标记纪律保证）；照惯例带越界防御。"""
        for i, rf in enumerate(self._getStepRows()):
            if i >= len(self.steps_data):
                break
            rf._delay_btn.configure(
                text=f"⏱ {self._delayTypeToText(self.steps_data[i].get('delayAfter', {}))}"
            )


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

        applyAppIcon(self)
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
        applyAppIcon(self)

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

class ReorderStepsWindow(ctk.CTkToplevel):
    """步骤排序专用弹窗（37 号，设计定稿 v1 + 使用反馈修订 v2）。

    v2 修订（用户实测反馈四点）：
    1. 序号输入改为【显式提交】模型：Enter /「↻ 刷新」才应用，失焦丢弃草稿。
       理由：实测中"失焦即应用"不符合输入习惯——输入后按 Enter 无反应，
       界面纹丝不动，让人以为功能失效；显式提交语义也更清晰。
       「完成」会自动应用焦点框的未提交草稿，不丢输入。
       附带收益：原"失焦触发重渲染 → 拖拽把手死点击"的已知边界自然消失
       （重渲染不再由失焦触发，v1 定稿四.4 可以勾销）。
    2. 正在编辑序号的行持续高亮（FocusIn 起，至提交/失焦止），追踪"在改哪行"。
    3. 移动完成后该行在新位置橙色闪烁 1.2 秒，确认结果。
    4. 拖拽过程画橙色插入指示线（canvas 画线，不影响布局不触重排），
       落点一目了然；边缘自动滚动时同步重画，线始终指向真实落点。
    """

    # ---- 集中常量（防魔法值漂移）----
    ROW_HEIGHT = 44          # 等高行 —— 落点中点判定的前提
    EDGE_PX = 30             # 距列表上/下边缘多少像素内触发自动滚动
    SCROLL_STEP = 0.02       # 自动滚动每拍推进的视图比例（50ms/拍 ≈ 40%每秒）
    DRAG_COLOR = "#3A5A7A"   # 被拖行 / 编辑中行的高亮色（深蓝）
    FLASH_COLOR = "#C97A1A"  # 移动完成后新位置的闪烁色（橙棕）
    FLASH_MS = 1200          # 闪烁持续毫秒数
    DROP_LINE_COLOR = "#FFA500"  # 拖拽插入指示线颜色（橙）
    ROW_HEIGHT = 44  # 行的初始请求高度（备注自适应后，实际行高由内容决定）

    def __init__(self, parent, steps_snapshot: list, apply_callback):
        super().__init__(parent)
        self.title("调整步骤顺序")
        self.geometry("560x520")
        self.minsize(480, 380)
        self.grab_set()  # 模态：与父窗一切编辑操作互斥

        self._applyCallback = apply_callback
        # 重置基准（永不改动）与工作副本（一切渲染/移动只动它）。
        # 父窗传入的已是 deepcopy，这里各再拷一层，让「重置」永远有干净参照
        self._initialOrder = copy.deepcopy(steps_snapshot)
        self._workSteps = copy.deepcopy(steps_snapshot)

        # ---- 运行期状态 ----
        self._rowFrames: list = []      # 当前行框引用（落点判定 / 视觉恢复）
        self._indexEntries: list = []   # 各行序号 Entry 引用（Enter/完成时按行取值）
        self._focusedRowIndex: int = -1  # 当前聚焦序号框所在行（-1 = 无）
        self._dragIndex: int = -1       # 正在拖拽的行下标
        self._dragActive: bool = False  # 拖拽会话总闸（bind_all 回调第一行就查它）
        self._edgeDirection: int = 0    # 自动滚动方向：-1 上 / 0 停 / +1 下
        self._autoScrollJob = None      # 自动滚动 after 任务句柄（单实例）
        self._lastMotionY: int = 0      # 最后一次鼠标屏幕 y（自动滚动时重画指示线用）
        self._dropLineId = None         # 指示线的 canvas item id（None = 未画）
        self._lastMovedIndex: int = -1  # 刚被移动的行在新位置的下标（闪烁用）
        self._flashJob = None           # 闪烁清除 after 句柄（单实例）
        self._noteBoxFocus: bool = False  # 焦点是否压在某行备注只读框上（Enter 守卫用）
        self._rendering: bool = False   # 渲染期重入护栏（见 _renderRows）

        self._buildUI()
        self._renderRows()

        # 应用级鼠标绑定：bind_all 挂在全局 'all' bindtag 上，指针在窗口内任何
        # 控件（含其他行、滚动区）上移动/松开都会进入回调 —— 这是"把手起拖、
        # 全窗落点"的关键，绕开 CTk 控件内部 canvas 吞事件的层级问题。
        # _dragActive 总闸保证非拖拽期零开销；本项目没有其他 'all' 级绑定，
        # destroy 时 unbind_all 不会误伤。
        self.bind_all("<B1-Motion>", self._onGlobalMotion, add="+")
        self.bind_all("<ButtonRelease-1>", self._onGlobalRelease, add="+")
        # v2：窗口级 Enter —— 焦点在任何控件（含序号 Entry 内部 entry）上按
        # Enter 都会冒泡到本窗口的 bindtag。这是序号输入的主提交通道
        self.bind("<Return>", self._onEnterKey)
        # X 关闭键与「完成」同一条 finalize（设计定稿五.4）
        self.protocol("WM_DELETE_WINDOW", self._finalize)
        applyAppIcon(self)

    # ────────────────── UI 构建 ──────────────────

    def _buildUI(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)   # 中部滚动区吃掉全部剩余高度

        # 顶部操作说明（灰色弱化；v2 文案同步显式提交模型）
        ctk.CTkLabel(
            self,
            text="拖动 ☰ 移动（有橙色指示线）；或在序号框输入目标位后按 Enter / 点「刷新」",
            font=("微软雅黑", 12), text_color="gray",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

        # 中部滚动列表
        self.listScroll = ctk.CTkScrollableFrame(self)
        self.listScroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.listScroll.grid_columnconfigure(0, weight=1)

        # 底部按钮：完成最右，重置、刷新依次向左（刷新与 Enter 同一入口）
        btnFrame = ctk.CTkFrame(self, fg_color="transparent")
        btnFrame.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        ctk.CTkButton(btnFrame, text="完成", width=100,
                      command=self._finalize).pack(side="right", padx=5)
        ctk.CTkButton(btnFrame, text="重置", width=100,
                      fg_color="#555555", hover_color="#404040",
                      command=self._onReset).pack(side="right", padx=5)
        # v2：刷新按钮。CTkButton takefocus=0，点击不夺焦点 —— 焦点仍留在
        # 序号框里，所以它和 Enter 行为完全一致（有焦点框就应用其输入）
        ctk.CTkButton(btnFrame, text="↻ 刷新", width=100,
                      command=self._onEnterKey).pack(side="right", padx=5)

    # ────────────────── 行渲染 ──────────────────

    def _renderRows(self):
        """按 _workSteps 当前顺序重建全部行。
        排序窗内的重渲染没有父窗那种 flush 错位风险 —— 持有的是独立快照，
        行控件直接从数据生成、从不回写，天然满足"控件序 == 数据下标序"。
        """
        # 渲染期重入护栏：销毁旧行可能引发迟到的 FocusOut 等事件，
        # 渲染期间一律拒绝移动操作，防止用过期下标改数据
        self._rendering = True
        self._noteBoxFocus = False  # 旧行全部销毁，焦点归属随之清零

        try:
            # 1. 记录滚动位置（重渲染后恢复，防大列表跳顶 —— 设计定稿三.5）
            canvas = self.listScroll._parent_canvas   # 私有 canvas，addStep 已有先例
            try:
                prev_top = canvas.yview()[0]
            except Exception:
                prev_top = 0.0

            # 2. 清空旧行（指示线是 canvas item，随行销毁引用失效，一并复位）
            self._clearDropLine()
            for w in self.listScroll.winfo_children():
                w.destroy()
            self._rowFrames.clear()
            self._indexEntries.clear()

            # 3. 逐行重建（等高行）
            for i, step in enumerate(self._workSteps):
                row = ctk.CTkFrame(self.listScroll, height=self.ROW_HEIGHT, corner_radius=5)
                row.pack(fill="x", pady=2, padx=2)
                # v2.5：去掉 grid_propagate(False)，行高改由内容决定。
                # 落点判定与指示线读的是每行实时几何，从不依赖等高，变高行安全
                row.grid_columnconfigure(3, weight=1)  # 备注列吃掉剩余宽度

                row.grid_columnconfigure(3, weight=1)   # 备注列吃掉剩余宽度

                enabled = step.get("enabled", True)

                # v2.3：刚被移动的行在新位置闪烁高亮（用户要求"能看到结果"）
                if i == self._lastMovedIndex:
                    row.configure(fg_color=self.FLASH_COLOR)

                # 3.1 序号 Entry：FocusIn 高亮所在行；FocusOut 丢弃草稿恢复
                #     显示（v2 显式提交模型，应用只走 Enter/刷新/完成）
                idx_entry = ctk.CTkEntry(row, width=46, justify="center",
                                         font=("微软雅黑", 13))
                idx_entry.insert(0, str(i + 1))
                idx_entry.grid(row=0, column=0, padx=(6, 2), pady=5)
                idx_entry.bind("<FocusIn>",
                               lambda e, idx=i: self._onIndexFocusIn(idx))
                idx_entry.bind("<FocusOut>",
                               lambda e, w=idx_entry, idx=i: self._onIndexFocusOut(w, idx))
                self._indexEntries.append(idx_entry)

                # 3.2 ☰ 拖拽把手：仅此控件响应起拖（整行绑事件会与备注/按钮打架）
                handle = ctk.CTkLabel(row, text="☰", width=28, font=("微软雅黑", 15))
                handle.grid(row=0, column=1, padx=2)
                handle.bind("<Button-1>", lambda e, idx=i: self._onDragStart(idx))

                # 3.3 动作名（定宽；禁用行灰显 + ⛔ 标记）
                action_def = getActionDefByKey(step.get("action", ""))
                name_text = action_def.displayName.split("\n")[0] if action_def else "（无动作）"
                name_label = ctk.CTkLabel(
                    row, text=name_text, width=185, anchor="w", font=("微软雅黑", 13),
                    text_color=("gray" if not enabled else None),
                )
                name_label.grid(row=0, column=2, padx=2, sticky="w")
                if not enabled:
                    name_label.configure(text=name_text + " ⛔")

                # 3.4 备注：多行只读完整展示（v2.5，与父窗备注控件同款风格）
                note_text = str(step.get("note", "")).strip()
                note_box = ctk.CTkTextbox(
                    row, font=("微软雅黑", 12), height=28, border_width=0,
                    fg_color="transparent", text_color="gray",
                    activate_scrollbars=False,
                )
                note_box.insert("1.0", note_text if note_text else "（无备注）")
                # 只读口径：排序窗只管顺序。必须 disabled —— 可编辑的话，
                # 打的字会被任何一次重渲染无声丢弃，是"假编辑"
                note_box.configure(state="disabled")
                note_box.grid(row=0, column=3, sticky="ew", padx=(2, 8), pady=5)
                # 记录焦点归属：Enter 守卫需要知道焦点是否压在备注框里
                note_box.bind("<FocusIn>", lambda e: setattr(self, "_noteBoxFocus", True))
                note_box.bind("<FocusOut>", lambda e: setattr(self, "_noteBoxFocus", False))
                self._adjustNoteBoxHeight(note_box)
                self._rowFrames.append(row)
            # 4. 恢复滚动位置（update_idletasks 让 scrollregion 先算完再 moveto）
            try:
                self.listScroll.update_idletasks()
                canvas.yview_moveto(prev_top)
            except Exception:
                pass

            # 5. v2.3：安排闪烁清除（单实例：再次移动会先取消旧任务）
            if self._lastMovedIndex >= 0:
                if self._flashJob is not None:
                    try:
                        self.after_cancel(self._flashJob)
                    except Exception:
                        pass
                self._flashJob = self.after(self.FLASH_MS, self._clearFlash)
        finally:
            self._rendering = False

    def _clearFlash(self):
        """闪烁到点熄灭。三重防御：该行正被拖拽 / 正被编辑 → 不熄
        （它们各自的恢复路径负责）；行已被销毁 → 静默。"""
        self._flashJob = None
        idx = self._lastMovedIndex
        self._lastMovedIndex = -1
        try:
            if 0 <= idx < len(self._rowFrames) \
                    and not self._dragActive and idx != self._focusedRowIndex:
                self._rowFrames[idx].configure(fg_color="transparent")
        except Exception:
            pass

    def _adjustNoteBoxHeight(self, textbox):
        """按内容行数调整备注框高度（排序窗版，思路同父窗 _adjust_note_height）。
        排序窗备注列比父窗窄，按每行约 16 个中文字符估算折行；
        估多了只是底部留白，估少了行偏矮，都不影响正确性。"""
        content = textbox.get("1.0", "end-1c")
        lines = content.count("\n") + 1
        if len(content) > 16:
            lines += len(content) // 16
        new_height = max(28, (lines * 18) + 12)
        if textbox.cget("height") != new_height:
            textbox.configure(height=new_height)


    # ────────────────── 核心移动原语 ──────────────────

    def _reorder(self, from_index: int, target_index: int) -> bool:
        """核心移动原语（拖拽与改序号共用这一条数据路径 —— 设计定稿四.1）：
        取出 from_index 的步骤，插入到【当前列表】target_index 之前。
        target_index 为 insert-before 语义，合法域 [0, n]（n = 追加到末尾之后）。
        返回是否发生了实际移动。
        """
        n = len(self._workSteps)
        from_index = max(0, min(from_index, n - 1))
        target_index = max(0, min(target_index, n))
        if target_index in (from_index, from_index + 1):
            return False    # 原地（含"紧贴自己下方"），语义上等于没动
        step = self._workSteps.pop(from_index)
        # pop 之后：若 target 在 from 右侧，需 -1 补偿删除带来的整体左移
        insert_at = target_index - 1 if target_index > from_index else target_index
        self._workSteps.insert(insert_at, step)
        # v2.3：记录新位置，渲染后该行闪烁确认
        self._lastMovedIndex = insert_at
        self._renderRows()
        return True

    # ────────────────── 通道一：改序号（显式提交） ──────────────────

    def _onIndexFocusIn(self, row_index: int):
        """序号框获得焦点：所在行持续高亮（v2.2），并记录行号供 Enter 使用。
        CTkButton/CTkLabel 都是 takefocus=0，点击它们不会夺走焦点 ——
        所以高亮会一直保持到提交或点到真正可聚焦的控件为止。"""
        self._focusedRowIndex = row_index
        try:
            self._rowFrames[row_index].configure(fg_color=self.DRAG_COLOR)
        except Exception:
            pass

    def _onIndexFocusOut(self, entry_widget, row_index: int):
        """序号框失焦：丢弃草稿、恢复显示实际序号、取消行高亮。
        v2 取舍（显式提交模型）：失焦 = 放弃本次输入，应用的唯一通道是
        Enter / 刷新 / 完成。好处是没有"半提交"的悬空草稿态，语义唯一。
        _rendering 护栏：渲染销毁旧框时迟到的 FocusOut 直接跳过
        （winfo_exists 防御已销毁场景）。"""
        if self._rendering:
            return
        try:
            if entry_widget.winfo_exists():
                entry_widget.delete(0, "end")
                entry_widget.insert(0, str(row_index + 1))
        except Exception:
            pass
        if self._focusedRowIndex == row_index:
            self._focusedRowIndex = -1
        try:
            # 该行若同时正被拖拽，颜色由拖拽路径负责恢复，这里不动
            if not self._dragActive and 0 <= row_index < len(self._rowFrames):
                self._rowFrames[row_index].configure(fg_color="transparent")
        except Exception:
            pass

    def _onIndexCommit(self, entry_widget, row_index: int):
        """应用某行序号框的输入为"移到第 N 位"。
        v2 起只由 Enter / 刷新 / 完成三条显式路径调用（失焦不再调用）。
        校验规则：空/非数字 → 恢复原值不动；合法数字 → 钳位到 [1, N] 后移位。"""
        def _restore():
            entry_widget.delete(0, "end")
            entry_widget.insert(0, str(row_index + 1))

        raw = entry_widget.get().strip()
        n = len(self._workSteps)
        if not raw or not raw.isdigit():
            _restore()      # 空/非数字 → 恢复原值（设计定稿四.3）
            return
        pos = max(1, min(int(raw), n))    # 钳位到合法区间
        if pos == row_index + 1:
            _restore()      # 目标就是原位：仅恢复显示（顺带吃掉前导 0 等写法）
            return
        # "第 N 位"（最终位置语义）换算为 _reorder 的 insert-before 下标：
        #   f <  N → target = N     （向后移：pop 后插到 N-1 位）
        #   f >= N → target = N - 1 （向前移）
        target = pos if row_index < pos else pos - 1
        self._reorder(row_index, target)

    def _onEnterKey(self, event=None):
        """Enter /「↻ 刷新」的统一入口（v2 主提交通道）。
        两个分支：
        ① 焦点在某行序号框 → 应用该框输入（_reorder 成功即重渲染，
           失败/非法则只恢复显示）；
        ② 焦点不在序号框 → 纯重渲染，对齐显示（按钮名义上的"刷新"语义）。
        注意：row_index 直接用 _focusedRowIndex 是安全的 —— 显式提交模型下
        两次提交之间不可能发生重排，渲染时记录的行号始终有效。"""
        # v2.5 守卫：焦点压在备注只读框上时按 Enter —— 框已 disabled，Enter
        # 无编辑意义；不拦的话窗口级 <Return> 会走纯刷新，把光标所在的
        # 备注框销毁，视觉上像"按 Enter 窗口闪一下"
        if self._noteBoxFocus:
            return

        idx = self._focusedRowIndex
        if 0 <= idx < len(self._indexEntries):
            try:
                if self._indexEntries[idx].winfo_exists():
                    self._onIndexCommit(self._indexEntries[idx], idx)
                    return
            except Exception:
                pass
        self._renderRows()   # 无焦点框：纯刷新对齐

    # ────────────────── 通道二：拖拽 ──────────────────

    def _onDragStart(self, index: int):
        """把手按压：进入拖拽会话。
        只做状态记录与视觉标记，【不重排不重建】—— 拖拽期间渲染会销毁重建控件，
        既打断事件链又破坏"行框 ↔ 数据下标"的对应（设计定稿三.3）。"""
        if self._rendering or not (0 <= index < len(self._workSteps)):
            return
        self._dragIndex = index
        self._dragActive = True
        self._edgeDirection = 0
        try:
            self._rowFrames[index].configure(fg_color=self.DRAG_COLOR)
        except Exception:
            pass
        # 启动自动滚动轮询（单实例：已有任务在跑就不重复起）
        if self._autoScrollJob is None:
            self._autoScrollJob = self.after(50, self._autoScrollTick)

    def _onGlobalMotion(self, event):
        """bind_all 级运动回调：非拖拽期直接返回（总闸）。
        v2 职责两件：更新边缘滚动方向 + 重画插入指示线（v2.4）。"""
        if not self._dragActive or self._rendering:
            return
        self._lastMotionY = event.y_root   # 自动滚动重画线时要复用
        try:
            canvas = self.listScroll._parent_canvas
            rel_y = event.y_root - canvas.winfo_rooty()
            if rel_y < self.EDGE_PX:
                self._edgeDirection = -1
            elif rel_y > canvas.winfo_height() - self.EDGE_PX:
                self._edgeDirection = +1
            else:
                self._edgeDirection = 0
        except Exception:
            self._edgeDirection = 0
        self._updateDropIndicator(event.y_root)

    def _hitTestTarget(self, y_root: int):
        """落点判定（松手提交与运动画线共用这一份逻辑，防两处漂移）：
        指针落在哪一行 → 上半返回 i（插其前）、下半返回 i+1（插其后）；
        不在任何行上返回 None。"""
        for i, rf in enumerate(self._rowFrames):
            try:
                top = rf.winfo_rooty()
                bottom = top + rf.winfo_height()
            except Exception:
                continue
            if top <= y_root <= bottom:
                return i if y_root < (top + bottom) / 2 else i + 1
        return None

    def _updateDropIndicator(self, y_root: int):
        """v2.4：在内部 canvas 上画/移插入指示线。
        为什么画线而不是动态插行让位：插行会触发真实布局重排，与
        "拖拽期间不重建"的铁律冲突；canvas 画线是纯图层，零副作用。
        坐标换算：行的屏幕 y - canvas 屏幕顶部 = 视口内偏移，
        再经 canvasy() 转成 canvas 内容坐标（画出的线随内容滚动）。"""
        try:
            canvas = self.listScroll._parent_canvas
            # 先清旧线
            self._clearDropLine()
            target = self._hitTestTarget(y_root)
            if target is None or not self._rowFrames:
                return
            # 线的 y：target 行的顶边；target == n（追加到末尾）→ 最后一行的底边
            if target < len(self._rowFrames):
                rf = self._rowFrames[target]
            else:
                rf = self._rowFrames[-1]
                # 底边情形：顶边 + 行高（pady 的 2px 误差视觉可忽略）
            screen_offset = rf.winfo_rooty() - canvas.winfo_rooty()
            if target == len(self._rowFrames):
                screen_offset += rf.winfo_height()
            cy = canvas.canvasy(screen_offset)
            self._dropLineId = canvas.create_line(
                4, cy, canvas.winfo_width() - 4, cy,
                fill=self.DROP_LINE_COLOR, width=3,
                       )
        except Exception:
            self._dropLineId = None

    def _clearDropLine(self):
        """删除指示线（防御：canvas 可能已销毁）。"""
        if self._dropLineId is not None:
            try:
                self.listScroll._parent_canvas.delete(self._dropLineId)
            except Exception:
                pass
            self._dropLineId = None

    def _autoScrollTick(self):
        """拖拽期间的边缘自动滚动（50ms 一拍）。
        只滚视图不动行 —— 落点在松手时按指针物理位置判定，
        滚动只是为了让远处的行可见（设计定稿三.5）。
        v2.4：滚动后重画指示线 —— 指针没动但内容滚了，指针下的行已变，
        线必须跟随真实落点（_lastMotionY 记录了最后一次指针位置）。"""
        if not self._dragActive:
            self._autoScrollJob = None    # 拖拽结束，轮询自然熄火
            return
        if self._edgeDirection != 0:
            try:
                canvas = self.listScroll._parent_canvas
                top, _ = canvas.yview()
                canvas.yview_moveto(
                    min(max(top + self.SCROLL_STEP * self._edgeDirection, 0.0), 1.0)
                )
                self._updateDropIndicator(self._lastMotionY)
            except Exception:
                pass
        self._autoScrollJob = self.after(50, self._autoScrollTick)

    def _onGlobalRelease(self, event):
        """bind_all 级松开回调：拖拽会话的唯一提交点。"""
        if not self._dragActive or self._rendering:
            return
        self._dragActive = False
        self._edgeDirection = 0
        self._clearDropLine()

        # 恢复被拖行视觉。v2 防御：若该行正被编辑（焦点还在它的序号框里），
        # 保留编辑高亮色而不是熄灭 —— 两种高亮共用一行时的归属仲裁
        try:
            color = self.DRAG_COLOR if self._dragIndex == self._focusedRowIndex \
                else "transparent"
            self._rowFrames[self._dragIndex].configure(fg_color=color)
        except Exception:
            pass

        # 落点判定（与运动画线共用 _hitTestTarget，线到哪手就落到哪）
        target_index = self._hitTestTarget(event.y_root)
        if target_index is None:
            return    # 松在列表区域之外 → 视为取消本次拖拽
        self._reorder(self._dragIndex, target_index)

    # ────────────────── 收尾 ──────────────────

    def _onReset(self):
        """重置：恢复打开时快照并重渲染自身，不触碰父窗（设计定稿五.3）。
        重置后直接「完成」= 零变化，天然等价于"撤销全部"。
        v2：清掉闪烁标记 —— 旧行号在新列表里无意义。"""
        self._lastMovedIndex = -1
        self._workSteps = copy.deepcopy(self._initialOrder)
        self._renderRows()

    def _finalize(self):
        """「完成」/ X 关闭的统一收尾：把最终顺序写回父窗。
        v2：显式提交模型下唯一的宽容点 —— 焦点框里可能还压着未提交的
        草稿（点「完成」不夺焦点，失焦恢复不会发生），先应用它再写回，
        保证"看到的数字就是生效的顺序"，不丢用户输入。
        其余行的草稿在渲染销毁时自然消失（渲染后框里显示的都是实际序号）。"""
        idx = self._focusedRowIndex
        if 0 <= idx < len(self._indexEntries):
            try:
                if self._indexEntries[idx].winfo_exists():
                    self._onIndexCommit(self._indexEntries[idx], idx)
            except Exception:
                pass
        try:
            if self._applyCallback is not None:
                self._applyCallback(self._workSteps)
        except Exception:
            pass    # 父窗已销毁等极端场景：本窗随之销毁，改动自然丢弃
        self.destroy()

    def destroy(self):
        """收尾兜底：停自动滚动轮询 / 闪烁任务，删指示线，解除应用级鼠标绑定。
        本项目没有其他 'all' 级绑定，unbind_all 不会误伤（见 __init__ 注释）。"""
        self._dragActive = False
        self._edgeDirection = 0
        for job_attr in ("_autoScrollJob", "_flashJob"):
            job = getattr(self, job_attr, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
                setattr(self, job_attr, None)
        self._clearDropLine()
        try:
            self.unbind_all("<B1-Motion>")
            self.unbind_all("<ButtonRelease-1>")
        except Exception:
            pass
        super().destroy()
