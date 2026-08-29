''' 保留停止组合（唯一真相源） '''
# -*- coding: utf-8 -*-
''' 
=====================================================================
【职能边界】
本模块只做一件事：定义"软件级停止组合"这一对系统保留按键，并提供
两种精度【故意不同】的判定工具。它是 31/33 号功能（动作组键盘急停 +
不拦截监听）的组合常量与匹配逻辑的唯一出处，禁止在任何其他文件抄副本
（Bug#30 的病根之一就是副本漂移）。

【两条保留组合（35 号修订 · 确认键 caps_lock，不可配置）】
  强制停止  ctrl_r + alt_r + caps_lock   右手双修饰键 + 左手确认 = 双手硬停
  平滑停止  ctrl_l + alt_l + caps_lock   左手单手可成 = 软停

【为什么确认键从 esc 换成 caps_lock（35 号决策记录，全文见设计定稿第六节）】
❌ esc（v3 原案，废弃）：
   ctrl+esc = 开始菜单、alt+esc = 窗口循环切换。系统对这两个子集的
   响应是【即时的、不管顺序与子集】——用户先按 ctrl 再按 esc 的瞬间
   （alt 尚未按下）系统行为已经发生，软件侧无法补救；若改走拦截路线
   又直接违反 33 号"不拦截监听"红线。顺子窗口是结构性的，
   换确认键是唯一正解。
❌ num_lock（候选，否决）：
   · 小键盘右上角属右手区 → 软停"左手单手可成"破产（决策1：保单手）；
   · 笔记本多为 Fn 复合，而 Fn 是硬件层按键 OS 根本看不到 →
     目标用户群的逃生口直接失效（决策2：不放弃笔记本）；
   · toggle 翻转小键盘模式会改变本软件自己的监听语义（小键盘数字↔
     导航键，vkKeyMap 表头注释自证），副作用过重（决策3：越小越好）。
✅ caps_lock（定案）：
   ① 软停单手保住——拇指 alt_l + 小指 ctrl_l + 无名指 caps_lock，
     紧贴 a 键，比原 esc 更近主区；
   ② 笔记本不放弃——独立存在，无 Fn 复合问题；
   ③ 副作用最小——同为 toggle，翻大小写（轻）而非小键盘模式（重），
     且 vk-first 归一化对此免疫（字母 vk 统一小写存表，监听语义零扰动）；
   ④ 漏键中间态干净——ctrl+caps / alt+caps 系统均无绑定，
     "顺序无关"承诺从此真正成立（v3 文案里那句与系统子集即时响应
     相互矛盾，是误导源，随本次换键一并废止重写）；
   ⑤ 监听/合法域/发送端三层现成全通（pynput name 透传 /
     LEGAL_KEYS 已收录 / pynput.Key.caps_lock 直取），零配套改动。

⚠ 已接受并需在用户文档声明的副作用（决策3"可接受，越小越好"的兑现）：
   · 每次命中停止组合，大小写状态翻转一次；
   · 系统 ToggleKeys 辅助功能开启时会响铃；
   · caps_lock 被用户改键（重映射为其他键）的环境下软硬停不可用，
     记为已知边界。

【两种判定、两个调用方、精度为什么不同】
1) matchReservedStopCombo —— 运行时路由用（core/executor.py，第二轮接）
   精确集合相等。物理按键永远产生特称名（ctrl_l/ctrl_r，keyNormalizer
   三级漏斗保证），所以运行时必须也只必须做特称精确比对：
   · 混按不触发：{ctrl_l, alt_r, caps_lock} 与两条均不相等 ✅
   · 模拟统称免疫：simulateKeys 发统称 ctrl 走 VK_CONTROL(0x11)，
     监听端收到的 name 是统称 "ctrl"，与特称集合永不相等 ✅
   结论：运行时绝不能用统称通配 —— 那会把模拟按键的统称组合误判成
   急停，制造宏自吞的回声 bug。
2) checkReservedConflict —— 校验层用（utils/keyValidator.py，本轮接）
   统称通配感知。用户配置里写统称 ctrl/alt 时，运行时
   executor._is_key_match 的统称/特称智能匹配会让"物理按左键"命中
   统称配置 —— 于是统称 ctrl+alt+caps_lock 会被停止路由永久截胡，
   成为绑了也永远不触发的哑键。校验层必须镜像这个匹配语义：
   配置的 token 在某种左右侧解析下能等于保留集合，即判冲突。
   注意：这不是扩大保留范围（"精确保留"原则不变），恰恰是把
   "运行时真的会截胡"的范围如实标出来 —— 校验与运行时完全一致。

【导入方向】
reservedCombos -> keyNormalizer -> vkKeyMap 纯数据 + 纯函数，
不依赖 executor/listener/GUI，谁都能安全 import。

【边界铁律】
· 本模块不做"要不要停"的决策（那是 executor 路由的事），只回答
  "按下的集合是不是保留组合 / 配置串会不会被截胡"；
· 不拦截任何系统行为、不碰监听器 —— 33 号需求的兑现方式就是
  "选无系统占用的组合"，而不是"写拦截代码"。
  
      安全论证（31 二轮方案 A 修订）：单步 simulateKeys 的组合必过
    validate_key_combination，保留组合（含统称通配）已被源头拦截 →
    单步模拟凑不成保留集。
    已接受边界（方案 A 记档，详见 executor.handleKeyPress 注释）：
    执行期释放事件被闸门忽略、集合只增不清，两条理论路径可凑成"假超集"
    （成员由模拟键/残留贡献）：a) 残留×模拟——物理按住某组合的两修饰键
    + 宏恰模拟 caps_lock；b) 跨步累积——不同步骤模拟的键跨步凑齐。
    两条都要求"模拟 caps_lock"参与，概率低、后果轻（动作组或单动作
    提前停止，无危险性）。实测命中再升级注入位检测（方案 B，需动
    core/listener.py，暂不实现）。

 '''


