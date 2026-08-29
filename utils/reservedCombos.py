'''
保留停止组合（唯一真相源）
'''
# -*- coding: utf-8 -*-
'''

=====================================================================

【职能边界】
本模块只做一件事：定义"软件级停止组合"这一对系统保留按键，并提供
两种精度【故意不同】的判定工具。它是 31/33 号功能（动作组键盘急停 +
不拦截监听）的组合常量与匹配逻辑的唯一出处，禁止在任何其他文件抄副本
（Bug#30 的病根之一就是副本漂移）。

【两条保留组合（设计定稿 v3 · 三键版，不可配置）】
    强制停止  ctrl_r + alt_r + esc   右手双修饰键 + 左手 esc = 双手硬停
    平滑停止  ctrl_l + alt_l + esc   左手单手可成 = 软停

【为什么是这两条（决策记录摘要，全文见设计定稿第六节）】
    ❌ ctrl+esc        系统占用（开始菜单）—— 漏按 alt 时中间态会撞它
    ❌ alt+esc         系统占用（窗口循环切换）—— 漏按 ctrl 时会撞它
    ❌ shift+esc       浏览器任务管理器 + 单修饰键易误触
    ✅ 三键版           esc 确认键 + 左右分区 + 系统零占用 + 精确集合匹配
    （ctrl+alt+esc 本身无任何系统绑定 → 33 号"不拦截监听"保持成立，
      监听器纯被动，零拦截代码。）

【两种判定、两个调用方、精度为什么不同】
    1) matchReservedStopCombo —— 运行时路由用（core/executor.py，第二轮接）
       精确集合相等。物理按键永远产生特称名（ctrl_l/ctrl_r，keyNormalizer
       三级漏斗保证），所以运行时必须也只必须做特称精确比对：
       · 混按不触发：{ctrl_l, alt_r, esc} 与两条均不相等 ✅
       · 模拟统称免疫：simulateKeys 发统称 ctrl 走 VK_CONTROL(0x11)，
         监听端收到的 name 是统称 "ctrl"，与特称集合永不相等 ✅
       结论：运行时绝不能用统称通配 —— 那会把模拟按键的统称组合误判成
       急停，制造宏自吞的回声 bug。

    2) checkReservedConflict —— 校验层用（utils/keyValidator.py，本轮接）
       统称通配感知。用户配置里写统称 ctrl/alt 时，运行时
       executor._is_key_match 的统称/特称智能匹配会让"物理按左键"命中
       统称配置 —— 于是统称 ctrl+alt+esc 会被停止路由永久截胡，成为
       绑了也永远不触发的哑键。校验层必须镜像这个匹配语义：配置的
       token 在某种左右侧解析下能等于保留集合，即判冲突。
       注意：这不是扩大保留范围（"精确保留"原则不变），恰恰是把
       "运行时真的会截胡"的范围如实标出来 —— 校验与运行时完全一致。

【导入方向】
    reservedCombos -> keyNormalizer -> vkKeyMap
    纯数据 + 纯函数，不依赖 executor/listener/GUI，谁都能安全 import。

【边界铁律】
    · 本模块不做"要不要停"的决策（那是 executor 路由的事），只回答
      "按下的集合是不是保留组合 / 配置串会不会被截胡"；
    · 不拦截任何系统行为、不碰监听器 —— 33 号需求的兑现方式就是
      "选无系统占用的组合"，而不是"写拦截代码"。
'''

from utils.keyNormalizer import normalizeAlias

# =====================================================================
# 保留组合常量（唯一真相源，禁止抄副本）
# =====================================================================

# 强制停止：右手双修饰键 + esc。命中后 executor 置位全局硬中断事件，
# 动作组在下一个 ≤50ms 的检查点（延迟分片 / 步间检查）被强制终止。
RESERVED_HARD_SET: frozenset = frozenset({"ctrl_r", "alt_r", "esc"})

# 平滑停止：左手单手可成。命中后置位软停事件，当前步骤执行完毕后在
# 步间退出，语义 = "做完手上这一步再停"，与托盘「平滑停止」同口径。
RESERVED_SOFT_SET: frozenset = frozenset({"ctrl_l", "alt_l", "esc"})

# 触发归因标签（executor 路由 & 日志文案共用，防止两边各写一份字符串漂移）
STOP_KIND_HARD = "hard"
STOP_KIND_SOFT = "soft"


