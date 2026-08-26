''' 通用数据校验相关工具 '''

# ==================== 校验规则常量定义 ====================
# 合法按键字典（全部小写）。命名唯一口径：见下分区块注释。
LEGAL_KEYS = {
    # ── 修饰键及左右变体（统称/特称两级，等价拼写靠校验前的小写化兜住）──
    "ctrl", "ctrl_l", "ctrl_r", "control", "control_l", "control_r",
    "shift", "shift_l", "shift_r", "alt", "alt_l", "alt_r",
    "option", "option_l", "option_r",
    "cmd", "cmd_l", "cmd_r", "windows", "command",

    # ── 字母 a-z ──
    *[chr(i) for i in range(97, 123)],

    # ── 主键盘数字 0-9 ──
    *[str(i) for i in range(10)],

    # ── 小键盘数字 ──
    *[f"numpad_{i}" for i in range(10)],

    # ── 小键盘运算键五名（与主键盘同名符号视为不同的键）──
    # 注意不收录 numpad_enter：它与主回车共用 VK_RETURN(13)，
    # 事件层无法区分，口径为"统一写 enter，两处回车均命中"
    "numpad_decimal", "numpad_add", "numpad_subtract",
    "numpad_multiply", "numpad_divide",

    # ── 功能键 ──
    *[f"f{i}" for i in range(1, 13)],

    # ── 特殊键（命名照抄 pynput.Key 属性，保证发送端可直接取属性）──
    "space", "tab", "enter", "esc",
    "up", "down", "left", "right",
    "page_up", "page_down", "caps_lock", "insert", "print_screen",

    "backspace", "delete", "home", "end",

    # ── OEM 标点行 11 键：一律写美式布局底位符，与 vkKeyMap 收录一致；
    #    上档效果（加号/@/#...）由用户补一个 shift 成员表达 ──
    ";", "=", ",", "-", ".", "/", "`", "[", "\\", "]", "'",
}
# 显式不收录（防止未来有人好心回加，先刻碑）：
#   · "plus" 与 "+" ：'+' 是分隔符本身无法成为键名，且未发布无兼容包袱，
#     加号效果请写 shift+=（决策5：不告诉用户存在过 plus 这种设计）
#   · 上档字符 "@#$%..." ：不是键名，让校验器报错并教学才是正道

# ==================== 通用校验函数 ====================
def validate_key_combination(key_str: str):
    """校验快捷键组合字符串是否合法（不强制结构，只要键名合法即可）。

    返回: (is_valid, message, cleaned_data)
        cleaned_data 为清理后标准串（去首尾空白、统一小写）

    定位：【唯一的拦截面兼教学面】
      - 组合内出现非法键名在这里报错并给出"怎么写才对"；
      - 因此 executor 与 actionHandlers 两侧对输入保持零宽容直通，
        三方（校验/监听/发送）都以本函数放行为共同信任前提。
    """
    if not key_str or not key_str.strip():
        return False, "快捷键不能为空。", key_str

    # 静默修正：去首尾空格、转小写
    cleaned_key = key_str.strip().lower()

    # 按 '+' 拆分。'+' 是唯一分隔符且不可转义，因此空片段必然是笔误
    # （连续加号 / 首尾多加号），一律拒绝而不是静默吞掉——静默吞掉会让
    # "ctrl++x" 变成 "ctrl+x" 触发，属于隐藏的语义篡改
    parts = [p.strip() for p in cleaned_key.split('+')]
    if any(not p for p in parts):
        return False, (
            "快捷键格式错误：检测到连续的 '+' 或首尾多余的 '+'。\n"
            "本软件没有名为加号的独立按键：加号 = 等号键的上档位，"
            "请写 shift+= ；若要的是等号本身，直接写 = 即可。"
        ), cleaned_key

    # 逐名比对，收集所有非法项一次性反馈（省得用户来回试错）
    invalid_keys = [p for p in parts if p not in LEGAL_KEYS]
    if invalid_keys:
        tips = []
        for name in invalid_keys:
            if name in ("plus", "+"):
                # 教学点①：加号不存在独立键名（决策5：文案不提 plus 历史）
                tips.append(
                    "[{}] 不存在独立的加号键名：加号=等号键+Shift，请写 shift+=".format(name)
                )
            elif len(name) == 1:
                # 教学点②：单字符多半是想写上档符号（@ # & ...）
                tips.append(
                    "[{}] 不是合法键名。标点键只认美式底位符号 11 个："
                    "; = , - . / ` [ \\ ] ' ，需要上档效果时补一个 shift 成员"
                    "（例如 @ 所在按键写作 shift+2）".format(name)
                )
            else:
                # 其余拼写错误：如实报告
                tips.append("[{}] 未知的按键名称".format(name))
        return False, "按键名校验失败：\n· " + "\n· ".join(tips), cleaned_key

    # 拼接回标准格式（此时各段均合法且不含空白，直接 join 即得规范形）
    final_key = "+".join(parts)
    return True, "校验通过", final_key

# ==================== 以后扩展的校验函数写在这里 ====================
# 例如：
# def validate_path(path_str: str):
#     ...
# def validate_command(command_str: str):
#     ...
