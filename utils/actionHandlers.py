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

from utils.keyValidator import validate_key_combination

from utils.vkKeyMap import NAME_TO_VK


# ==================== 工具函数 ====================

def _releaseHeldModifiers(kb: keyboard.Controller | None = None):
    """释放可能仍被物理按住的修饰键（左右变体全覆盖）。

    背景：用户以 ctrl+alt+k 触发快捷键时，手指还压着 Ctrl/Alt，
    此时不释放就直接模拟其他键，发出去的组合会被污染（如变成 Ctrl+Alt+V）。

    说明：
    1. 原为 _simulate_input 的内联代码，现抽成公共函数，
       供 粘贴文本 / 插入日期时间 / 模拟按键(simulateKeys) 三处共用。
    2. 特意不处理 Win/Cmd 键 —— 模拟期间松开 Win 可能误触开始菜单等
       系统行为，风险大于收益。此取舍与抽函数前的原始行为完全一致。
    """
    if kb is None:
        kb = keyboard.Controller()
    kb.release(keyboard.Key.ctrl_l)
    kb.release(keyboard.Key.ctrl_r)
    kb.release(keyboard.Key.alt_l)
    kb.release(keyboard.Key.alt_r)
    kb.release(keyboard.Key.shift_l)
    kb.release(keyboard.Key.shift_r)


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

    # 2. 释放可能还按着的修饰键（改为调用公共函数，逻辑不变）
    kb = keyboard.Controller()
    _releaseHeldModifiers(kb)
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

# ==================== 新增：键盘-模拟按键（仅动作组内可见） ====================

# 别名归一化表：与 executor._normalizeAlias 口径完全一致。
# 不直接 import executor 的原因：executor.py 导入了本模块(actionHandlers)，
# 反向导入会形成循环依赖，故维护一份最小副本，修改时需两边同步。
_SIMULATE_ALIAS_MAP = {
    "control": "ctrl", "control_l": "ctrl_l", "control_r": "ctrl_r",
    "option": "alt", "option_l": "alt_l", "option_r": "alt_r",
    "command": "cmd", "windows": "cmd",
}

# 修饰键集合：解析出的 token 若属于这里，则作为"按住不放"的前缀处理；
# 其余 token 视作"末位实体键"。允许纯修饰键组合（如只发一个 shift），
# 这恰好支撑了 hint 里"切输入法"配方——很多机器单击 Shift 即切换中英。
_SIMULATE_MODIFIER_TOKENS = {
    "ctrl", "ctrl_l", "ctrl_r",
    "shift", "shift_l", "shift_r",
    "alt", "alt_l", "alt_r",
    "cmd", "cmd_l", "cmd_r",
}

# 小键盘运算键与所有常规字符键的 vk 映射已并入 utils/vkKeyMap.NAME_TO_VK，
# 监听端与发送端共用同一张总表，杜绝两端各养一份映射漂移的可能。


# 特殊键白名单：与 keyValidator.LEGAL_KEYS 的"特殊键"区段一一对应，
# 这些名字恰好都是 pynput.Key 的真实属性名，可直接 getattr 取用。
# （显式列举而非盲目 getattr，避免拿到注册表之外的意外属性）
_SIMULATE_SPECIAL_KEYS = {
    "space", "tab", "enter", "esc", "up", "down", "left", "right",
    "backspace", "delete", "home", "end", "page_up", "page_down",
    "caps_lock", "insert",
    "print_screen",  # 与 LEGAL_KEYS 同步收录；pynput.Key.print_screen 属性直取即可

}


def _parseSimulateTokens(key_str: str) -> list[str]:
    """把按键组合字符串拆成 token 列表。

    拆分规则与 keyValidator.validate_key_combination 保持同源：
    转 小写 -> 按 '+' 分割 -> 去空格和空片段。

    【直通原则】不做任何别名兑换（plus 分支已随决策5删除）：走到这里的
    输入必然刚通过校验器放行，而校验器根本不接受 plus/'+' 这类写法。
    """
    return [p.strip().lower() for p in key_str.split('+') if p.strip()]


