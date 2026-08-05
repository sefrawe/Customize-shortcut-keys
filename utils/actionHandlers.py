''' 具体的动作执行逻辑实现 '''
import time
import win32clipboard as wc
from pynput import keyboard
from utils.actionRegistry import registerActionHandler, ACTION_REGISTRY


def doPasteText(params: dict):
    """动作：模拟粘贴文本"""
    text = params.get("text", "")
    if not text:
        return

    # 1. 将文本复制到剪贴板
    wc.OpenClipboard()
    wc.EmptyClipboard()
    wc.SetClipboardData(wc.CF_UNICODETEXT, text)
    wc.CloseClipboard()

    # 2. 释放可能还按着的修饰键
    kb = keyboard.Controller()
    kb.release(keyboard.Key.ctrl_l)
    kb.release(keyboard.Key.ctrl_r)
    kb.release(keyboard.Key.alt_l)
    kb.release(keyboard.Key.alt_r)
    kb.release(keyboard.Key.shift_l)
    kb.release(keyboard.Key.shift_r)
    time.sleep(0.05)

    # 3. 模拟按下 Ctrl+V 粘贴
    with kb.pressed(keyboard.Key.ctrl):
        kb.press('v')
        kb.release('v')


def doSystemCommand(params: dict):
    print("准备执行系统命令，参数:", params)
    pass


def doOpenPath(params: dict):
    print("准备打开路径，参数:", params)
    pass


# ★ 在模块加载时，将函数注册到动作注册表 ★
def initActionHandlers():
    registerActionHandler("pasteText", doPasteText)
    # registerActionHandler("system_command", doSystemCommand)
    # registerActionHandler("openPath", doOpenPath)
    for action_def in ACTION_REGISTRY:
        # 跳过 "（无动作）" 这个特殊动作
        if action_def.key == "":
            continue
        if action_def.handler is None:
            raise RuntimeError(f"动作 '{action_def.displayName}' 未注册执行逻辑！")
