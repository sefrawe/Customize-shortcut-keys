''' 解释器特征注册表：数据驱动模式管理不同 Shell 的执行参数 '''

from dataclasses import dataclass

@dataclass
class InterpreterSpec:
    """描述一个解释器的执行规格"""
    name: str                    # 解释器标识
    match_keywords: list[str]    # 用于模糊匹配用户输入的 executable
    
    # 执行后关闭的参数列表 (如 ['cmd', '/c'] 或 ['python', '-c'])
    # 注意：executable 会在 actionHandlers 中动态插入到列表最前面
    eval_params: list[str]       
    
    # 保持窗口并进入交互模式的参数列表 (如 ['cmd', '/k'] 或 ['python', '-i'])
    keep_params: list[str]      
    
    multiline_sep: str           # 多行命令连接符
    danger_keywords: list[str]   # 强黑名单关键词

# ──────────────── 解释器注册表 ────────────────
INTERPRETER_REGISTRY: list[InterpreterSpec] = [
    InterpreterSpec(
        name="cmd",
        match_keywords=["cmd"],
        eval_params=['/c'],
        keep_params=['/k'],                 # /k 执行完保留在 cmd 窗口
        multiline_sep=" & ",
        danger_keywords=[
            "format",      
            "diskpart",    
        ],
    ),
    InterpreterSpec(
        name="powershell",
        match_keywords=["powershell", "pwsh"],
        # 注意：这里不需要加 -NoProfile，因为保持窗口需要 -NoExit -Command
        eval_params=['-NoProfile', '-Command'],
        keep_params=['-NoExit', '-Command'], # -NoExit 执行完保留在 PS 窗口
        multiline_sep=" ; ",
        danger_keywords=[
            "Format-Volume",   
            "Remove-Item",     
        ],
    ),
    InterpreterSpec(
        name="python",
        match_keywords=["python", "python3"],
        eval_params=['-c'],
        keep_params=['-i'],                  # -i 执行完进入 >>> 交互环境
        multiline_sep="\n",
        danger_keywords=[
            "os.system",       
            "shutil.rmtree",   
        ],
    ),
]

# 默认规格：不支持原生保持窗口的解释器，退化为执行后关闭
_DEFAULT_SPEC = InterpreterSpec(
    name="unknown",
    match_keywords=[],
    eval_params=['-c'],
    keep_params=[],                          # 空列表表示不支持保持，退化为 eval_params
    multiline_sep="\n",
    danger_keywords=[],
)

def getInterpreterSpec(executable: str) -> InterpreterSpec:
    """根据用户输入的 executable 返回匹配的规格"""
    if not executable:
        return _DEFAULT_SPEC

    exe_lower = executable.lower().strip()

    for spec in INTERPRETER_REGISTRY:
        for keyword in spec.match_keywords:
            if keyword in exe_lower:
                return spec

    return _DEFAULT_SPEC
