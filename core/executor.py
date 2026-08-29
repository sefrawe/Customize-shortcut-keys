''' 动作执行器 '''
''' 【执行器核心执行逻辑说明】
 本执行器采用 "异步执行 + 状态锁拦截" 策略，彻底解决了动作执行卡死底层钩子，
 以及模拟按键干扰自身监听器的问题。

 1. 异步执行防阻塞：
    - 按键匹配成功后，_executeShortcut 被放入独立的守护线程执行。
    - pynput 监听线程瞬间返回，不再被剪贴板操作或 time.sleep 阻塞，
      保证全局键盘输入流畅。

 2. 状态锁防重入：
    - 动作执行前置为 True，执行完毕 置为 False。
    - 在 handleKeyPress / handleKeyRelease 开头判断此标志：
      若正在执行，直接忽略所有底层键盘事件。
    - 目的：阻断 actionHandlers 中模拟按键（如 kb.press('v')）触发的自身
      监听回调，防止状态机错乱（如"单按Ctrl触发粘贴"的灵异Bug）。

 3. 防连发与强制重置：
    - hasTriggeredCurrentPress 保证一轮按键只触发一次动作。
    - 动作执行期间所有按键释放事件被忽略，动作结束后在 finally 块中强制
      清空监听器的按键集合并重置所有标志。
    - 当前行为结论：用户必须完全松开所有按键，让状态机回到纯净的初始状态后，
      才能触发下一次快捷键动作。牺牲了"按住修饰键连击"的灵敏度，
      换取了绝对的执行稳定性。
'''
''' 【停止组合三级路由说明（31/33 号新增）】
 动作组可能劫持鼠标，此时托盘与 GUI 都点不到 → 键盘组合是唯一可靠逃生口。
 handleKeyPress 最顶端（务必在 isExecuting / hasTriggeredCurrentPress 两个
 闸门之前 —— 铁律：放在闸门后，恰在最需要时失效）对归一化后的按下集合做
 精确匹配（utils/reservedCombos.matchReservedStopCombo，唯一真相源）：
     强制停止 ctrl_r + alt_r + esc ／ 平滑停止 ctrl_l + alt_l + esc

 三级路由：
   ① is_busy=True    → set 全局硬停/软停事件后静默返回。不弹模态框（鼠标被
                        劫持时弹了也点不到）；播放器报告机制保证"干净的手动
                        停止不写 error_report → 不弹汇总"，鼠标停下即反馈。
   ② 试运行注册活跃  → set 试运行局部事件（register_trial_interrupt 槽位，
                        由动作组编辑窗注册，见 gui/ActionGroupEditorWindow）。
   ③ 都不是          → 静默吞掉。空闲防护 + 运行时豁免层：手改 JSON 绑了
                        保留组合的快捷键在此被永久截胡，最坏结局 = 该快捷键
                        失效，而不是系统停止功能失效。

 匹配语义与已知边界（全文见 reservedCombos 模块头与设计定稿）：
   · 精确集合相等、只认特称 → 混按（左ctrl+右alt+esc）不触发；模拟按键发
     统称 ctrl 得到的是统称名，与特称集合永不相等 → 宏无法误触急停，
     路由端零防回声负担（特称写法已被 keyValidator 在源头拦截）；
   · 触发后置位 hasTriggeredCurrentPress 并立 _stopComboLatched 闩锁：
     esc 轻点即松，但两个修饰键大概率仍按住；不锁则执行在按住期间结束后，
     补按字母键会把 {ctrl_l, alt_l, k} 送给用户快捷键误触发。闩锁等
     "全部松开"才解锁（_executeShortcut 的 finally 对闩锁让路，见彼处）；
   · 不拦截任何系统行为：ctrl+alt+esc 无系统绑定，监听器保持纯被动（33 号）；
   · 停止组合依赖监听器在跑：无启用方案时监听器未启动（start 提前返回），
     此时试运行只能用编辑窗的停止按钮 —— 记录为已知限制。
'''

import re
import threading
from collections.abc import Callable

from core.configManager import configDirectory
from core.listener import KeyboardListener
# 引入并初始化 handler 绑定 (也可以在 main.py 启动时调用)
from utils.actionHandlers import initActionHandlers
from utils.actionRegistry import getActionDefByKey
from utils.shortcutUtils import getShortcutBySchemeName, getStartupEnabledShortcutScheme

