"""动作组回放器：在子线程中按顺序执行各个步骤"""
import time
import threading
from utils.actionRegistry import getActionDefByKey

class ActionGroupPlayer:
    """
    动作组回放器：支持循环、超时、试运行日志与硬中断
    它是动作组执行的核心引擎，独立于 Tkinter UI 运行。
    """
    def __init__(self, steps: list, stop_on_error: str, context: dict | None = None,
                 interrupt_event=None,soft_stop_event=None, log_callback=None, confirm_all=False,
                 loop_count=1, max_exec_time=60):
        self.steps = steps
        self.stop_on_error = stop_on_error
        self.context = context or {}
        # 跨线程中断事件：如果从外部(如托盘)设置了该事件，回放器会在下一步前或休眠中被唤醒并终止
        self.hard_interrupt_event = interrupt_event if interrupt_event else threading.Event()
        # 平滑中断事件：收到信号后，允许当前步执行完毕，在进入下一步前退出
        self.soft_stop_event = soft_stop_event if soft_stop_event else threading.Event()
        # 日志回调：如果有(通常是试运行时传入)，则把执行过程实时输出到 UI；如果没有则打印到控制台
        self.log_callback = log_callback
        # 是否在执行前统一确认所有危险命令
        self.confirm_all = confirm_all
        self.loop_count = int(loop_count)

        try:
            # 尝试转换为整数
            parsed_time = int(max_exec_time)
        except (ValueError, TypeError):
            # 如果转换失败（如输入了字母或为空），使用默认值 60
            parsed_time = 60

        # 强制钳制在 1 到 120 秒之间，防止用户手改 JSON 设置过大导致死机
        self.max_exec_time = max(1, min(parsed_time, 120))

        # 记录开始时间，用于超时判断
        self.start_time = 0
        # 定位说明：
        # 本功能解决"正式执行零反馈"盲区 —— 所有 _log 只进控制台(print)，
        # 打包(pythonw 启动)后控制台不存在，用户对"为什么停了/有没有跳过"完全无知。
        #
        # 采集原则：
        # ① 只采异常态，不采正常流：禁用步骤跳过 / 统一确认取消 / 干净的手动停止
        #   一律不入账，避免通知疲劳训练出"看到弹窗就关"的肌肉记忆；
        # ② 存二元组 (category, message) 而非裸字符串：format 阶段要按类别给出
        #   针对性建议文案，靠正则反推太脆；
        # ③ 本模块只负责采集与格式化，是否弹窗、何时弹窗由上层
        #   (actionHandlers.doActionGroup 收尾段) 决定 —— 职责分离，方便日后
        #   把同样的数据喂给日志页或落盘而不必改这里。
        #
        # 四个合法类别及对应场景：
        #   invalid_action : 步骤引用了注册表中不存在的动作名
        #   step_exception : 动作 handler 执行中抛出了异常
        #   timeout        : 总执行时长超过 max_exec_time 被强制截断
        #   startup_reject : 还没开跑就被拦下（如超 50 步硬上限），整个动作组未执行
        self.error_report: list[tuple[str, str]] = []
        # 是否发生了内部超时截断。为什么要单独标记：超时的实现是拉高
        # hard_interrupt_event（借用了用户的强制停止信号通道），如果只看
        # 该事件的状态，将无法区分"到点了自然停"和"用户按了急停"，
        # 导致报告张冠李戴。有此标志后，凡见事件置位且本标志为 True，
        # 一律归因超时而非人为干预。
        self.timed_out: bool = False
        # 是否确认为"来自用户"的中断（托盘按钮）。判定口诀：
        # 事件置位 且 timed_out 为 False → 就是人手按的。
        self.user_interrupted: bool = False
        # 当前正在执行的轮次（从 1 起），用于让报告能精确定位到
        # "第 N 轮·第 M 步"。play() 每进入一轮循环就覆写一次。
        self.current_loop: int = 0


    def _log(self, msg: str):
        """统一日志输出入口，保证线程安全(若操作UI需回调主线程)"""
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    def play(self):
        """开始按顺序执行步骤"""
        # 1. 规模限制：超过50步绝对上限，拒绝执行，防止配置错误导致内存爆炸
        if len(self.steps) > 50:
            self._log("❌ 错误：步骤数量超过绝对上限 50 步，拒绝执行！")
            # 此类拦截原先也走 _log 哑管道，正式执行下用户同样看不见，
            #   与运行期错误同病同理，一并纳入报告体系（决策②：并入同管道）。
            #   区别在于它一条有效步骤都没跑 —— 格式化方法会据此用更短的模板。
            self.error_report.append(
                ("startup_reject", "步骤数量超过绝对上限 50 步，动作组整体被拒绝启动。")
            )
            return

        # 2. 全局统一确认：如果是正式执行(非试运行)且勾选了统一确认，先收集所有命令弹一次窗
        if self.confirm_all and not self.log_callback:
            if not self._check_all_commands():
                self._log("用户取消了全局确认，动作组中止。")
                return

        # 2.5 记录计时起点：超时检测以这里为基准
        # （为何不能省：start_time 若保持初值 0，epoch 差值必然超过上限，
        #   所有动作组会被误判为秒超时，一句都跑不了）
        self.start_time = time.time()

        # 3. 循环执行逻辑
        for loop_idx in range(self.loop_count):
            #  记录当前轮次，供后续错误报告中拼接精确定位前缀
            self.current_loop = loop_idx + 1
            # 每一轮开始前检查中断信号
            if self.hard_interrupt_event.is_set():
                # 归因判定 —— 事件置位且无超时记录，才认定为用户主动中断。
                #   若 timed_out 为真，这里的 break 其实只是超时截断的余波，
                #   不能重复归类成人手操作。
                if not self.timed_out:
                    self.user_interrupted = True
                self._log("⛔ 收到硬中断信号，强制停止回放。")
                break
            if self.soft_stop_event.is_set():
                if not self.timed_out:
                    self.user_interrupted = True
                self._log("⏸ 收到平滑停止信号，动作组在当前步完成后终止。")
                break
            if self.loop_count > 1:
                self._log(f"--- 开始第 {loop_idx + 1}/{self.loop_count} 轮执行 ---")
            self._execute_steps()

        self._log("✅ 动作组回放流程结束。")

    def _check_all_commands(self) -> bool:
        """收集所有 customCommand 步骤的命令，弹出统一确认框"""
        commands = []
        for step in self.steps:
            if not step.get("enabled", True): continue
            if step.get("action") == "customCommand":
                cmd = step.get("actionParams", {}).get("command", "")
                if cmd: commands.append(cmd)

        if not commands: return True

        # 获取跨线程确认回调
        confirm_callback = self.context.get("confirm_callback")
        if not confirm_callback: return True # 无回调直接放行

        # 组装消息并阻塞子线程等待用户点击
        msg = "即将执行以下命令组合:\n" + "\n---\n".join(commands)
        event = threading.Event()
        result_holder = [False]
        confirm_callback(msg, result_holder, event)
        event.wait() # 阻塞直到主线程唤醒
        return result_holder[0]

    def _execute_steps(self):
        """执行单轮所有的步骤"""
        total_steps = len(self.steps)
        for i, step in enumerate(self.steps):
            # 1. 超时检测：如果总耗时超过设定值，强制拉高中断事件并退出
            if time.time() - self.start_time > self.max_exec_time:
                self._log(f"⏰ 达到最大超时时间 {self.max_exec_time}s，强制终止！")
                # ★ 新增：超时算不算失败报告？算。"为什么提前停了"正是最贵的一类盲区。
                #   先打标再拉事件，顺序不能反 —— 归因逻辑依赖这个标志判断
                #   "刚才看到的置位到底是超时还是人手"。
                self.timed_out = True
                self.hard_interrupt_event.set()
                # 入账时会自动拼上"进行到哪一步了"，截断处的上下文由外部
                # getFormattedReport 通过 self.current_loop 与本次中断位置还原，
                # 此处不必写死坐标，减少重复维护成本。
                self.error_report.append(
                    ("timeout", f"总执行时长超过 {self.max_exec_time}s 设定上限，流程被强制截断")
                )
                break

            # 2. 外部强制中断检测
            if self.hard_interrupt_event.is_set():
                self._log("⛔ 收到硬中断信号，强制停止。")
                break
            if self.soft_stop_event.is_set():
                self._log("⏸ 收到平滑停止信号，终止后续步骤。")
                break

            # 3. 跳过被禁用的步骤
            if not step.get("enabled", True):
                self._log(f"步骤 {i+1}/{total_steps} 已禁用，跳过。")
                continue

            action_key = step.get("action", "")
            action_params = step.get("actionParams", {})
            note = step.get("note", "")

            # 跳过空动作
            if not action_key:
                self._log(f"步骤 {i+1}/{total_steps} 动作类型为空，跳过。")
                continue

            self._log(f"[{time.strftime('%H:%M:%S')}] 执行步骤 {i+1}/{total_steps}: {note} ({action_key})...")

            # 3.5 构建本步专用的 context 拷贝：
            # 为何要拷贝而不是直接用 self.context —— 防止某个 handler 在
            # 运行中往 context 写临时键，污染同组后续步骤的执行环境；
            # （如果动原始文件时这里有额外的注入逻辑，以你手头未改动前的
            #   版本为准恢复，不要凭空新增）
            local_context = dict(self.context)



            # 4. 获取动作定义和处理器
            action_def = getActionDefByKey(action_key)
            if not action_def or not action_def.handler:
                err_msg = f"步骤 {i+1} 的动作 '{action_key}' 无效或未注册。"
                self._log(f"❌ 错误捕获: {err_msg}")
                self._recordError(
                    "invalid_action",
                    f"动作 '{action_key}' 无效或未注册",
                    i, note,
                )
                if self._handle_error(err_msg):
                    break
                else:
                    continue

            # 5. 核心执行：调用 handler（注意只此一处，别再有第二个）
            try:
                action_def.handler(action_params, local_context)

                self._log(f" -> ✅ 完成")
            except Exception as e:
                err_msg = f"步骤 {i+1} 执行出错: {str(e)}"
                self._log(f"❌ 错误捕获: {err_msg}")
                self._recordError("step_exception", str(e), i, note)
                if self._handle_error(err_msg):
                    break
                else:
                    continue

            # 6. 执行步骤间延迟 —— 只有成功路径会自然流到这里，
            #    失败路径均已 break/continue 提前退出，不会多等一次。
            # 修复说明：此调用曾在错误报告机制的合并中被意外裁掉，导致所有
            # delayAfter 配置失效、步骤节奏消失；统一复用 _apply_delay 的
            # 分片休眠实现（其内部每 50ms 检查一次中断事件）。
            self._apply_delay(step.get("delayAfter"))

    def _handle_error(self, msg: str) -> bool:
        """错误处理策略：返回 True 表示需要中断，False 表示跳过继续"""
        if self.stop_on_error == "停止整个动作组":
            return True
        return False

    def _apply_delay(self, delay_config: dict | None):
        """执行步骤间的延迟。采用分片休眠，保证休眠期间能响应外部中断事件 (统一毫秒)"""
        if not delay_config or delay_config.get("type", "none") == "none":
            time.sleep(0.1)  # 默认极短延迟，防止动作过快系统反应不过来
            return

        delay_type = delay_config.get("type", "none")
        # 无论 fixed 还是 wait_release，拿到的 value 都直接是毫秒
        # 强制转换为 float，解决 IDE 静态类型检查的格式化警告，并防止用户手改 JSON 填错类型导致崩溃
        try:
            value_ms = float(delay_config.get("value", 0))
        except (ValueError, TypeError):
            value_ms = 0.0

        if delay_type in ("fixed", "wait_release") and value_ms > 0:
            # 如果是等待释放，给个日志提示，方便调试
            if delay_type == "wait_release":
                # 日志里转换为秒显示，方便人类阅读
                self._log(f"等待 {value_ms / 1000:.1f}s...")

            # 分片休眠，每 50ms 醒来检查一次是否被中断
            slept = 0
            while slept < value_ms:
                if self.hard_interrupt_event.is_set() or self.soft_stop_event.is_set():
                    break
                time.sleep(0.05)
                slept += 50

    def _recordError(self, category: str, message: str, step_index: int, note: str):
        """往 error_report 里追加一条结构化的异常记录。

        为何单独抽函数而不是三处各自拼字符串：
        · 定位前缀 "第N轮·步骤M" 的拼接规则在此集中一处，未来想改成"绝对秒偏移"
          或加上"来源于哪个方案"等上下文，只需改这一个函数；
        · 自动带上步骤备注（note），让用户不用回编辑器数序号就知道坏在哪一步。

        参数:
            category   : 四个合法类别之一（见 __init__ 顶部注释）
            message    : 异常的具体描述（不含位置前缀，前缀在这里统一拼）
            step_index : 当前步骤在 steps 列表中的下标（0-based）
            note       : 该步骤的备注字段，可为空字符串
        """
        # 组装形如 "第2轮·步骤5『粘贴网址』" 的定位前缀；
        # 没填备注就不显示『』，保持输出清爽。
        loc = f"第{self.current_loop}轮·步骤{step_index + 1}"
        if note:
            loc += f"『{note}』"
        self.error_report.append((category, f"{loc}: {message}"))

    def getFormattedReport(self) -> str | None:
        """将累计的错误记录整理成适合 messagebox 展示的多行文本。

        返回值语义严格划分：
        · None  → 没有任何需要告知用户的事（含"干净的手动停止"），
                  调用方必须据此跳过弹窗，绝不能拿去渲染空字符串标题栏；
        · str   → 有值得说明的情况，调用方直接弹窗即可。

        判空在函数最顶端完成，隐式实现了三条静默规则：
        ① 全部成功 → 不弹；② 主动停止且无前置错误 → 不弹；
        ③ 用户自己取消统一确认 → play() 里根本没走到收集，天然为空。
        """
        if not self.error_report:
            return None

        # ---------- 防爆围栏常量 ----------
        # 明细最多列 8 条：循环次数 × 每轮多处失败的组合能把弹窗撑到超屏。
        MAX_DETAIL_LINES = 8
        # 总字符上限约 1500：普通桌面 messagebox 在此规模内仍流畅可读，
        # 极限情况下靠末尾的截断提示兜底。
        MAX_TEXT_LENGTH = 1500

        lines: list[str] = []

        # ---------- 标题 ----------
        lines.append(f"⚠ 本次执行中出现 {len(self.error_report)} 处异常：")
        lines.append("")

        # ---------- 明细 ----------
        for _, msg in self.error_report[:MAX_DETAIL_LINES]:
            lines.append(f"• {msg}")
        omitted = len(self.error_report) - MAX_DETAIL_LINES
        if omitted > 0:
            lines.append(f"…（另有 {omitted} 条相同性质的记录已省略）")

        # ---------- 宏观终局线 ----------
        # 超时优先级最高 —— 它决定了"剩下的步骤根本没机会跑"，信息量最大。
        if self.timed_out:
            lines.append("")
            lines.append(
                f"[超时] 达到设定的总执行上限 {self.max_exec_time}s，"
                f"流程在第 {self.current_loop} 轮附近被强制终止。"
            )
        elif self.user_interrupted:
            # 只有当已有真实错误铺垫时，手动终止才值得一并说明——否则那是
            # 用户自己的知情选择，弹出来纯属噪音（设计定稿①：主动停止不弹）。
            lines.append("")
            lines.append(f"[终止] 流程在第 {self.current_loop} 轮被你手动停止。")

        # ---------- 分类建议 ----------
        # 只列出实际出现过的类别对应的建议，没出现的毛病没必要占篇幅。
        seen_categories = {cat for cat, _ in self.error_report}
        suggestion_map = {
            "invalid_action": "该步骤引用的动作类型已不存在（软件升级后可能被移除），请在编辑器中重新选择动作并配置参数。",
            "step_exception": "根据上述错误信息排查参数；也可以把这个步骤单独拷出来，在动作组编辑窗点「▶ 试运行」实时看日志定位。",
            "timeout": "建议调大「总超时限制」参数，或将一个长流程拆分成多个动作组分别触发，避免超时切断关键环节。",
            "startup_reject": "动作组未能启动 —— 请按提示精简步骤数量或修正配置后再试。",
        }
        # 用固定顺序遍历 map，保证输出稳定不抖动（dict 取键顺序虽然 Py3.7+
        # 保有序，但显式白名单读起来更清楚哪些是有意支持的类别）。
        ordered_cats = [c for c in
                        ("invalid_action", "step_exception", "timeout", "startup_reject")
                        if c in seen_categories]
        if ordered_cats:
            lines.append("")
            lines.append("💡 建议处理方式：")
            for c in ordered_cats:
                lines.append(f"· {suggestion_map[c]}")

        # ---------- 残缺状态提醒 ----------
        # 仅当策略是"跳过继续"且确实发生过失败才说这句 —— 它是这一模式最容易
        # 让用户忽略的隐性代价：以为后面都跑了所以没事，其实前面已经断了根。
        if self.stop_on_error != "停止整个动作组":
            lines.append("")
            lines.append(
                "⚠ 因当前策略为「单步失败时跳过继续」，失败之后的步骤已经在"
                "不完整的前置状态下执行过了，最终效果可能不符合预期，请人工核对。"
            )

        text = "\n".join(lines)

        # 长度兜底截断，最后一行标注去哪里看完整内容
        if len(text) > MAX_TEXT_LENGTH:
            text = (
                    text[:MAX_TEXT_LENGTH]
                    + "\n…\n（提示：报告过长已截断，完整明细请查看开发/调试模式下的控制台输出。）"
            )
        return text

