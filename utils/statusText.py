''' 监听/执行状态文案（单点真相源） '''

# ==============================================================================
# 【34 号设计定稿：状态文案单点化】
# ------------------------------------------------------------------------------
# 背景：Bug#34 的深层教训之一是"状态显示逻辑分散"——设置页 _refreshControlStatus
# 与托盘 _build_dynamic_menu 各写一套读取/措辞，任何一处口径调整都会造成两处
# 显示漂移。本模块把"从 executor 读状态 → 生成用户文案"收敛为纯函数：
#
#   - 输入：executor（或 None），不依赖任何 GUI / 配置文件；
#   - 输出：(文案, 颜色) 二元组。颜色供设置页 Label 使用；托盘 MenuItem 无
#     颜色概念，忽略颜色只用文案；
#   - 纯函数无副作用：托盘线程调用安全（只读 executor 属性，GIL 下原子）。
#
# 接入方（仅此两处，禁止第三方自写文案）：
#   - gui/SettingsPage._refreshControlStatus（500ms 轮询刷新 Label）
#   - gui/trayIcon._build_full_menu（菜单展开时构建状态行）
#
# 已知口径变化：动作组执行中文案从原设置页的"可用停止组合 / 本区按钮停止"
# 改为通用措辞"可用停止组合 / 托盘 / 设置页停止"——单点化后文案必须两边
# 通吃，以更全面的版本为准（设计定稿 v2 已声明）。
# ==============================================================================


def getListenStatus(executor):
    """
    监听状态文案。

    参数 executor: core.executor.Executor 实例，可为 None（执行器未注入）。
    返回: (文案, 颜色) 元组。颜色为 CustomTkinter 接受的色值。

    判定优先级（与原设置页逻辑逐分支等价）：
      1. isPaused（用户主动暂停）——最高优先级，压过一切；
      2. isListening 且有启用方案 → "监听中 · 方案: X"；
      3. isListening 但无启用方案 → 橙色警示（sync 本应停掉监听器，
         此态只应短暂存在，如实显示、不掩盖）；
      4. 其余 → 未启动。
    """
    if executor is None:
        return "未启动（无启用方案）", "gray"

    # getattr 兜底：极旧 executor 实例（未含 isPaused 字段）不炸，退化为未暂停
    paused = bool(getattr(executor, 'isPaused', False))
    if paused:
        return "已暂停（可用下方按钮恢复）", "#FFA500"

    listening = bool(getattr(executor, 'isListening', False))
    if listening:
        scheme = executor.getActiveSchemeInfo()
        name = (scheme or {}).get("name")
        if name:
            return f"监听中 · 方案: {name}", "#008000"
        return "监听中（无启用方案）", "#FFA500"

    return "未启动（无启用方案）", "gray"


def getExecStatus(executor):
    """
    执行状态文案。

    参数与返回值同 getListenStatus。

    判定优先级：is_busy（动作组，可能劫持鼠标）优先于 isExecuting
    （单动作长尾，如大 duration 的 mouseMoveTo）——与设置页原逻辑一致。
    """
    if executor is None:
        return "未知", "gray"

    busy = bool(getattr(executor, 'is_busy', False))
    if busy:
        return "动作组执行中（可用停止组合 / 托盘 / 设置页停止）", "#FF6B6B"

    executing = bool(getattr(executor, 'isExecuting', False))
    if executing:
        return "单动作执行中", "#FFA500"

    return "空闲", "gray"