# 【归一化下沉】实现体已平移至 utils/keyNormalizer.py（唯一真相源），本文件改为委托。
# VK_TO_NAME 在本文件已无直接使用者，原导入随之移除；未来确需 vk 查询时再按需导入。
from utils.keyNormalizer import normalizeSingleKey, normalizeAlias

# ==================== 31/33 号新增导入 ====================
# 保留停止组合的唯一真相源：常量 + 运行时精确匹配工具。
# 导入方向 executor → reservedCombos → keyNormalizer，无循环依赖。
from utils.reservedCombos import matchReservedStopCombo, STOP_KIND_HARD, STOP_KIND_SOFT, matchReservedStopComboLoose

initActionHandlers()


class Executor:
    """动作执行器：负责组装监听器并接收监听结果。"""

    def __init__(self):
        # self指的是当前实例
        # 提示回调由主窗口注入，避免执行器直接依赖 GUI 组件
        # 定义一个可选的回调函数，用于显示提示信息。如果未设置回调函数，则使用默认的控制台输出方式。
        self.tipCallback: Callable[[str, str], None] | None = None
        # 跨线程确认弹窗回调
        self.confirmCallback: Callable[[str, list, threading.Event], None] | None = None
        # 操作软件自身的跨线程回调
        self.appControlCallback: Callable[[str], None] | None = None
        # 定义一个可选的字典，用于存储当前启用的快捷键方案。如果没有启用的方案，则为 None。
        self.activeScheme: dict | None = None
        # 定义一个列表，用于存储当前启用的快捷键方案中的所有快捷键信息。每个快捷键信息是一个字典，包含快捷键的名称、组合键、动作等信息。
        self.activeShortcuts: list[dict] = []
        # 当前这一轮按键是否已经触发过快捷键
        self.hasTriggeredCurrentPress = False
        # 动作执行状态锁，防止重入和模拟按键干扰
        self.isExecuting = False
        # 动作组全局忙碌状态
        self.is_busy = False
        # 供托盘紧急中断动作组使用 (硬停止，立即打断)
        self.action_group_interrupt_event = threading.Event()
        # 供托盘平滑停止动作组使用 (软停止，允许当前步执行完毕后在下一步前退出)
        self.action_group_soft_stop_event = threading.Event()

        # ==================== 31/33 号新增：停止组合路由配套状态 ====================
        # 试运行中断事件槽位：动作组编辑窗试运行开始时 register、try/finally 里
        # unregister。单槽引用赋值在 GIL 下是原子操作，无需加锁；None = 无试运行。
        # 路由二级靠"槽位非 None"判定试运行活跃，注册/注销的生命周期即试运行生命周期。
        self._trial_interrupt_event: threading.Event | None = None
        # 停止组合闩锁：标记当前 hasTriggeredCurrentPress 是否因停止组合触发而立起。
        # 存在理由：_executeShortcut 的 finally 会无条件复位 hasTriggeredCurrentPress，
        # 若执行是被停止组合终止的（硬停打断长步骤后），复位时用户手指往往仍按着
        # 停止修饰键 —— 复位会让随后补按的字母键直达用户快捷键匹配（设计定稿 1.2
        # 要防的边缘场景）。闩锁立着时 finally 跳过复位，交由 handleKeyRelease 的
        # "全部松开"分支一并解除。普通快捷键触发不立此锁，行为与历史版本完全一致。
        self._stopComboLatched = False
        # ==========================================================================

        # 定义一个布尔值，用于表示当前监听器是否正在监听按键事件。如果正在监听，则为 True；否则为 False。
        self.isListening = False
        self.listener = KeyboardListener(
            on_key_press=self.handleKeyPress,
            on_key_release=self.handleKeyRelease,
        )
        self.refresh()

    def _buildListener(self):
        """重建监听器，避免 stop 后复用失效的 listener 对象。"""
        self.listener = KeyboardListener(
            on_key_press=self.handleKeyPress,
            on_key_release=self.handleKeyRelease,
        )

    def setTipCallback(self, callback: Callable[[str, str], None]):
        """设置提示窗口回调。"""
        self.tipCallback = callback

    def setConfirmCallback(self, callback: Callable[[str, list, threading.Event], None]):
        """设置跨线程确认弹窗回调，供动作执行器在需要用户确认时调用。"""
        self.confirmCallback = callback

    def setAppControlCallback(self, callback: Callable[[str], None]):
        """设置操作软件自身的跨线程回调，供动作执行器在需要控制软件时调用。"""
        self.appControlCallback = callback

    def showTip(self, text, title="提示"):
        """显示提示信息；没有回调时退化为控制台输出。"""
        if self.tipCallback:
            self.tipCallback(title, text)
            return
        print(f"{title}: {text}")

    def start(self):
        # 启动前先刷新一次，确保读取的是最新配置
        self.refresh()
        if self.activeScheme is None:
            # self.showTip("没有被设置为启动启用状态的快捷键方案，键盘监听器未启动。")
            return None
        # self.showTip(f"启动键盘监听器，监听快捷键方案: {self.activeScheme['name']}")
        self.isListening = True
        return self.listener.start()

    def stop(self):
        # 停止监听器
        self.listener.stop()
        self.isListening = False

    def destroy(self):
        # 销毁监听器对象，释放资源
        self.stop()
        self.listener = None

    def restart(self):
        # 配置改动后，旧监听器对象可能已经不可继续使用，所以先销毁再重建
        self.destroy()
        self._buildListener()
        self.refresh()
        return self.start()

    def refresh(self):
        """刷新当前启用的快捷键方案和对应快捷键信息。"""
        self.activeScheme = getStartupEnabledShortcutScheme(configDirectory)
        if self.activeScheme is None:
            self.activeShortcuts = []
            return None
        self.activeShortcuts = getShortcutBySchemeName(self.activeScheme["name"])
        return self.activeScheme

    def sync(self):
        """同步执行器状态：有方案就保持监听，没方案就停掉。"""
        # ==================== 31/32 号新增：执行中守卫（权威防线）====================
        # sync() 会无条件复位 isExecuting / hasTriggeredCurrentPress —— 这在执行中
        # 等于拆掉状态锁，模拟按键将穿透闸门直达匹配逻辑（灵异触发复活）。
        # 入口共三个：托盘菜单（菜单项已按 is_busy 置灰）、MainWindow.refreshExecutor
        # （第三轮加同款守卫）、动作组内 appControlSafe 的"刷新执行器"指令（该指令
        # 在动作组中调用合法，所以守卫必须做在方法本体才能兜住全部入口 —— 本处即
        # 权威防线）。守卫口径用 isExecuting 而非 is_busy：单动作也有长尾
        # （如 mouseMoveTo 大 duration），一并覆盖。代价：执行中的同步请求被静默
        # 忽略（无方案时本就返回 None，调用方已兼容），用户稍后再点一次即可。
        if self.isExecuting:
            return None
        # ==========================================================================
        self.refresh()
        # 无论监听器是否在运行，都重置状态标志，防止编辑后状态卡死
        self.hasTriggeredCurrentPress = False
        # 闩锁与 hasTriggeredCurrentPress 同源同清，防止留下"标志已清、闩锁还立"
        # 的不一致态（否则未来某次普通执行的 finally 会错误跳过复位）
        self._stopComboLatched = False
        self.isExecuting = False
        if self.activeScheme is None:
            if self.listener is not None and self.isListening:
                self.listener.stop()
                self.isListening = False
            return None
        if self.listener is None or not self.isListening:
            self._buildListener()
            return self.start()
        # 监听器仍在运行时，清空按键集合，防止残留按键状态干扰
        if self.listener is not None:
            self.listener.pressedKey.clearKeys()
        return self.activeScheme

    # ==================== 31 号新增：试运行中断注册/注销接口 ====================
    def register_trial_interrupt(self, event: threading.Event) -> None:
        """注册试运行中断事件（动作组编辑窗试运行开始时调用）。

        注册后，全局停止组合的路由二级会把硬停信号送进这里 —— 试运行
        劫持鼠标时编辑窗按钮同样点不到，键盘组合是试运行的逃生口
        （31 号顺带项）。单槽位语义：同一时刻至多一个试运行在跑
        （编辑窗入口另有 is_busy 守卫，见 ActionGroupEditorWindow 本轮配套接线）。
        """
        self._trial_interrupt_event = event

    def unregister_trial_interrupt(self) -> None:
        """注销试运行中断事件（试运行线程的 try/finally 里调用，防槽位泄漏）。

        finally 注销是硬要求：无论试运行正常结束、被停止还是抛异常，都必须
        清槽 —— 否则残留的旧事件引用会让后续空闲期的停止组合误入路由二级
        （只是 set 一个无人监听的事件，无害，但不干净、且语义错位）。
        """
        self._trial_interrupt_event = None
    # ==========================================================================

    def getActiveSchemeInfo(self):
        # 获取当前启用的快捷键方案信息
        return self.activeScheme

    def getActiveShortcutInfos(self):
        # 获取当前启用的快捷键方案中的所有快捷键信息
        return list(self.activeShortcuts)

    def getActiveRuntimeInfo(self):
        return {
            "scheme": self.getActiveSchemeInfo(),
            "shortcuts": self.getActiveShortcutInfos(),
        }

    def handleKeyPress(self, key, pressed_keys):
        # ==================== 31/33 号新增：归一化提前 + 停止组合三级路由 ==========
        # 归一化从原"闸门之后"提升到最顶端：停止路由与后续用户快捷键匹配共用
        # 同一次归一化结果（一次遍历两用，每个按键事件只算一遍）。
        pressedKeyNames = self._normalizePressedKeys(pressed_keys.getPressedKeys())

        # 路由点在最顶端 —— 在下面两个闸门之前。
        # 铁律：动作组执行中 isExecuting 恒为 True，若路由放在闸门之后，
        # 停止组合恰在最需要时失效。
        stop_kind = matchReservedStopCombo(pressedKeyNames)
        if stop_kind is not None:
            if self.is_busy:
                # 一级：动作组执行中 → 置对应全局事件后静默返回。
                # 不弹任何模态框（鼠标被劫持时弹了也点不到）；播放器报告机制
                # 保证"干净的手动停止不写 error_report → 不弹汇总弹窗"，
                # 鼠标停下本身就是反馈。
                if stop_kind == STOP_KIND_HARD:
                    self.action_group_interrupt_event.set()
                elif stop_kind == STOP_KIND_SOFT:
                    self.action_group_soft_stop_event.set()
            elif self._trial_interrupt_event is not None:
                # 二级：试运行注册活跃 → 置试运行局部事件（编辑窗自建事件，
                # 播放器每步检查）。放在 is_busy 之后：真执行与试运行理论上
                # 不并存（编辑窗入口守卫），此处顺序只是防御性优先级。
                self._trial_interrupt_event.set()
            # 三级：都不是 → 静默吞掉（不落到底部匹配逻辑）。
            # 空闲防护：空闲时按停止组合无事发生；
            # 运行时豁免层：手改 JSON 绑了保留组合的快捷键在此被永久截胡，
            # 最坏结局 = 该快捷键失效，而不是系统停止功能失效。
            # 幂等：按住期间 auto-repeat 会反复进入本分支，重复 set 无害；
            # 软停信号已发再按，行为不变。
            #
            # 触发后置位 hasTriggeredCurrentPress（仅一/二级，三级纯吞不立锁，
            # 否则空闲试按会莫名锁住后续快捷键）：esc 轻点即松，但两个修饰键
            # 大概率仍按住；不置位的话，执行若在按住期间结束（软停在步间退出，
            # 往往就在 esc 松开后几十毫秒内），补按字母键会把 {ctrl_l, alt_l, k}
            # 送给用户快捷键。置位后须等全部按键松开才解锁 —— 正好符合急停语义。
            # _stopComboLatched 的作用见 __init__ 注释与 _executeShortcut 的 finally。
            if self.is_busy or self._trial_interrupt_event is not None:
                self.hasTriggeredCurrentPress = True
                self._stopComboLatched = True
            return
        # =========================================================================

        # 如果动作正在执行，直接忽略所有按键事件（包括模拟出来的按键）
        if self.isExecuting:
            stop_kind = matchReservedStopComboLoose(pressedKeyNames)
        else:
            stop_kind = matchReservedStopCombo(pressedKeyNames)

        # 已经触发过一次后，必须等按键集合完全清空，才允许下一次触发
        if self.hasTriggeredCurrentPress:
            return

        # 复用顶部归一化结果（31 号：归一化已提前，此处不再重复计算）
        matchedShortcut = self._findMatchedShortcut(pressedKeyNames)
        if matchedShortcut is None:
            return

        self.hasTriggeredCurrentPress = True
        # 异步执行动作，防止底层钩子阻塞
        threading.Thread(
            target=self._executeShortcut,
            args=(matchedShortcut,),
            daemon=True
        ).start()

    def handleKeyRelease(self, key, pressed_keys):
        # 动作执行期间忽略释放事件，防止模拟释放污染状态机
        if self.isExecuting:
            return
        # 只有所有键都松开后，才把"已触发"状态清掉
        if not pressed_keys.getPressedKeys():
            self.hasTriggeredCurrentPress = False
            # 31 号新增：停止组合闩锁随"全部松开"一并解除 —— 解锁判据与
            # hasTriggeredCurrentPress 完全同源，不引入第二套时序。
            # 注：执行中（isExecuting=True）释放事件被上面的闸门忽略，闩锁
            # 不会在执行中途被清；执行结束后的首次"全松开"释放事件在此解锁。
            self._stopComboLatched = False

    def _normalizePressedKeys(self, pressed_keys):
        """把 pynput 的按键对象转成可比较的字符串集合。"""
        normalized = set()
        for key in pressed_keys:
            name = self._normalizeSingleKey(key)
            if name:
                normalized.add(name)
        return normalized

    def _normalizeSingleKey(self, key):
        """【已下沉】实现体平移至 utils.keyNormalizer.normalizeSingleKey（唯一真相源）。
        本方法仅保留为兼容委托：executor 内部调用点（_normalizePressedKeys 等）
        零感知，无需改动。三级漏斗的完整说明、判定顺序铁律、Bug#30 重构背景、
        调用方约定，全部随实现体迁移至 utils/keyNormalizer.py，以彼处为准。
        """
        return normalizeSingleKey(key)

    def _normalizeAlias(self, keyName):
        """【已下沉】见 utils.keyNormalizer.normalizeAlias。仅兼容委托，零行为变化。"""
        return normalizeAlias(keyName)

    # 类变量：统称 → 可匹配的特称集合
    _KEY_SUPERSET = {
        "ctrl": {"ctrl_l", "ctrl_r"},
        "shift": {"shift_l", "shift_r"},
        "alt": {"alt_l", "alt_r"},
        "cmd": {"cmd_l", "cmd_r"},
    }

    def _is_key_match(self, config_key, pressed_key):
        """检查配置中的按键是否能匹配监听到的按键（支持统称匹配特称）。"""
        # 1. 完全相等（特称匹配特称，或普通键匹配普通键）
        if config_key == pressed_key:
            return True
        # 2. 统称匹配特称：配置写 ctrl，允许 ctrl_l/ctrl_r
        if config_key in self._KEY_SUPERSET:
            return pressed_key in self._KEY_SUPERSET[config_key]
        return False

    def _parseKeyCombination(self, keyCombination):
        """把配置里的组合键字符串拆成集合。

        【直通原则】本函数没有任何别名兑换（旧的 plus 还原已随决策5删除）：
        - 合法性由 keyValidator 在保存环节把关，此处无条件信任输入；
        - 统称/特称收敛统一走 _normalizeAlias（control->ctrl 等等价拼写除外）；
        - 若出现监听端不可能产出的键名（如手改JSON写了 prtscn），
          后果只是该快捷键永不触发，不影响其他条目——坏数据的最坏结局
          就是"失效"，而不是"误触发"，这是可接受的设计底线。
        """
        if not keyCombination:
            return set()

        tokens = re.split(r"\s*\+\s*", keyCombination.strip())
        normalized = set()
        for token in tokens:
            token = token.strip().lower()
            if not token:
                continue
            normalized.add(self._normalizeAlias(token))
        return normalized

    def _findMatchedShortcut(self, pressedKeyNames):
        """找出当前按键集合匹配的快捷键（支持统称/特称智能匹配）。"""
        matchedShortcut = None
        matchedLength = -1
        for shortcut in self.activeShortcuts:
            if not shortcut.get("enabled", False):
                continue
            shortcutKeys = self._parseKeyCombination(shortcut.get("keyCombination", ""))
            if not shortcutKeys:
                continue
            # 数量不一致直接跳过
            if len(shortcutKeys) != len(pressedKeyNames):
                continue
            # 用智能匹配替代严格相等
            if self._isCombinationMatch(shortcutKeys, pressedKeyNames) and len(shortcutKeys) > matchedLength:
                matchedShortcut = shortcut
                matchedLength = len(shortcutKeys)
        return matchedShortcut

    def _isCombinationMatch(self, configKeys, pressedKeyNames):
        """检查配置按键集合与监听按键集合是否匹配（支持统称匹配特称）。"""
        pressedList = list(pressedKeyNames)
        used = [False] * len(pressedList)
        for cKey in configKeys:
            found = False
            for i, pKey in enumerate(pressedList):
                if not used[i] and self._is_key_match(cKey, pKey):
                    used[i] = True
                    found = True
                    break
            if not found:
                return False
        return True

    def _executeShortcut(self, shortcut: dict):
        """动作分发器：从注册表获取定义并执行（运行在独立子线程中）"""
        self.isExecuting = True
        #动作组忙碌状态控制
        is_action_group = (shortcut.get("action") == "actionGroup")
        if is_action_group:
            self.is_busy = True
            self.action_group_interrupt_event.clear()  # 执行前清空中断信号
            # 每次开始新的动作组前，清理上一次可能残留的软停止信号
            self.action_group_soft_stop_event.clear()

        try:
            shortcutName = shortcut.get("name", "")
            actionKey = shortcut.get("action", "")
            actionParams = shortcut.get("actionParams", {})

            if not actionKey:
                self.showTip(f"快捷键 '{shortcutName}' 没有配置动作。")
                return

            # 1. 从注册表获取动作定义
            actionDef = getActionDefByKey(actionKey)
            if actionDef is None:
                self.showTip(f"未知的动作类型: {actionKey}", title="执行错误")
                return

            # 2. 后端参数兜底校验 (防止用户手改JSON导致参数缺失)
            for spec in actionDef.params:
                if spec.required and not actionParams.get(spec.key):
                    self.showTip(f"快捷键 '{shortcutName}' 缺少必填参数: {spec.label}", title="执行错误")
                    return

            # 3. 执行挂载的 handler
            if actionDef.handler is None:
                self.showTip(f"动作 '{actionDef.displayName}' 尚未实现执行逻辑", title="执行错误")
                return

            try:
                # 构建 context 并传递给 handler
                # ==================== 新增两个键（报告机制配套）====================
                # ① shortcut_name：报告标题需要"这份报告是谁的"。shortcut 名是
                #    局部变量本来就有，透传下去几乎零成本；若空则 actionHandlers
                #    会自动降级为"未命名快捷键"占位。
                # ② tip_callback：执行结束后的汇总弹窗通道。它本身已被主窗口按
                #    "self.after(0, ...)" 的跨线程安全范式包装好了（见
                #    MainWindow.showExecutorTip），直接挂进来就能跨线程使用，
                #    与本文件既有的 confirm_callback 是同一套协作约定。
                # ================================================================
                context = {
                    "confirm_callback": self.confirmCallback,
                    "app_control_callback": self.appControlCallback,
                    "tip_callback": self.tipCallback,
                    "shortcut_name": shortcutName,
                    "interrupt_event": self.action_group_interrupt_event if is_action_group else None,
                    # 只有动作组才需要传入软停止事件，普通动作传 None
                    "soft_stop_event": self.action_group_soft_stop_event if is_action_group else None,
                }
                actionDef.handler(actionParams, context)
            except Exception as e:
                self.showTip(f"执行动作 '{actionDef.displayName}' 失败:\n{str(e)}", title="执行错误")
        finally:
            # 动作执行完毕后的善后工作
            self.isExecuting = False
            # 解除忙碌状态
            if is_action_group:
                self.is_busy = False
            # 清空监听器中的按键集合，防止执行期间模拟按键造成的残留状态干扰
            if self.listener is not None:
                self.listener.pressedKey.clearKeys()
            # ==================== 31 号新增：闩锁让路 ====================
            # 原逻辑在此无条件复位 hasTriggeredCurrentPress。但若本次执行是被
            # 停止组合终止的（硬停打断长步骤后，用户手指往往仍按着 ctrl_r+alt_r），
            # 此时复位会让随后补按的字母键（配合修饰键 auto-repeat 重新入集合）
            # 直达用户快捷键匹配 —— 设计定稿 1.2 "置位后松开全部按键才解锁"的
            # 承诺会在这里被拆台。闩锁立着时跳过复位，交由 handleKeyRelease 的
            # "全部松开"分支解锁。普通触发（闩锁未立）保持原行为，零变化。
            # 已知残余微豁口（设计已接受）：clearKeys 清掉的虚拟集合不再记录
            # 用户仍物理按着的键，"全部松开"的判定以释放事件流为准，个别按键
            # 交错序列下可能提前解锁 —— 概率低、后果轻，不值得引入新状态机。
            if not self._stopComboLatched:
                self.hasTriggeredCurrentPress = False
            # ============================================================
