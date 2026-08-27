''' 动作执行器 '''

''' 【执行器核心执行逻辑说明】
本执行器采用 "异步执行 + 状态锁拦截" 策略，彻底解决了动作执行卡死底层钩子，以及模拟按键干扰自身监听器的问题。

1. 异步执行防阻塞：
   - 按键匹配成功后，_executeShortcut 被放入独立的守护线程执行。
   - pynput 监听线程瞬间返回，不再被剪贴板操作或 time.sleep 阻塞，保证全局键盘输入流畅。

2. 状态锁防重入 (isExecuting)：
   - 动作执行前置为 True，执行完毕 (finally) 置为 False。
   - 在 handleKeyPress / handleKeyRelease 开头判断此标志：若正在执行，直接忽略所有底层键盘事件。
   - 目的：阻断 actionHandlers 中模拟按键（如 kb.press('v')）触发的自身监听回调，防止状态机错乱（如"单按Ctrl触发粘贴"的灵异Bug）。

3. 防连发与强制重置：
   - hasTriggeredCurrentPress 保证一轮按键只触发一次动作。
   - 动作执行期间所有按键释放事件被忽略，动作结束后在 finally 块中强制清空监听器的按键集合并重置所有标志。
   - 当前行为结论：用户必须完全松开所有按键，让状态机回到纯净的初始状态后，才能触发下一次快捷键动作。牺牲了"按住修饰键连击"的灵敏度，换取了绝对的执行稳定性。
'''

''' 【快捷键匹配核心逻辑说明】
为了区分键盘上的重复物理键（如左/右 Ctrl、Shift、Alt，主键盘数字与右侧小键盘数字），
同时保持原有基于字符串配置的向后兼容性，本模块采用了"统称与特称智能匹配"策略，
无需将配置文件结构重构为复杂的 JSON 对象。

1. 标准化不再合并：
   - _normalizeAlias: 只做等价拼写转换（如 control -> ctrl），不再将 ctrl_l/ctrl_r 强行合并为 ctrl。
   _normalizeSingleKey: 先查 name 特殊键别名体系；常规字符键一律经 vkKeyMap.VK_TO_NAME 以虚拟键码判定（物理键位语义，免疫修饰键/大写锁定/输入法污染；Bug#30 重构核心）。

2. 智能匹配机制：
   - _is_key_match / _isCombinationMatch: 如果配置写统称(如 'ctrl')，则允许监听到的具体特称(如 'ctrl_l' 或 'ctrl_r')匹配成功；
     如果配置写特称(如 'ctrl_l')，则只有按下左 Ctrl 才能匹配成功。
     数字键不互通（'1' 与 'numpad_1' 视为完全不同的键）。

3. 动作模拟适配：
   - _doPasteText: 为防止用户按住的是右 Ctrl 而代码只释放了通用 Ctrl，统一释放所有修饰键的左右变体。
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

from utils.vkKeyMap import VK_TO_NAME


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

        #  操作软件自身的跨线程回调
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
        self.refresh()
        # 无论监听器是否在运行，都重置状态标志，防止编辑后状态卡死
        self.hasTriggeredCurrentPress = False
        self.isExecuting = False

        if self.activeScheme is None:
            if self.listener is not None and self.isListening:
                self.listener.stop()
                self.isListening = False
            return None

        if self.listener is None or not self.isListening:
            self._buildListener()
            return self.start()

        #  监听器仍在运行时，清空按键集合，防止残留按键状态干扰
        if self.listener is not None:
            self.listener.pressedKey.clearKeys()

        return self.activeScheme

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
        # 如果动作正在执行，直接忽略所有按键事件（包括模拟出来的按键）
        if self.isExecuting:
            return

        # 已经触发过一次后，必须等按键集合完全清空，才允许下一次触发
        if self.hasTriggeredCurrentPress:
            return

        pressedKeyNames = self._normalizePressedKeys(pressed_keys.getPressedKeys())
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

    def _normalizePressedKeys(self, pressed_keys):
        """把 pynput 的按键对象转成可比较的字符串集合。"""
        normalized = set()
        for key in pressed_keys:
            name = self._normalizeSingleKey(key)
            if name:
                normalized.add(name)
        return normalized

    def _normalizeSingleKey(self, key):
        """
        将 pynput 按键事件对象归一化为规范键名字符串（Bug#30 重构核心）。

        判定顺序【不可调换】，三级漏斗从可靠到不可靠：
          ① 特殊键   有 name 属性 → 走别名归一化
                     （ctrl_l / f5 / space 等由 _normalizeAlias 统一收口，
                      此路原有逻辑不动）
          ② 常规键★ vk 命中 vkKeyMap.VK_TO_NAME → 直接采用规范名
                     vk 是物理键位编号，天生免疫修饰键/大小写锁定/输入法
                     三种状态污染——这是本次重构的全部意义所在。
          ③ char兜底 仅当 vk 未收录且无 name 的极罕见场景。
                     ⚠ 此路径的产物可能被修饰键污染（如 Ctrl+C 给出 '\x03'），
                     属于"知道不可靠但留着以防万一"的容错位。
                     边界铁律：永远不许靠它实现新功能（见记事本·边界备忘3）。

        参数: key —— pynput 监听回调交来的按键对象
        返回: 规范键名 str；无法识别返回 None（调用方按既有逻辑忽略该键）
        """
        if key is None:
            return None

        # ── ① 特殊键：pynput 的 Key 枚举成员才有 name 属性 ─────────────
        name = getattr(key, "name", None)
        if name:
            return self._normalizeAlias(str(name).lower())

        # ── ② vk 总表查询：本轮唯一的新增主路径 ★ ─────────────────────
        vk = getattr(key, "vk", None)
        if vk is not None and vk in VK_TO_NAME:
            return VK_TO_NAME[vk]

        # ── ③ char 最后容错（不可靠路径，勿依赖）─────────────────────
        ch = getattr(key, "char", None)
        if ch:
            return str(ch).lower()

        return None

    def _normalizeAlias(self, keyName):
        """统一等价别名，但不再合并左右修饰键。"""
        aliasMap = {
            "control": "ctrl",
            "control_l": "ctrl_l",
            "control_r": "ctrl_r",
            "option": "alt",
            "option_l": "alt_l",
            "option_r": "alt_r",
            "command": "cmd",
            "windows": "cmd",
        }
        return aliasMap.get(keyName, keyName)

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
                #   局部变量本来就有，透传下去几乎零成本；若空则 actionHandlers
                #   会自动降级为"未命名快捷键"占位。
                # ② tip_callback：执行结束后的汇总弹窗通道。它本身已被主窗口按
                #   "self.after(0, ...)" 的跨线程安全范式包装好了（见
                #   MainWindow.showExecutorTip），直接挂进来就能跨线程使用，
                #   与本文件既有的 confirm_callback 是同一套协作约定。
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
            self.hasTriggeredCurrentPress = False