def _kindToLabel(kind: str) -> str:
    """触发种类 -> 中文标签。集中一处，防止 executor/日志文案漂移。"""
    return "强制停止" if kind == STOP_KIND_HARD else "平滑停止"


def _kindToComboStr(kind: str) -> str:
    """触发种类 -> 规范写法串（教学文案里给用户看的标准形）。"""
    return ("ctrl_r+alt_r+esc" if kind == STOP_KIND_HARD
            else "ctrl_l+alt_l+esc")

def describeReservedKinds(kinds: list) -> str:
    """触发种类列表 -> 中文描述串（冲突报告等 UI 文案用，单一出口防漂移）。

    例：[STOP_KIND_HARD] -> "强制停止"；
        [STOP_KIND_SOFT, STOP_KIND_HARD] -> "平滑停止、强制停止"。
    """
    return "、".join(_kindToLabel(k) for k in kinds)



# =====================================================================
# 工具一：运行时精确匹配（core/executor.py 路由专用，第二轮接线）
# =====================================================================

def matchReservedStopCombo(pressed_names: set) -> str | None:
    """判断"当前物理按下的键名集合"是否【恰好等于】某条保留停止组合。

    参数:
        pressed_names —— 归一化后的按下键名集合（executor 监听端维护，
        成员均为 keyNormalizer 产出的规范名，如 {'ctrl_l','alt_l','esc'}）。
        【调用契约】调用方保证已归一化 —— executor 会在 handleKeyPress
        顶端做一次归一化，路由与后续用户快捷键匹配共用同一次结果。

    返回:
        STOP_KIND_HARD / STOP_KIND_SOFT —— 命中对应停止组合；
        None —— 未命中（混按/缺键/多键/统称等一切其他情况）。

    匹配语义（设计定稿 1.2，改这里前先读模块头注释）：
    · 精确集合相等（==），不做子集/前缀判断 —— esc 是确认键，少任何
      一个修饰键都不算；多一个杂键也不算（混按防手滑的核心）；
    · 只认特称：物理按键经三级漏斗必然产出 ctrl_l/ctrl_r 等特称名
      （修饰键有 name 属性，normalizeAlias 原样保留左右不合并）；
    · 模拟按键免疫：simulateKeys 发统称 ctrl 产生 VK_CONTROL(0x11)，
      监听端收到的 name 就是统称 "ctrl"，与本集合永不相等 —— 宏不可能
      误触发急停，路由端零防回声负担；
    · 顺序无关：调用方传的是集合，三键任意按下顺序、esc 松开前凑齐
      即命中，无需维护按键序列状态。
    """
    if pressed_names == RESERVED_HARD_SET:
        return STOP_KIND_HARD
    if pressed_names == RESERVED_SOFT_SET:
        return STOP_KIND_SOFT
    return None


# =====================================================================
# 工具二：配置串冲突检查（utils/keyValidator.py 校验层专用，本轮接线）
# =====================================================================

# 修饰键写法 -> 该写法在"统称/特称"匹配语义下可解析到的物理侧集合。
# 语义镜像 executor._is_key_match：统称可命中任意一侧，特称只命中自身。
# 左右侧用 'L'/'R' 标记，与 ctrl_l/ctrl_r 的后缀一一对应。
_SIDE_ANY = frozenset({"L", "R"})

_MODIFIER_SIDES = {
    # ctrl 族（control/control_l 等别名先经 normalizeAlias 收敛成正名再查）
    "ctrl":   _SIDE_ANY,          # 统称：物理按左或按右都命中
    "ctrl_l": frozenset({"L"}),
    "ctrl_r": frozenset({"R"}),
    # alt 族
    "alt":    _SIDE_ANY,
    "alt_l":  frozenset({"L"}),
    "alt_r":  frozenset({"R"}),
}


