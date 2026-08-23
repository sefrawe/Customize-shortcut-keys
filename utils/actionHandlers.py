''' 具体的动作执行逻辑实现 '''
import os
import subprocess
import sys
import time
import webbrowser

import win32clipboard as wc
from pynput import keyboard

from utils.actionRegistry import registerActionHandler, ACTION_REGISTRY

import shlex

def _simulate_input(text: str):
    """将文本放入剪贴板并模拟 Ctrl+V 粘贴"""
    if not text:
        return

    # 1. 将文本复制到剪贴板
    wc.OpenClipboard()
    wc.EmptyClipboard()
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
    v_key = keyboard.KeyCode.from_vk(86)
    with kb.pressed(keyboard.Key.ctrl):
        kb.press(v_key)
        kb.release(v_key)


def doPasteText(params: dict):
    """动作：模拟粘贴文本"""
    text = params.get("text", "")
    _simulate_input(text)


def doInsertDateTime(params: dict):
    """动作：插入当前日期时间"""
    fmt = params.get("format", "%Y-%m-%d %H:%M:%S")
    try:
        # 根据格式获取当前时间字符串
        current_time_str = time.strftime(fmt)
        # 复用粘贴逻辑输入时间
        _simulate_input(current_time_str)
    except Exception as e:
        # 捕获不合法的格式化字符串
        raise RuntimeError(f"时间格式错误:\n{str(e)}")


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


def doMediaControl(params: dict):
    """动作：媒体与音量控制"""
    action = params.get("action", "播放/暂停")
    kb = keyboard.Controller()

    # 将用户选择的操作映射到 pynput 的多媒体按键对象
    media_key_map = {
        "播放/暂停": keyboard.Key.media_play_pause,
        "上一首": keyboard.Key.media_previous,
        "下一首": keyboard.Key.media_next,
        "音量加": keyboard.Key.media_volume_up,
        "音量减": keyboard.Key.media_volume_down,
        "静音": keyboard.Key.media_volume_mute
    }

    target_key = media_key_map.get(action)
    if target_key is None:
        return

    try:
        # 模拟按下并释放多媒体按键
        kb.press(target_key)
        kb.release(target_key)
    except Exception as e:
        raise RuntimeError(f"执行媒体控制失败:\n{str(e)}")


def doCustomCommand(params: dict):
    """动作：执行自定义命令 (暂不包含安全校验与黑名单)"""
    command = params.get("command", "").strip()
    executable = params.get("executable", "cmd").strip()
    execMode = params.get("execMode", "后台静默执行")
    workingDir = params.get("workingDir", "").strip()

    # ★ 核心安全校验：工作目录绝对不能为空
    if not workingDir:
        raise RuntimeError("安全限制：工作目录为必填项，不能为空！")

    # ★ 校验工作目录是否真实存在且是文件夹
    if not os.path.isdir(workingDir):
        raise RuntimeError(f"工作目录不存在或不是一个有效的文件夹:\n{workingDir}")

    if not command:
        return

    # 处理多行命令，将换行符替换为 cmd 可识别的连接符 &
    # 如果是 cmd，将 \n 替换为 &
    if "cmd" in executable.lower():
        command = command.replace('\n', ' & ')
    # 如果是 powershell，将 \n 替换为 ;
    elif "powershell" in executable.lower() or "pwsh" in executable.lower():
        command = command.replace('\n', ' ; ')

    try:
        is_win = sys.platform == "win32"
        exe_lower = executable.lower()

        # 判断使用的 shell 类型，以便适配不同的启动参数 (/c, /k, -Command 等)
        is_cmd = "cmd" in exe_lower
        is_ps = "powershell" in exe_lower or "pwsh" in exe_lower

        # ★ 提前定义好 Windows 下的窗口标志位
        no_window_flag = subprocess.CREATE_NO_WINDOW if is_win else 0
        new_console_flag = subprocess.CREATE_NEW_CONSOLE if is_win else 0

        # ============ 1. 后台静默执行 ============
        if execMode == "后台静默执行":
            if is_win:
                if is_cmd:
                    command = command.replace('\n', ' & ')
                    subprocess.Popen(['cmd', '/c', command], cwd=workingDir, creationflags=no_window_flag)
                elif is_ps:
                    command = command.replace('\n', ' ; ')
                    subprocess.Popen(['powershell', '-NoProfile', '-Command', command], cwd=workingDir,
                                     creationflags=no_window_flag)
                else:
                    # 直接用列表传参，list2cmdline 自动处理路径空格
                    subprocess.Popen([executable, '-c', command], cwd=workingDir, creationflags=no_window_flag)
            else:
                subprocess.Popen([executable, '-c', command], cwd=workingDir)

        # ============ 2. 弹出终端并保持 ============
        elif execMode == "弹出终端并保持":
            if is_win:
                if is_cmd:
                    command = command.replace('\n', ' & ')
                    subprocess.Popen(['cmd', '/k', command], cwd=workingDir, creationflags=new_console_flag)
                elif is_ps:
                    command = command.replace('\n', ' ; ')
                    subprocess.Popen(['powershell', '-NoExit', '-Command', command], cwd=workingDir,
                                     creationflags=new_console_flag)
                else:
                    # ★ 不用 cmd /k 包裹，改为在代码末尾追加 input() 阻塞
                    if 'python' in executable.lower():
                        kept_command = command + '\ninput("\\n--- 执行完毕，按回车键关闭 ---")'
                        subprocess.Popen([executable, '-c', kept_command], cwd=workingDir,
                                         creationflags=new_console_flag)
                    else:
                        # 非 Python 的兜底方案
                        subprocess.Popen([executable, '-c', command], cwd=workingDir, creationflags=new_console_flag)
            else:
                subprocess.Popen(['xterm', '-hold', '-e', executable, '-c', command], cwd=workingDir)

        # ============ 3. 弹出终端执行后关闭 ============
        elif execMode == "弹出终端执行后关闭":
            if is_win:
                if is_cmd:
                    command = command.replace('\n', ' & ')
                    subprocess.Popen(['cmd', '/c', command], cwd=workingDir, creationflags=new_console_flag)
                elif is_ps:
                    command = command.replace('\n', ' ; ')
                    subprocess.Popen(['powershell', '-NoProfile', '-Command', command], cwd=workingDir,
                                     creationflags=new_console_flag)
                else:
                    # 直接用列表传参，执行完自然关闭
                    subprocess.Popen([executable, '-c', command], cwd=workingDir, creationflags=new_console_flag)
            else:
                subprocess.Popen(['xterm', '-e', executable, '-c', command], cwd=workingDir)

    except Exception as e:
        raise RuntimeError(f"执行命令失败:\n{str(e)}")


# ★ 在模块加载时，将函数注册到动作注册表 ★
def initActionHandlers():
    registerActionHandler("pasteText", doPasteText)
    registerActionHandler("openPath", doOpenPath)
    registerActionHandler("mediaControl", doMediaControl)
    registerActionHandler("insertDateTime", doInsertDateTime)
    registerActionHandler("customCommand", doCustomCommand)

    for action_def in ACTION_REGISTRY:
        # 跳过 "（无动作）" 这个特殊动作
        if action_def.key == "":
            continue
        if action_def.handler is None:
            raise RuntimeError(f"动作 '{action_def.displayName}' 未注册执行逻辑！")
