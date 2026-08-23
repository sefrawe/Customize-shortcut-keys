''' 具体的动作执行逻辑实现 '''

import os
import re
import sys
import time
import subprocess
import threading
import webbrowser

import win32clipboard as wc
from pynput import keyboard

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

    ════════════════════════════════════════════════════════════
    【三层安全防御体系】（从严到松，逐层过滤）
    ════════════════════════════════════════════════════════════

    第 1 层 — 强制黑名单（不可逾越）：
        来源：解释器注册表 InterpreterSpec.danger_keywords
        匹配：正则 \\b关键字\\b 精确匹配（单词边界，防止误杀）
        行为：命中直接 raise RuntimeError 拒绝执行，不弹窗。

    第 2 层 — 用户自定义黑名单（强制确认）：
        来源：Global Settings.json 中的 userBlacklist 列表
        匹配：不区分大小写的子串包含检查（in 判断）
        行为：命中后触发跨线程确认弹窗，用户点"否"则终止。

    第 3 层 — 常规确认（needConfirm）：
        来源：快捷键配置中的 needConfirm 布尔值
        行为：为 True 时触发跨线程确认弹窗，用户点"否"则终止。

    如果第 2 层和第 3 层同时触发，只弹一次窗，合并提示信息。

    ════════════════════════════════════════════════════════════
    【跨线程确认机制】
    ════════════════════════════════════════════════════════════

    本函数运行在 Executor 的子线程中，而 Tkinter 的 messagebox
    必须在主线程调用。通信流程如下：

    子线程：                                    主线程：
    1. 创建 threading.Event()                   |
    2. 创建 result_holder = [False]             |
    3. 调用 confirm_callback(msg,              |
       result_holder, event)                    |
                                                ├──> 4. app.after(0, ...) 收到请求
                                                ├──> 5. messagebox.askyesno() 弹窗
                                                ├──> 6. 将结果存入 result_holder[0]
                                                └──> 7. event.set() 通知子线程
    8. event.wait() 阻塞解除 <────────────────────|
    9. 读取 result_holder[0] 判断是否继续          |
    """

    # ──────────────────────────────────────────────
    # 第一步：提取参数 & 基础校验
    # ──────────────────────────────────────────────

    command = params.get("command", "").strip()
    executable = params.get("executable", "cmd").strip()
    execMode = params.get("execMode", "后台静默执行")
    workingDir = params.get("workingDir", "").strip()

    # needConfirm 可能是布尔值（从 UI 保存）或字符串（用户手改 JSON）
    needConfirm = params.get("needConfirm", True)
    if isinstance(needConfirm, str):
        needConfirm = needConfirm.lower() in ("true", "1", "yes")

    # ★ 核心安全校验：工作目录绝对不能为空
    if not workingDir:
        raise RuntimeError("安全限制：工作目录为必填项，不能为空！")

    # ★ 校验工作目录是否真实存在且是文件夹
    if not os.path.isdir(workingDir):
        raise RuntimeError(f"工作目录不存在或不是一个有效的文件夹:\n{workingDir}")

    if not command:
        return  # 空命令直接返回，不报错

    # ──────────────────────────────────────────────
    # 第二步：获取解释器规格（数据驱动核心）
    # ──────────────────────────────────────────────

    spec = getInterpreterSpec(executable)

    # ──────────────────────────────────────────────
    # 第三步：安全拦截 — 第 1 层（强制黑名单，不可逾越）
    # ──────────────────────────────────────────────

    # 遍历当前解释器的 danger_keywords
    # 使用正则 \b关键字\b 进行单词边界精确匹配
    # 防止误杀（例如 echo format_this 中的 format 不会匹配，因为 _ 是单词字符）
    for keyword in spec.danger_keywords:
        # re.escape 防止关键字中包含正则特殊字符（如 . * 等）
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, command, re.IGNORECASE):
            # 命中强制黑名单，直接拒绝，不弹窗
            raise RuntimeError(
                f"⛔ 命令被拒绝执行！\n"
                f"命中强制黑名单关键词: '{keyword}'\n"
                f"解释器: {spec.name}"
            )

    # ──────────────────────────────────────────────
    # 第四步：安全拦截 — 第 2 层（用户自定义黑名单）
    # ──────────────────────────────────────────────

    # 从全局配置文件读取用户自定义黑名单字典
    try:
        userBlacklist = loadUserBlacklist()
    except Exception:
        userBlacklist = {}  # 读取失败时降级为空字典

    # 记录命中的用户黑名单关键词（用于弹窗提示）
    hitUserBlacklist = []
    command_lower = command.lower()

    # 获取当前解释器名称
    current_interpreter = spec.name

    # 从用户黑名单中获取当前解释器的关键词列表
    interpreter_keywords = userBlacklist.get(current_interpreter, [])
    
    # 检查当前解释器的关键词
    for keyword in interpreter_keywords:
        if keyword.lower() in command_lower:
            hitUserBlacklist.append(keyword)

    # ──────────────────────────────────────────────
    # 第五步：安全拦截 — 第 3 层（常规确认 needConfirm）
    # ──────────────────────────────────────────────

    # 判断是否需要弹窗确认
    # 第 2 层命中 或 第 3 层 needConfirm=True，都需要弹窗
    needPopup = needConfirm or len(hitUserBlacklist) > 0

    if needPopup:
        # 尝试从 context 中获取跨线程确认回调
        # context 由 Executor._executeShortcut 在调用时注入
        confirm_callback = (context or {}).get("confirm_callback")

        if confirm_callback:
            # ── 有回调：走跨线程阻塞弹窗流程 ──

            # 构建弹窗提示信息（合并第 2 层和第 3 层的提示）
            messages = []
            if hitUserBlacklist:
                messages.append(
                    f"⚠️ 命令命中自定义黑名单:\n"
                    f"  {', '.join(hitUserBlacklist)}"
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

            # ★ 跨线程通信核心 ★
            # Event 对象用于子线程阻塞等待主线程弹窗结果
            event = threading.Event()
            # result_holder 是可变容器（列表），主线程写入结果后子线程读取
            # 不能用普通变量因为闭包只能读不能写，用 list 包装可变
            result_holder = [False]

            # 调用 confirm_callback，它会通过 app.after(0, ...)
            # 将弹窗操作抛到 Tkinter 主线程执行
            confirm_callback(popup_message, result_holder, event)

            # ★ 子线程在此阻塞，直到主线程调用 event.set() ★
            event.wait()

            # 主线程已唤醒本线程，读取弹窗结果
            if not result_holder[0]:
                # 用户点了"否"，终止执行
                return

        else:
            # ── 无回调（context 为空或未注入 confirm_callback）──
            # 降级处理：跳过确认，直接执行
            # 这种情况一般出现在单元测试或直接调用 handler 时
            pass

    # ──────────────────────────────────────────────
    # 第六步：构建命令参数（数据驱动组装）
    # ──────────────────────────────────────────────

    # 处理多行命令：将换行符替换为当前解释器的多行连接符
    # cmd:       \n → " & "    (如 echo 第一行 & echo 第二行)
    # powershell: \n → " ; "   (如 echo 第一行 ; echo 第二行)
    # python:    \n → "\n"     (保持原样，-c 参数支持多行)
    processed_command = command.replace('\n', spec.multiline_sep)

    # Windows 平台标志位
    is_win = sys.platform == "win32"
    no_window_flag = subprocess.CREATE_NO_WINDOW if is_win else 0
    new_console_flag = subprocess.CREATE_NEW_CONSOLE if is_win else 0

    # 根据执行模式选择参数列表和窗口标志位
    #
    # execMode 三种模式：
    #   1. "后台静默执行"    → eval_params + CREATE_NO_WINDOW
    #   2. "弹出终端并保持"  → keep_params + CREATE_NEW_CONSOLE
    #   3. "弹出终端执行后关闭" → eval_params + CREATE_NEW_CONSOLE
    #
    # 如果解释器不支持保持模式（keep_params 为空列表），则退化为 eval_params

    if execMode == "弹出终端并保持":
        # 优先使用 keep_params，为空则退化为 eval_params
        cmd_args = spec.keep_params if spec.keep_params else spec.eval_params
        creation_flags = new_console_flag
    elif execMode == "弹出终端执行后关闭":
        cmd_args = spec.eval_params
        creation_flags = new_console_flag
    else:
        # 默认：后台静默执行
        cmd_args = spec.eval_params
        creation_flags = no_window_flag

    # ──────────────────────────────────────────────
    # 第七步：执行命令
    # ──────────────────────────────────────────────

    try:
        if not is_win and execMode != "后台静默执行":
            # ── Linux/macOS：使用 xterm 包装终端窗口 ──
            # xterm -hold：执行完保持窗口
            # xterm（不带 -hold）：执行完自动关闭
            hold_flag = ['-hold'] if execMode == "弹出终端并保持" else []
            subprocess.Popen(
                ['xterm'] + hold_flag + ['-e', executable] + cmd_args + [processed_command],
                cwd=workingDir
            )
        else:
            # ── Windows 或后台静默模式 ──
            # 直接传列表，subprocess 会自动处理路径中的空格
            # 列表形式：[executable, eval_param1, eval_param2, ..., command]
            # 示例 cmd:    ['cmd', '/c', 'echo hello']
            # 示例 PS:     ['powershell', '-NoProfile', '-Command', 'echo hello']
            # 示例 python: ['python', '-c', 'print("hello")']
            subprocess.Popen(
                [executable] + cmd_args + [processed_command],
                cwd=workingDir,
                creationflags=creation_flags
            )
    except Exception as e:
        raise RuntimeError(f"执行命令失败:\n{str(e)}")


# ==================== 注册 ====================

def initActionHandlers():
    """在模块加载时，将所有 handler 函数注册到动作注册表"""
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
