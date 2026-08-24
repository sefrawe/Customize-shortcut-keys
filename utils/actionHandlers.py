''' 具体的动作执行逻辑实现 '''

import os
import re
import sys
import time
import subprocess
import threading
import webbrowser

import win32clipboard as wc
from pynput import keyboard,mouse

from utils.actionRegistry import registerActionHandler, ACTION_REGISTRY
from utils.interpreterRegistry import getInterpreterSpec
from core.configManager import loadUserBlacklist




# ==================== 工具函数 ====================

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

    # 2. 释放可能还按着的修饰键（防止 Ctrl+V 变成 Ctrl+Ctrl+V）
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


# ==================== 动作处理器 ====================
# 所有 handler 的签名统一为 (params: dict, context: dict | None = None)
# context 由 Executor 在调用时注入，包含 confirm_callback 等跨线程通信回调。
# 不需要 context 的 handler 直接忽略该参数即可。

def doPasteText(params: dict, context: dict | None = None):
    """动作：模拟粘贴文本"""
    text = params.get("text", "")
    _simulate_input(text)


def doInsertDateTime(params: dict, context: dict | None = None):
    """动作：插入当前日期时间"""
    fmt = params.get("format", "%Y-%m-%d %H:%M:%S")
    try:
        current_time_str = time.strftime(fmt)
        _simulate_input(current_time_str)
    except Exception as e:
        raise RuntimeError(f"时间格式错误:\n{str(e)}")


def _open_target(target: str):
    """跨平台的打开路径/网址辅助函数"""
    if sys.platform == "win32":
        os.startfile(target)
    elif sys.platform == "darwin":
        subprocess.run(['open', target])
    else:
        subprocess.run(['xdg-open', target])


def doOpenPath(params: dict, context: dict | None = None):
    """动作：打开路径/网址"""
    target = params.get("path", "").strip()
    mode = params.get("mode", "系统默认行为")

    if not target:
        return

    try:
        # 1. 明确的网址前缀
        if target.startswith(("http://", "https://", "ftp://", "mailto:")):
            if mode == "强制打开新窗口":
                webbrowser.open_new(target)
            else:
                webbrowser.open(target)
            return

        # 2. 本地路径处理
        local_path = os.path.normpath(target)
        if os.path.exists(local_path):
            if mode == "强制打开新窗口" and sys.platform == "win32":
                subprocess.run(['explorer.exe', local_path], shell=True)
            else:
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


def doMediaControl(params: dict, context: dict | None = None):
    """动作：媒体与音量控制"""
    action = params.get("action", "播放/暂停")
    kb = keyboard.Controller()

    media_key_map = {
        "播放/暂停": keyboard.Key.media_play_pause,
        "上一首": keyboard.Key.media_previous,
        "下一首": keyboard.Key.media_next,
        "音量加": keyboard.Key.media_volume_up,
        "音量减": keyboard.Key.media_volume_down,
        "静音": keyboard.Key.media_volume_mute,
    }

    target_key = media_key_map.get(action)
    if target_key is None:
        return

    try:
        kb.press(target_key)
        kb.release(target_key)
    except Exception as e:
        raise RuntimeError(f"执行媒体控制失败:\n{str(e)}")


