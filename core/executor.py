'''
动作执行器
'''
import re
from collections.abc import Callable

from pynput import keyboard

from core.listener import KeyboardListener
from core.configManager import configDirectory
from utils.shortcutUtils import getShortcutBySchemeName, getStartupEnabledShortcutScheme
import win32clipboard as wc

class Executor:
    """动作执行器：负责组装监听器并接收监听结果。"""

    def __init__(self):#self指的是当前实例
        # 提示回调由主窗口注入，避免执行器直接依赖 GUI 组件
        self.tipCallback: Callable[[str, str], None] | None = None#定义一个可选的回调函数，用于显示提示信息。如果未设置回调函数，则使用默认的控制台输出方式。
        self.activeScheme: dict | None = None#定义一个可选的字典，用于存储当前启用的快捷键方案。如果没有启用的方案，则为 None。
        self.activeShortcuts: list[dict] = []#定义一个列表，用于存储当前启用的快捷键方案中的所有快捷键信息。每个快捷键信息是一个字典，包含快捷键的名称、组合键、动作等信息。
        self.hasTriggeredCurrentPress = False  # 当前这一轮按键是否已经触发过快捷键
        self.isListening = False#定义一个布尔值，用于表示当前监听器是否正在监听按键事件。如果正在监听，则为 True；否则为 False。
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
            self.showTip("没有被设置为启动启用状态的快捷键方案，键盘监听器未启动。")
            return None
        self.showTip(f"启动键盘监听器，监听快捷键方案: {self.activeScheme['name']}")
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
        if self.activeScheme is None:
            self.hasTriggeredCurrentPress = False
            if self.listener is not None and self.isListening:
                self.listener.stop()
                self.isListening = False
            return None

        if self.listener is None or not self.isListening:
            self._buildListener()
            return self.start()

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
        # 已经触发过一次后，必须等按键集合完全清空，才允许下一次触发
        if self.hasTriggeredCurrentPress:
            return

        pressedKeyNames = self._normalizePressedKeys(pressed_keys.getPressedKeys())
        matchedShortcut = self._findMatchedShortcut(pressedKeyNames)
        if matchedShortcut is None:
            return

        self.hasTriggeredCurrentPress = True
        self._executeShortcut(matchedShortcut)

    def handleKeyRelease(self, key, pressed_keys):
        # 只有所有键都松开后，才把“已触发”状态清掉
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
        """把单个按键对象统一成字符串。"""
        if key is None:
            return None
        # 特殊键（如 Key.ctrl、Key.alt）
        if hasattr(key, "name"):
            return self._normalizeAlias(key.name.lower())
        # 普通字符键（如 KeyCode）
        keyName = getattr(key, "char", None)
        if keyName:
            return keyName.lower()
        # ★ 关键修复：char 为 None 时，用 vk 虚拟键码还原
        vk = getattr(key, "vk", None)
        if vk is not None:
            # 数字键 0-9（vk 码 48-57）
            if 48 <= vk <= 57:
                return chr(vk)
            # 字母键 A-Z（vk 码 65-90）
            if 65 <= vk <= 90:
                return chr(vk).lower()
        return None

    def _normalizeAlias(self, keyName):
        """把不同写法统一成同一种名称，避免配置和监听值对不上。"""
        aliasMap = {
            "ctrl_l": "ctrl",
            "ctrl_r": "ctrl",
            "control_l": "ctrl",
            "control_r": "ctrl",
            "shift_l": "shift",
            "shift_r": "shift",
            "alt_l": "alt",
            "alt_r": "alt",
            "cmd": "cmd",
            "command": "cmd",
            "windows": "cmd",
            "option": "alt",
        }
        if keyName in aliasMap:
            return aliasMap[keyName]
        return keyName

    def _parseKeyCombination(self, keyCombination):
        """把配置里的组合键字符串拆成集合。"""
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
        """找出当前按键集合匹配的快捷键。"""
        matchedShortcut: dict | None = None
        matchedLength = -1
        for shortcut in self.activeShortcuts:
            if not shortcut.get("enabled", False):
                continue
            shortcutKeys = self._parseKeyCombination(shortcut.get("keyCombination", ""))
            if not shortcutKeys:
                continue
            # 必须完全一致才算触发，避免半套按键误触发
            if shortcutKeys == pressedKeyNames and len(shortcutKeys) > matchedLength:
                matchedShortcut = shortcut
                matchedLength = len(shortcutKeys)
        return matchedShortcut

    def _executeShortcut(self, shortcut: dict):
        """动作分发器：根据 action 类型派发到具体的执行方法。"""
        shortcutName = shortcut.get("name", "")
        action = shortcut.get("action", "")
        actionParams = shortcut.get("actionParams", {})

        if not action:
            self.showTip(f"快捷键 '{shortcutName}' 没有配置动作。")
            return

        # 建立动作映射表 (策略模式)
        actionMap = {
            "pasteText": self._doPasteText,
            "systemCommand": self._doSystemCommand,
            "openPath": self._doOpenPath,
        }

        targetAction = actionMap.get(action)
        if targetAction is None:
            self.showTip(f"未知的动作类型: {action}", title="执行错误")
            return

        try:
            targetAction(actionParams)
        except Exception as e:
            self.showTip(f"执行动作 '{action}' 失败:\n{str(e)}", title="执行错误")

    def _doPasteText(self, params):
        """动作：模拟粘贴文本"""
        text = params.get("text", "")
        if not text:
            return

        # 1. 将文本复制到剪贴板 (使用 pywin32)
        wc.OpenClipboard()
        wc.EmptyClipboard()
        wc.SetClipboardData(wc.CF_UNICODETEXT, text)
        wc.CloseClipboard()

        # 2. 释放可能还按着的修饰键，否则会变成 Ctrl+Alt+V
        import time
        kb = keyboard.Controller()
        kb.release(keyboard.Key.ctrl)
        kb.release(keyboard.Key.alt)
        kb.release(keyboard.Key.shift)
        time.sleep(0.05)  # 给系统一点时间处理释放事件

        # 3. 模拟按下 Ctrl+V 粘贴
        with kb.pressed(keyboard.Key.ctrl):
            kb.press('v')
            kb.release('v')

    def _doSystemCommand(self, params):
        """动作：执行系统命令"""
        print("准备执行系统命令，参数:", params)
        pass

    def _doOpenPath(self, params):
        """动作：打开程序/文件"""
        print("准备打开路径，参数:", params)
        pass

