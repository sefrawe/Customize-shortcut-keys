''' 通用数据校验相关工具 '''

# ==================== 校验规则常量定义 ====================

# 合法按键字典 (包含所有允许的按键名称，小写)
LEGAL_KEYS = {
    # 修饰键及其变体
    "ctrl", "ctrl_l", "ctrl_r", "control", "control_l", "control_r",
    "shift", "shift_l", "shift_r",
    "alt", "alt_l", "alt_r", "option", "option_l", "option_r",
    "cmd", "cmd_l", "cmd_r", "windows", "command",
    
    # 字母
    *[chr(i) for i in range(97, 123)],
    
    # 数字
    *[str(i) for i in range(10)],
    
    # 小键盘
    *[f"numpad_{i}" for i in range(10)], 
    "numpad_enter", "numpad_decimal", "numpad_add", "numpad_subtract", "numpad_multiply", "numpad_divide",
    
    # 功能键
    *[f"f{i}" for i in range(1, 13)],
    
    # 特殊键
    "space", "tab", "enter", "esc", "up", "down", "left", "right",
    "plus", "+", "backspace", "delete", "home", "end", "page_up", "page_down", "caps_lock", "insert"
}

# ==================== 通用校验函数 ====================

def validate_key_combination(key_str: str):
    """
    校验快捷键组合字符串是否合法。
    (规则：不强制要求组合结构，允许纯修饰键或多个普通键，只要按键名合法即可)
    
    返回: tuple (is_valid: bool, message: str, cleaned_data: str)
      - is_valid: 是否合法
      - message: 校验结果信息（错误原因或成功提示）
      - cleaned_data: 清理后的标准格式字符串（如统一小写、去空格）
    """
    if not key_str or not key_str.strip():
        return False, "快捷键不能为空。", key_str
    
    # 静默修正：去首尾空格、转小写
    cleaned_key = key_str.strip().lower()
    
    # 按加号拆分，并去除拆分后的空格
    parts = [p.strip() for p in cleaned_key.split('+') if p.strip()]
    
    if not parts:
        return False, "快捷键格式错误：未检测到有效按键。", cleaned_key
    
    # 将 'plus' 还原为 '+' 以便后续匹配执行器的逻辑
    parts = ["+" if p == "plus" else p for p in parts]
    
    invalid_keys = []
    for p in parts:
        if p not in LEGAL_KEYS:
            invalid_keys.append(p)
    
    if invalid_keys:
        return False, f"包含未知的按键: {', '.join(invalid_keys)}", cleaned_key
    
    # 拼接回标准格式（确保加号前后无空格）
    final_key = "+".join(parts)
    return True, "校验通过", final_key


# ==================== 以后扩展的校验函数写在这里 ====================
# 例如：
# def validate_path(path_str: str):
#     ...
# def validate_command(command_str: str):
#     ...