def doCustomCommand(params: dict, context: dict | None = None):
    """
    动作：执行自定义命令（数据驱动 + 三层安全拦截）
    (注释保持原有结构，仅修改内部实现)
    """
    # ──────────────────────────────────────────────
    # 第一步：提取参数 & 基础校验
    # ──────────────────────────────────────────────
    command = params.get("command", "").strip()

    # ★ 核心改动：提取解释器类型和绝对路径 ★
    interpreterType = params.get("interpreterType", "cmd").strip()
    executablePath = params.get("executablePath", "").strip()

    execMode = params.get("execMode", "后台静默执行")
    workingDir = params.get("workingDir", "").strip()

    # needConfirm 可能是布尔值（从 UI 保存）或字符串（用户手改 JSON）
    needConfirm = params.get("needConfirm", True)
    if isinstance(needConfirm, str):
        needConfirm = needConfirm.lower() in ("true", "1", "yes")

    # ★ 核心安全校验：工作目录绝对不能为空
    if not workingDir:
        raise RuntimeError("安全限制：工作目录为必填项，不能为空！")
    if not os.path.isdir(workingDir):
        raise RuntimeError(f"工作目录不存在或不是一个有效的文件夹:\n{workingDir}")

    if not command:
        return  # 空命令直接返回，不报错

    # ★ 核心安全校验：执行程序路径绝对不能为空
    if not executablePath:
        raise RuntimeError("安全限制：执行程序路径为必填项，不能为空！")

    # ──────────────────────────────────────────────
    # 第二步：获取解释器规格 & 防呆校验（数据驱动核心）
    # ──────────────────────────────────────────────
    # 根据用户填写的绝对路径，去解释器注册表中模糊匹配对应的规格
    # 比如：路径包含 "cmd" 匹配 cmd 规格；包含 "powershell" 匹配 powershell 规格
    spec = getInterpreterSpec(executablePath)

    # ★ 防呆校验：检查用户选择的"类型"与填写的"路径"是否一致 ★
    # 比如用户选了 python，但路径还是默认的 cmd.exe，这里会被拦截
    # spec.name != "unknown" 是为了放行未注册的自定义解释器（虽然目前UI限制了，但留个口子）
    if spec.name != interpreterType and spec.name != "unknown":
        raise RuntimeError(
            f"解释器类型与路径不匹配！\n"
            f"你选择了 '{interpreterType}'，但填写的路径似乎是 '{spec.name}'。\n"
            f"请检查路径是否填写正确。"
        )

    # ──────────────────────────────────────────────
    # 第三步：安全拦截 — 第 1 层（强制黑名单，不可逾越）
    # ──────────────────────────────────────────────
    for keyword in spec.danger_keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, command, re.IGNORECASE):
            raise RuntimeError(
                f"⛔ 命令被拒绝执行！\n"
                f"命中强制黑名单关键词: '{keyword}'\n"
                f"解释器: {spec.name}"
            )

    # ──────────────────────────────────────────────
    # 第四步：安全拦截 — 第 2 层（用户自定义黑名单）
    # ──────────────────────────────────────────────
    try:
        userBlacklist = loadUserBlacklist()
    except Exception:
        userBlacklist = {}

    hitUserBlacklist = []
    command_lower = command.lower()
    current_interpreter = spec.name
    interpreter_keywords = userBlacklist.get(current_interpreter, [])

    for keyword in interpreter_keywords:
        if keyword.lower() in command_lower:
            hitUserBlacklist.append(keyword)

    # ──────────────────────────────────────────────
    # 第五步：安全拦截 — 第 3 层（常规确认 needConfirm）
    # ──────────────────────────────────────────────
    needPopup = needConfirm or len(hitUserBlacklist) > 0

    if needPopup:
        confirm_callback = (context or {}).get("confirm_callback")
        if confirm_callback:
            messages = []
            if hitUserBlacklist:
                messages.append(
                    f"⚠️ 命令命中自定义黑名单:\n"
                    f" {', '.join(hitUserBlacklist)}"
                )
            if needConfirm:
                messages.append("ℹ️ 此快捷键设置了执行前确认。")
            messages.append(f"\n即将以 {spec.name} 执行以下命令:")
            messages.append(f"{'─' * 40}")
            messages.append(command)
            messages.append(f"{'─' * 40}")
            messages.append(f"工作目录: {workingDir}")
            messages.append(f"执行模式: {execMode}")
            popup_message = "\n".join(messages)

            event = threading.Event()
            result_holder = [False]
            confirm_callback(popup_message, result_holder, event)
            event.wait()

            if not result_holder[0]:
                return
        else:
            pass

    # ──────────────────────────────────────────────
    # 第六步：构建命令参数（数据驱动组装）
    # ──────────────────────────────────────────────
    processed_command = command.replace('\n', spec.multiline_sep)

    is_win = sys.platform == "win32"
    no_window_flag = subprocess.CREATE_NO_WINDOW if is_win else 0
    new_console_flag = subprocess.CREATE_NEW_CONSOLE if is_win else 0

    if execMode == "弹出终端并保持":
        cmd_args = spec.keep_params if spec.keep_params else spec.eval_params
        creation_flags = new_console_flag
    elif execMode == "弹出终端执行后关闭":
        cmd_args = spec.eval_params
        creation_flags = new_console_flag
    else:  # 默认：后台静默执行
        cmd_args = spec.eval_params
        creation_flags = no_window_flag

    # ──────────────────────────────────────────────
    # 第七步：执行命令
    # ──────────────────────────────────────────────
    try:
        if not is_win and execMode != "后台静默执行":
            hold_flag = ['-hold'] if execMode == "弹出终端并保持" else []
            subprocess.Popen(
                ['xterm'] + hold_flag + ['-e', executablePath] + cmd_args + [processed_command],
                cwd=workingDir
            )
        else:
            # ★ 注意这里：使用 executablePath 替代原来的 executable 变量 ★
            subprocess.Popen(
                [executablePath] + cmd_args + [processed_command],
                cwd=workingDir,
                creationflags=creation_flags
            )
    except Exception as e:
        raise RuntimeError(f"执行命令失败:\n{str(e)}")

