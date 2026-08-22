''' 具体的动作执行逻辑实现 '''
import os
import sys
import time
import webbrowser
import subprocess
import win32clipboard as wc
from pynput import keyboard
from utils.actionRegistry import registerActionHandler, ACTION_REGISTRY


def doPasteText(params: dict):
    """动作：模拟粘贴文本"""
    text = params.get("text", "")
    if not text:
        return

    # 1. 将文本复制到剪贴板 (修复纯数字等特定字符串导致 UnicodeDecodeError 的底层 Bug)
    wc.OpenClipboard()
    wc.EmptyClipboard()
    # 手动编码为 UTF-16 LE，并强制加上双字节结束符 \x00\x00，防止底层越界读取
    data = text.encode('utf-16-le') + b'\x00\x00'
    wc.SetClipboardData(wc.CF_UNICODETEXT, data)
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
    # 使用 KeyCode.from_vk(86) 直接指定 V 键的虚拟键码，绕过 pynput 的字符编码解析
    v_key = keyboard.KeyCode.from_vk(86)
    with kb.pressed(keyboard.Key.ctrl):
        kb.press(v_key)
        kb.release(v_key)


def _open_target(target: str):
    """跨平台的打开路径/网址辅助函数"""
    if sys.platform == "win32":
        os.startfile(target)
    elif sys.platform == "darwin":
        subprocess.run(['open', target])
    else:
        subprocess.run(['xdg-open', target])


def doOpenPath(params: dict):
    """动作：打开路径/网址"""
    target = params.get("path", "").strip()
    mode = params.get("mode", "系统默认行为")  # 获取打开模式

    if not target:
        return

    try:
        # 1. 明确的网址前缀
        if target.startswith(("http://", "https://", "ftp://", "mailto:")):
            if mode == "强制打开新窗口":
                webbrowser.open_new(target)  # 尝试新窗口
            else:
                webbrowser.open(target)  # 交给浏览器（通常是在当前窗口开新标签页并聚焦）
            return

        # 2. 本地路径处理
        local_path = os.path.normpath(target)
        if os.path.exists(local_path):
            if mode == "强制打开新窗口" and sys.platform == "win32":
                # Windows下强制资源管理器开新窗口
                subprocess.run(['explorer.exe', local_path], shell=True)
            else:
                # 智能复用：系统默认行为
                # 对于文件夹，如果已打开，系统通常会自动聚焦到该窗口
                _open_target(local_path)
            return

        # 3. 兜底：不带协议的网址 (如 www.baidu.com)
        if "." in target and not os.path.exists(local_path):
            webbrowser.open(target)
            return

        # 真的打不开
        raise FileNotFoundError(f"找不到路径或无法识别: {target}")

    except Exception as e:
        raise RuntimeError(f"打开路径失败:\n{str(e)}")


# ★ 在模块加载时，将函数注册到动作注册表 ★
def initActionHandlers():
    registerActionHandler("pasteText", doPasteText)
    registerActionHandler("openPath", doOpenPath)

    for action_def in ACTION_REGISTRY:
        # 跳过 "（无动作）" 这个特殊动作
        if action_def.key == "":
            continue
        if action_def.handler is None:
            raise RuntimeError(f"动作 '{action_def.displayName}' 未注册执行逻辑！")
