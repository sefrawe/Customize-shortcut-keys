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

        # ==================== 新增：超时时间兜底校验 ====================
        try:
            # 尝试转换为整数
            parsed_time = int(max_exec_time)
        except (ValueError, TypeError):
            # 如果转换失败（如输入了字母或为空），使用默认值 60
            parsed_time = 60

        # 强制钳制在 1 到 120 秒之间，防止用户手改 JSON 设置过大导致死机
        self.max_exec_time = max(1, min(parsed_time, 120))
        # ==============================================================

        # 记录开始时间，用于超时判断
        self.start_time = 0

        # 记录开始时间，用于超时判断
        self.start_time = 0

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
            return

        self.start_time = time.time()

        # 2. 全局统一确认：如果是正式执行(非试运行)且勾选了统一确认，先收集所有命令弹一次窗
        if self.confirm_all and not self.log_callback:
            if not self._check_all_commands():
                self._log("用户取消了全局确认，动作组中止。")
                return

        # 3. 循环执行逻辑
        for loop_idx in range(self.loop_count):
            # 每一轮开始前检查中断信号
            if self.hard_interrupt_event.is_set():
                self._log("⛔ 收到硬中断信号，强制停止回放。")
                break
            if self.soft_stop_event.is_set():
                self._log("⏸ 收到平滑停止信号，动作组在当前步完成后终止。")
                break

            if self.loop_count > 1:
                self._log(f"--- 开始第 {loop_idx+1}/{self.loop_count} 轮执行 ---")

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
                self.hard_interrupt_event.set()
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

            # 4. 获取动作定义和处理器
            action_def = getActionDefByKey(action_key)
            if not action_def or not action_def.handler:
                err_msg = f"步骤 {i+1} 的动作 '{action_key}' 无效或未注册。"
                self._log(f"❌ 错误捕获: {err_msg}")
                if self._handle_error(err_msg): break
                else: continue

            # 5. 试运行模式拦截：如果是试运行(log_callback存在)，重写 confirm_callback 让其自动通过，避免弹窗卡住测试
            local_context = self.context.copy()
            if self.log_callback:
                local_context["confirm_callback"] = lambda msg, holder, evt: (holder.__setitem__(0, True), evt.set())

            # 6. 核心执行：调用 handler
            try:
                action_def.handler(action_params, local_context)
                self._log(f" -> ✅ 完成")
            except Exception as e:
                err_msg = f"步骤 {i+1} 执行出错: {str(e)}"
                self._log(f"❌ 错误捕获: {err_msg}")
                if self._handle_error(err_msg): break
                else: continue

            # 7. 执行步骤间的延迟
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
        # ==================== 修改：统一按毫秒处理 ====================
        # 无论 fixed 还是 wait_release，拿到的 value 都直接是毫秒
        # 强制转换为 float，解决 IDE 静态类型检查的格式化警告，并防止用户手改 JSON 填错类型导致崩溃
        try:
            value_ms = float(delay_config.get("value", 0))
        except (ValueError, TypeError):
            value_ms = 0.0

        # ============================================================

        if delay_type in ("fixed", "wait_release") and value_ms > 0:
            # 如果是等待释放，给个日志提示，方便调试
            if delay_type == "wait_release":
                # 日志里转换为秒显示，方便人类阅读
                self._log(f"等待 {value_ms / 1000:.1f}s...")

            # 分片休眠，每 50ms 醒来检查一次是否被中断
            slept = 0
            # ==================== 修改：循环条件改为直接对比毫秒 ====================
            # 以前: while slept < value * 1000:
            while slept < value_ms:
                # =================================================================
                if self.hard_interrupt_event.is_set() or self.soft_stop_event.is_set():
                    break
                time.sleep(0.05)
                slept += 50