def _tokenToPynputObject(token: str):
    """单个 token -> pynput 可按压对象（Key 枚举或 KeyCode）。查不到就抛错。

    映射原则【vk-first 双端对称】：
      · 常规字符键（字母/主键盘数字/小键盘数字与运算键/OEM标点11键）
        一律先查 vkKeyMap.NAME_TO_VK，再 KeyCode.from_vk 直发——
        与监听端 executor._normalizeSingleKey 共用同一张总表，
        保证"它能听到的，就一定能发出去"；同样免疫布局与大写锁定差异。
      · 特殊键与修饰键不属于字符键域，保持 pynput.Key 属性直取：
          - 修饰键 ctrl_l / alt_r ...（组合前缀，按住不放）
          - 功能键 f1~f12、space/tab/enter、方向键、编辑键区等
    """
    # 0) 等价拼写收敛（control/windows/command/option → 正名），
    #    口径与 executor._normalizeAlias 一致；_SIMULATE_ALIAS_MAP 因此生效
    token = _SIMULATE_ALIAS_MAP.get(token, token)

    # 1) ★ 常规字符键主路径：总表命中即直发虚拟键码。
    #    覆盖范围与监听端识别范围严格相等（62 键，见 vkKeyMap 自测数）。
    vk = NAME_TO_VK.get(token)
    if vk is not None:
        return keyboard.KeyCode.from_vk(vk)

    # 2) 修饰键：pynput.Key 真实属性名，作为前缀按压
    if token in _SIMULATE_MODIFIER_TOKENS:
        return getattr(keyboard.Key, token)

    # 3) 功能键 F1~F12：先验证 f 后必为数字且落在 1~12，
    #    防止把别的 f 开头单词误当功能键吞掉
    if len(token) >= 2 and token[0] == "f" and token[1:].isdigit():
        num = int(token[1:])
        if 1 <= num <= 12:
            return getattr(keyboard.Key, token)

    # 4) 其余特殊键白名单（与 keyValidator 特殊键区段一一对应）
    if token in _SIMULATE_SPECIAL_KEYS:
        return getattr(keyboard.Key, token)

    # 兜底防线：理论上经校验器放行的 token 都能命中以上分支；
    # 落到这里说明"校验器 ↔ vkKeyMap ↔ 白名单"三方出现了不同步。
    raise RuntimeError(
        f"未知的按键 token: '{token}'\n"
        f"（校验器与发送映射表不同步，请反馈此问题）"
    )


def doSimulateKeys(params: dict, context: dict | None = None):
    """动作：向当前活动窗口发送指定的【单个】按键组合（仅动作组内可用）。

    设计边界（勿越界回加）：
    - 一步只发一个组合：连发场景 = 复制 N 个步骤 + 每步延迟控制节奏；
    - 无重复次数、无按住时长：同上，属于动作组层的职责；
    - 保存时无格式校验（设计定稿方案A）：此处校验是唯一运行时防线，
      错误信息只会出现在试运行日志里，正式执行仅打印控制台。
    """
    # ── 第一步：取参数 ──
    keys = str(params.get("keys", "")).strip()
    if not keys:
        return  # 空参数静默返回（executor 层的必填校验通常拦不到手改 JSON 的空串）

    # ── 第二步：格式兜底校验（唯一防线，结果只进日志通道） ──
    is_valid, msg, cleaned = validate_key_combination(keys)
    if not is_valid:
        # 抛错给 ActionGroupPlayer 捕获 → 试运行日志可见 / 正式执行仅 print
        raise RuntimeError(
            f"按键组合格式不合法: {msg}\n"
            f"输入内容: {keys}\n"
            f"请在动作组编辑窗点「▶ 试运行」排查；可用键名参考快捷键录入规则。"
        )
    # ── 第三步：token 解析与分类 ──
    # token 化直接基于原始输入；cleaned 仅作门卫产物（现两者语义一致）
    tokens = _parseSimulateTokens(keys)
    modifier_objs: list = []   # 先按下的前缀（按住型）
    normal_objs: list = []     # 组合末位的实体键
    for raw in tokens:
        # ★ 先收敛等价拼写再做修饰键归类（A4 修复）：
        #   _SIMULATE_MODIFIER_TOKENS 只收正名，"control/windows" 等必须先转成
        #   正名才能命中集合，否则被误判为实体键导致按压顺序错乱
        t = _SIMULATE_ALIAS_MAP.get(raw, raw)
        obj = _tokenToPynputObject(t)  # 函数内部第0步再收敛一次，幂等无害
        if t in _SIMULATE_MODIFIER_TOKENS:
            modifier_objs.append(obj)
        else:
            normal_objs.append(obj)

    # 同名重复 token（如手滑写了 ctrl+ctrl）不特判：多按一次多放一次，无害且省分支。

    # ── 第四步：释放物理残留修饰键，防组合被污染（与粘贴文本共用逻辑）──
    kb = keyboard.Controller()
    _releaseHeldModifiers(kb)
    time.sleep(0.05)

    # ── 第五步：核心发送 —— 按下 → 微延时 → 释放 ──
    # pressed_stack 记录"实际成功按下"的对象，用于异常兜底逆序释放，
    # 防止中途出错导致按键卡死（与 mouseDrag 的保护思路一致）。
    pressed_stack: list = []
    try:
        # 5.1 先按住所有修饰键（顺序无关紧要，逆序释放即可）
        for obj in modifier_objs:
            kb.press(obj)
            pressed_stack.append(obj)
        # 5.2 再按下实体键（支持多实体键同时按住的场景，虽极少用到）
        for obj in normal_objs:
            kb.press(obj)
            pressed_stack.append(obj)
        # 5.3 约 30ms 微延时：给目标程序留出识别组合的时间窗，
        #     否则瞬时按下-释放可能被个别程序当作噪声过滤掉
        time.sleep(0.03)
    except Exception as e:
        raise RuntimeError(f"模拟按键失败:\n{str(e)}")
    finally:
        # 无论成功与否，一律逆序释放所有已按下的键，保证现场干净
        for obj in reversed(pressed_stack):
            try:
                kb.release(obj)
            except Exception:
                pass  # 释放失败不再抛出，避免掩盖原始错误

    # 无循环、无计时器 —— 到此即结束，节奏控制权完全交还给动作组的 delayAfter。


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