from utils.keyNormalizer import normalizeAlias

# =====================================================================
# 保留组合常量（唯一真相源，禁止抄副本）
# =====================================================================
# 35 号修订：确认键 esc → caps_lock（决策记录见模块头）。
# CONFIRM_KEY 单独立常量：checkReservedConflict 的结构门槛与循环跳过
# 两处共用，禁止再散写键名字符串（修订前门内就有两处 "esc" 硬编码，
# 教训在案——真相源内部也要守自己的纪律）。
CONFIRM_KEY: str = "caps_lock"

# 强制停止：右手双修饰键 + 确认键。命中后 executor 置位全局硬中断事件，
# 动作组在下一个 ≤50ms 的检查点（延迟分片 / 步间检查）被强制终止。
RESERVED_HARD_SET: frozenset = frozenset({"ctrl_r", "alt_r", CONFIRM_KEY})

# 平滑停止：左手单手可成。命中后置位软停事件，当前步骤执行完毕后在
# 步间退出，语义 = "做完手上这一步再停"，与托盘「平滑停止」同口径。
RESERVED_SOFT_SET: frozenset = frozenset({"ctrl_l", "alt_l", CONFIRM_KEY})

# 触发归因标签（executor 路由 & 日志文案共用，防止两边各写一份字符串漂移）
STOP_KIND_HARD = "hard"
STOP_KIND_SOFT = "soft"

def _kindToLabel(kind: str) -> str:
    """触发种类 -> 中文标签。集中一处，防止 executor/日志文案漂移。"""
    return "强制停止" if kind == STOP_KIND_HARD else "平滑停止"