# ==================== 鼠标动作处理器 ====================

# 按钮映射字典
_MOUSE_BUTTON_MAP = {
    "左键": mouse.Button.left,
    "右键": mouse.Button.right,
    "中键": mouse.Button.middle,
    "侧键前进": mouse.Button.x1,
    "侧键后退": mouse.Button.x2,
}

def doMouseMoveTo(params: dict, context: dict | None = None):
    """动作：鼠标移动到指定坐标"""
    try:
        x = int(float(params.get("x", "0")))
        y = int(float(params.get("y", "0")))
    except (ValueError, TypeError):
        raise RuntimeError("X 或 Y 坐标不是有效的整数")

    duration_str = str(params.get("duration", "0")).strip()
    try:
        duration = float(duration_str)
    except ValueError:
        duration = 0.0

    m = mouse.Controller()

    if duration <= 0:
        # 瞬移
        m.position = (x, y)
    else:
        # 平滑移动：线性插值，每 5ms 移动一步
        start_x, start_y = m.position
        steps = max(int(duration / 0.005), 1)
        for i in range(1, steps + 1):
            progress = i / steps
            cur_x = int(start_x + (x - start_x) * progress)
            cur_y = int(start_y + (y - start_y) * progress)
            m.position = (cur_x, cur_y)
            time.sleep(duration / steps)

    time.sleep(0.05)

def doMouseMoveStep(params: dict, context: dict | None = None):
    """动作：鼠标步进移动（微调）"""
    direction = params.get("direction", "右")
    try:
        distance = int(float(params.get("distance", 50)))
    except (ValueError, TypeError):
        distance = 50

    m = mouse.Controller()
    cur_x, cur_y = m.position

    if direction == "上":
        m.position = (cur_x, cur_y - distance)
    elif direction == "下":
        m.position = (cur_x, cur_y + distance)
    elif direction == "左":
        m.position = (cur_x - distance, cur_y)
    elif direction == "右":
        m.position = (cur_x + distance, cur_y)

    time.sleep(0.05)