def doAppControl(params: dict, context: dict | None = None):
    """
    动作：操作软件自身 (无参数版)
    通过 context 中的 app_control_callback 将指令抛回给主线程执行，
    从而彻底规避跨线程操作 Tkinter UI 导致的崩溃问题。
    """
    command = params.get("command", "")
    if not command:
        return

    # 从上下文中获取主线程注入的回调函数
    app_control_callback = (context or {}).get("app_control_callback")
    if app_control_callback:
        # ==================== 设计25修改：移除目标方案参数 ====================
        # 因为 appControl 现在不再负责方案切换，所以只传 command，目标方案传空字符串
        app_control_callback(command, "")
        # =====================================================================
    else:
        print("警告：未配置 app_control_callback，无法执行软件控制指令。")


def doAppControlSafe(params: dict, context: dict | None = None):
    """
    动作：操作软件自身(安全版)
    与 doAppControl 逻辑相同，仅支持的指令受限。
    专供动作组使用，确保宏执行期间不会意外退出或切换方案。
    """
    command = params.get("command", "")
    if not command:
        return

    app_control_callback = (context or {}).get("app_control_callback")
    if app_control_callback:
        # 为了接口签名统一，安全版也传个空字符串作为 target_scheme
        app_control_callback(command, "")
    else:
        print("警告：未配置 app_control_callback，无法执行安全软件控制指令。")


# ==================== 设计25新增：独立的方案切换动作 ====================
def doSwitchScheme(params: dict, context: dict | None = None):
    """
    动作：切换启用方案
    将指定方案设为启用，并互斥禁用其他所有方案。
    如果传入的方案名为空字符串，则代表禁用所有方案。
    """
    # 提取下拉框选择的方案名 (如果选了"（无）"，存进 JSON 的就是空字符串)
    target_scheme = params.get("targetSchemeSelect", "").strip()

    app_control_callback = (context or {}).get("app_control_callback")
    if app_control_callback:
        # 复用主线程的 "启用指定方案" 指令通道
        # 注意：主线程的 _handle_app_control 会判断 target_scheme 是否为空
        app_control_callback("启用指定方案", target_scheme)
    else:
        print("警告：未配置 app_control_callback，无法执行方案切换指令。")


# =====================================================================


def doActionGroup(params: dict, context: dict | None = None):
    """动作：动作组执行入口"""
    # 提取常规参数
    stop_on_error = params.get("stopOnError", "停止整个动作组")
    steps = params.get("steps", [])
    # 提取新增的进阶参数
    confirm_all = params.get("confirmAllAtOnce", False)
    loop_count = params.get("loopCount", "1")
    max_exec_time = params.get("maxExecutionTime", "60")

    from utils.actionGroupExecutor import ActionGroupPlayer

    # 从 context 中获取 Executor 注入的中断事件，用于托盘紧急停止
    interrupt_event = (context or {}).get("interrupt_event")
    # ==================== Bug修复：获取软停止事件 ====================
    soft_stop_event = (context or {}).get("soft_stop_event")
    # ==============================================================

    # 实例化回放器，正式执行不传 log_callback(不输出到UI)
    player = ActionGroupPlayer(
        steps,
        stop_on_error,
        context,
        interrupt_event,
        # ==================== Bug修复：把软停止事件传进去 ====================
        soft_stop_event,
        # =================================================================
        log_callback=None,
        confirm_all=confirm_all,
        loop_count=loop_count,
        max_exec_time=max_exec_time
    )

    # 开始阻塞执行(此方法在 Executor 的子线程中运行)
    player.play()


# ==================== 注册 ====================
def initActionHandlers():
    """在模块加载时，将所有 handler 函数注册到动作注册表"""
    registerActionHandler("pasteText", doPasteText)
    registerActionHandler("openPath", doOpenPath)
    registerActionHandler("mediaControl", doMediaControl)
    registerActionHandler("insertDateTime", doInsertDateTime)
    registerActionHandler("customCommand", doCustomCommand)
    registerActionHandler("simulateKeys", doSimulateKeys)
    registerActionHandler("mouseMoveTo", doMouseMoveTo)
    registerActionHandler("mouseMoveStep", doMouseMoveStep)
    registerActionHandler("mouseClick", doMouseClick)
    registerActionHandler("mouseScroll", doMouseScroll)
    registerActionHandler("mouseDrag", doMouseDrag)
    registerActionHandler("appControl", doAppControl)
    registerActionHandler("appControlSafe", doAppControlSafe)
    registerActionHandler("switchScheme", doSwitchScheme)
    registerActionHandler("actionGroup", doActionGroup)

    for action_def in ACTION_REGISTRY:
        # 跳过 "（无动作）" 这个特殊动作
        if action_def.key == "":
            continue
        if action_def.handler is None:
            raise RuntimeError(f"动作 '{action_def.displayName}' 未注册执行逻辑！")