def kindToComboStr(kind: str) -> str:
    """触发种类 -> 规范写法串（教学文案里给用户看的标准形）。

    35 号修订：原为模块私有 _kindToComboStr，因设置页停止按钮文案
    需要消费真相源而公共化（import 私有名会被审读误读为越权，公共口
    才是"禁止抄副本"纪律的长期落点）。UI 文案一律消费本函数，
    禁止在任何文件硬编码组合串。键名取自 CONFIRM_KEY，不自持字符串，
    未来再换确认键时本函数零改动。
    """
    return (
        f"ctrl_r+alt_r+{CONFIRM_KEY}" if kind == STOP_KIND_HARD
        else f"ctrl_l+alt_l+{CONFIRM_KEY}"
    )

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
        成员均为 keyNormalizer 产出的规范名，如 {'ctrl_l','alt_l','caps_lock'}）。

    【调用契约】调用方保证已归一化 —— executor 会在 handleKeyPress
    顶端做一次归一化，路由与后续用户快捷键匹配共用同一次结果。

    返回:
        STOP_KIND_HARD / STOP_KIND_SOFT —— 命中对应停止组合；
        None —— 未命中（混按/缺键/多键/统称等一切其他情况）。

    匹配语义（设计定稿 1.2，改这里前先读模块头注释）：
    · 精确集合相等（==），不做子集/前缀判断 —— caps_lock 是确认键，
      少任何一个修饰键都不算；多一个杂键也不算（混按防手滑的核心）；
    · 只认特称：物理按键经三级漏斗必然产出 ctrl_l/ctrl_r 等特称名
      （修饰键有 name 属性，normalizeAlias 原样保留左右不合并）；
    · 模拟按键免疫：simulateKeys 发统称 ctrl 产生 VK_CONTROL(0x11)，
      监听端收到的 name 就是统称 "ctrl"，与本集合永不相等 —— 宏不可能
      误触发急停，路由端零防回声负担；
    · 顺序无关：调用方传的是集合，三键任意按下顺序、确认键松开前凑齐
      即命中，无需维护按键序列状态。（35 号换键后该承诺首次真正成立：
      漏键子集 ctrl+caps / alt+caps 系统均无绑定，不存在"先按的瞬间
      系统抢跑"。）
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
    ① 逐 token 过 normalizeAlias 等价拼写收敛 —— LEGAL_KEYS 收录了
       control/option/control_r 等别名拼写，而运行时归一化会把它们
       折算成正名再触发；不做这一步，"control_r+option_r+caps_lock"
       就能绕过检查、保存后照样截胡。
    ② 去重 —— 手滑写 ctrl_r+ctrl_r 时，运行时按下集合本就是集合，
       重复 token 照样被截胡，检查必须与运行时同口径。
    ③ 结构门槛：去重后必须恰好 3 个 token —— 1 个确认键 caps_lock
       + 1 个 ctrl 族 + 1 个 alt 族。多/少/含其他键（如 shift、cmd）
       都与保留集合结构不同，运行时永不截胡，直接放行。
    ④ 侧集求交：ctrl/alt 各取可解析侧集，两侧存在公共侧即冲突 ——
       公共侧 = L 命中平滑停止，= R 命中强制停止。
       例：ctrl_l+alt_r+caps_lock 两侧交集为空 → 不冲突（混按本来
       就不触发停止、运行时也不会截胡，校验与运行时两边完全一致）。

    参数:
        tokens —— 已按 '+' 拆分、已小写的 token 列表（由 keyValidator
        拆好传入，本函数不重复拆分；token 顺序无关紧要）。

    返回:
        (is_conflict, message, matched)
        is_conflict —— True 表示该配置会被保留组合永久截胡（永不触发）；
        message —— 冲突时的教学文案（含命中的具体组合），无冲突为 None；
        matched —— 命中的保留组合种类列表（元素为 STOP_KIND_*）。
    """
    # ① 等价拼写收敛 + ② 去重（用集合一步完成，顺序信息本就不需要）
    normalized = {normalizeAlias(t) for t in tokens}

    # ③ 结构门槛：恰好 3 个键，且其中必须有确认键
    # 35 号修订："esc" 字面量 → CONFIRM_KEY 常量（门内第二处硬编码清偿；
    # 门槛数量 3 与键名无关，换键只动键名不动数字）。
    # （不满足 = 结构上不可能等于任何保留集合 → 运行时不会截胡 → 放行）
    if len(normalized) != 3 or CONFIRM_KEY not in normalized:
        return False, None, []

    # 遍历其余两个 token，分别认领 ctrl 族 / alt 族的侧集。
    # 用"认领后置 None 判重"的写法，天然拦下"双 ctrl 族/双 alt 族"
    # 这类结构不符的组合（如 ctrl+ctrl_l+caps_lock：运行时按不出两个
    # ctrl 族键同时匹配它的场景，实际不会截胡 → 放行）。
    ctrl_sides = None
    alt_sides = None
    for t in normalized:
        # 35 号修订：确认键跳过判断改消费常量（门内第二处硬编码），
        # 与上面的门槛共用同一真相，不再各写一份键名字符串。
        if t == CONFIRM_KEY:
            continue
        sides = _MODIFIER_SIDES.get(t)
        if sides is None:
            # 第三个键不是 ctrl/alt 族成员（如 shift/cmd）→ 结构不符 → 放行
            return False, None, []
        if t.startswith("ctrl"):
            if ctrl_sides is not None:
                # 出现第二个 ctrl 族成员
                return False, None, []
            ctrl_sides = sides
        else:
            if alt_sides is not None:
                # 出现第二个 alt 族成员
                return False, None, []
            alt_sides = sides

    if ctrl_sides is None or alt_sides is None:
        # 只有确认键 + 单族成员 → 结构不符 → 放行
        return False, None, []

    # ④ 侧集求交，逐条保留组合判定
    matched = []
    if ctrl_sides & alt_sides & {"L"}:
        matched.append(STOP_KIND_SOFT)   # 公共侧含 L → 可解析成软停
    if ctrl_sides & alt_sides & {"R"}:
        matched.append(STOP_KIND_HARD)   # 公共侧含 R → 可解析成硬停
    if not matched:
        # 左右侧集不相交（如 ctrl_l+alt_r+caps_lock 混按）→ 不会截胡 → 放行
        return False, None, []

    # 组装教学文案：说清命中的是哪条（或两条统称全占）、为什么永不触发。
    combo_lines = "、".join(
        f"「{_kindToLabel(k)}」{kindToComboStr(k)}"   # 35 号：消费公共化后的函数
        for k in matched
    )
    message = (
        "该快捷键与软件保留的停止组合冲突：你配置的组合在按下对应按键时\\n"
        f"会命中软件级停止组合 {combo_lines}。\\n"
        "停止组合的优先级高于所有用户快捷键（这是急停可靠性的前提），\\n"
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
    （35 号备注：逻辑吃 frozenset，常量换确认键后自动跟随，零改动。）
    """
    if RESERVED_HARD_SET <= pressed_names:
        return STOP_KIND_HARD
    if RESERVED_SOFT_SET <= pressed_names:
        return STOP_KIND_SOFT
    return None