def doMouseClick(params: dict, context: dict | None = None):
    """动作：模拟鼠标点击"""
    button_name = params.get("button", "左键")
    count = params.get("count", "单击")
    moveToFirst = params.get("moveToFirst", False)
    if isinstance(moveToFirst, str):
        moveToFirst = moveToFirst.lower() in ("true", "1", "yes")

    m = mouse.Controller()
    button = _MOUSE_BUTTON_MAP.get(button_name, mouse.Button.left)

    # 如果需要先移动到指定坐标
    if moveToFirst:
        try:
            x = int(float(params.get("x", "0")))
            y = int(float(params.get("y", "0")))
            m.position = (x, y)
            time.sleep(0.05)
        except (ValueError, TypeError):
            raise RuntimeError("X 或 Y 坐标不是有效的整数")

    # 执行点击
    click_count = 2 if count == "双击" else 1
    try:
        m.click(button, click_count)
    except Exception as e:
        # 侧键可能不支持，回退到左键
        if button_name in ("侧键前进", "侧键后退"):
            try:
                m.click(mouse.Button.left, click_count)
            except Exception:
                raise RuntimeError(f"鼠标点击失败，且侧键可能不支持:\n{str(e)}")
        else:
            raise RuntimeError(f"鼠标点击失败:\n{str(e)}")

    time.sleep(0.05)

def doMouseScroll(params: dict, context: dict | None = None):
    """动作：鼠标滚轮滚动"""
    direction = params.get("direction", "向上")
    try:
        amount = int(float(params.get("amount", "3")))
    except (ValueError, TypeError):
        raise RuntimeError("滚动量不是有效的整数")

    m = mouse.Controller()
    # pynput: dy > 0 向上滚, dy < 0 向下滚
    dy = amount if direction == "向上" else -amount

    try:
        m.scroll(0, dy)
    except Exception as e:
        raise RuntimeError(f"滚轮滚动失败:\n{str(e)}")

    time.sleep(0.05)

def doMouseDrag(params: dict, context: dict | None = None):
    """动作：鼠标拖拽"""
    try:
        startX = int(float(params.get("startX", "0")))
        startY = int(float(params.get("startY", "0")))
        endX = int(float(params.get("endX", "0")))
        endY = int(float(params.get("endY", "0")))
    except (ValueError, TypeError):
        raise RuntimeError("起点或终点坐标不是有效的整数")

    m = mouse.Controller()

    try:
        # 1. 移动到起点
        m.position = (startX, startY)
        time.sleep(0.1)

        # 2. 按下左键
        m.press(mouse.Button.left)
        time.sleep(0.1)

        # 3. 分步移动到终点（模拟真实拖拽手感，避免某些程序检测到瞬移）
        steps = 20
        for i in range(1, steps + 1):
            progress = i / steps
            cur_x = int(startX + (endX - startX) * progress)
            cur_y = int(startY + (endY - startY) * progress)
            m.position = (cur_x, cur_y)
            time.sleep(0.01)

        # 4. 确保到达终点
        m.position = (endX, endY)
        time.sleep(0.05)

        # 5. 松开左键
        m.release(mouse.Button.left)
    except Exception as e:
        # 异常时确保释放按键，防止鼠标卡死
        try:
            m.release(mouse.Button.left)
        except Exception:
            pass
        raise RuntimeError(f"鼠标拖拽失败:\n{str(e)}")

    time.sleep(0.05)



# ==================== 注册 ====================

def initActionHandlers():
    """在模块加载时，将所有 handler 函数注册到动作注册表"""
    registerActionHandler("pasteText", doPasteText)
    registerActionHandler("openPath", doOpenPath)
    registerActionHandler("mediaControl", doMediaControl)
    registerActionHandler("insertDateTime", doInsertDateTime)
    registerActionHandler("customCommand", doCustomCommand)
    registerActionHandler("mouseMoveTo", doMouseMoveTo)
    registerActionHandler("mouseMoveStep", doMouseMoveStep)
    registerActionHandler("mouseClick", doMouseClick)
    registerActionHandler("mouseScroll", doMouseScroll)
    registerActionHandler("mouseDrag", doMouseDrag)

    for action_def in ACTION_REGISTRY:
        # 跳过 "（无动作）" 这个特殊动作
        if action_def.key == "":
            continue
        if action_def.handler is None:
            raise RuntimeError(f"动作 '{action_def.displayName}' 未注册执行逻辑！")