def checkReservedConflict(tokens: list) -> tuple:
    """判断用户配置的按键 token 列表是否与保留停止组合冲突（统称通配感知）。

    判定流程（顺序即实现顺序）：
      ① 逐 token 过 normalizeAlias 等价拼写收敛
         —— LEGAL_KEYS 收录了 control/option/control_r 等别名拼写，而
         运行时归一化会把它们折算成正名再触发；不做这一步，
         "control_r+option_r+esc" 就能绕过检查、保存后照样截胡。
      ② 去重 —— 手滑写 ctrl_r+ctrl_r 时，运行时按下集合本就是集合，
         重复 token 照样被截胡，检查必须与运行时同口径。
      ③ 结构门槛：去重后必须恰好 3 个 token —— 1 个 esc + 1 个 ctrl 族
         + 1 个 alt 族。多/少/含其他键（如 shift、cmd）都与保留集合
         结构不同，运行时永不截胡，直接放行。
      ④ 侧集求交：ctrl/alt 各取可解析侧集，两侧存在公共侧即冲突
         —— 公共侧 = L 命中平滑停止，= R 命中强制停止。
         例：ctrl_l+alt_r+esc 两侧交集为空 → 不冲突（混按本来就不触发
         停止、运行时也不会截胡，校验与运行时两边完全一致）。

    参数:
        tokens —— 已按 '+' 拆分、已小写的 token 列表（由 keyValidator
        拆好传入，本函数不重复拆分；token 顺序无关紧要）。

    返回:
        (is_conflict, message, matched)
        is_conflict —— True 表示该配置会被保留组合永久截胡（永不触发）；
        message     —— 冲突时的教学文案（含命中的具体组合），无冲突为 None；
        matched     —— 命中的保留组合种类列表（元素为 STOP_KIND_*）。
    """
    # ① 等价拼写收敛 + ② 去重（用集合一步完成，顺序信息本就不需要）
    normalized = {normalizeAlias(t) for t in tokens}

    # ③ 结构门槛：恰好 3 个键，且其中必须有 esc
    # （不满足 = 结构上不可能等于任何保留集合 → 运行时不会截胡 → 放行）
    if len(normalized) != 3 or "esc" not in normalized:
        return False, None, []

    # 遍历其余两个 token，分别认领 ctrl 族 / alt 族的侧集。
    # 用"认领后置 None 判重"的写法，天然拦下"双 ctrl 族/双 alt 族"
    # 这类结构不符的组合（如 ctrl+ctrl_l+esc：运行时按不出两个 ctrl
    # 族键同时匹配它的场景，实际不会截胡 → 放行）。
    ctrl_sides = None
    alt_sides = None
    for t in normalized:
        if t == "esc":
            continue
        sides = _MODIFIER_SIDES.get(t)
        if sides is None:
            # 第三个键不是 ctrl/alt 族成员（如 shift/cmd）→ 结构不符 → 放行
            return False, None, []
        if t.startswith("ctrl"):
            if ctrl_sides is not None:      # 出现第二个 ctrl 族成员
                return False, None, []
            ctrl_sides = sides
        else:
            if alt_sides is not None:       # 出现第二个 alt 族成员
                return False, None, []
            alt_sides = sides

    if ctrl_sides is None or alt_sides is None:
        # 只有 esc + 单族成员 → 结构不符 → 放行
        return False, None, []

    # ④ 侧集求交，逐条保留组合判定
    matched = []
    if ctrl_sides & alt_sides & {"L"}:
        matched.append(STOP_KIND_SOFT)      # 公共侧含 L → 可解析成软停
    if ctrl_sides & alt_sides & {"R"}:
        matched.append(STOP_KIND_HARD)      # 公共侧含 R → 可解析成硬停

    if not matched:
        # 左右侧集不相交（如 ctrl_l+alt_r+esc 混按）→ 不会截胡 → 放行
        return False, None, []

    # 组装教学文案：说清命中的是哪条（或两条统称全占）、为什么永不触发。
    combo_lines = "、".join(
        f"「{_kindToLabel(k)}」{_kindToComboStr(k)}" for k in matched
    )
    message = (
        "该快捷键与软件保留的停止组合冲突：你配置的组合在按下对应按键时\n"
        f"会命中软件级停止组合 {combo_lines}。\n"
        "停止组合的优先级高于所有用户快捷键（这是急停可靠性的前提），\n"
        "因此本快捷键即使保存成功也永远不会触发。请更换按键组合。"
    )
    return True, message, matched

def matchReservedStopComboLoose(pressed_names: set) -> str | None:
    """执行期专用：按下集合【包含】保留组合即命中（超集匹配）。
    只应在 isExecuting=True 时使用——此时集合不可信（触发键残留 +
    模拟 release 清集合 + 模拟按键瞬时污染），精确相等会漏判。
    安全论证：simulateKeys 的组合必过 validate_key_combination，
    保留组合（含统称通配）已被拦截 → 模拟键永远凑不成保留集，
    超集匹配不会因宏自身误触发急停。
    """
    if RESERVED_HARD_SET <= pressed_names:
        return STOP_KIND_HARD
    if RESERVED_SOFT_SET <= pressed_names:
        return STOP_KIND_SOFT
    return None

