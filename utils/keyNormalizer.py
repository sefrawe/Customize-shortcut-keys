'''
键名归一化
'''
'''
（唯一真相源）

【职能边界】
本模块只做一件事：把 pynput 交来的按键对象归一化为全软件统一的规范键名。
它是【键名的唯一真相源】，服务的调用方：
  · 监听端（executor）：物理按键事件 → 规范键名，用于匹配配置（原有路径）；
  · 录入端（gui/ShortcutEditWindow 的「⌨ 录入按键」）：用户按下的键 → 规范键名，
    写进备注教学（Bug#30 vk-first 重构的配套产出，见设计定稿第五节）。

【为什么必须是独立纯函数】
历史上归一化逻辑长在 Executor 身上（实例方法），录入端想复用就得
new 一个执行器或抄一份。actionHandlers 已因循环导入被迫养了
_SIMULATE_ALIAS_MAP 副本（注释原文："修改时需两边同步"）——
副本漂移正是 Bug#30 的病根之一。故下沉为 utils 层纯函数：
只依赖 vkKeyMap 纯数据表，导入方向干净无环，谁都能安全 import。

【三级漏斗 · 判定顺序不可调换】（原 executor 注释原文平移）
① 特殊键：有 name 属性 → 走别名归一化（ctrl_l / f5 / space 等）
② 常规键★：vk 命中 vkKeyMap.VK_TO_NAME → 直接采用规范名
   vk 是物理键位编号，天生免疫修饰键/大小写锁定/输入法三种状态污染
   ——这是 Bug#30 重构的全部意义所在。
③ char 兜底：仅当 vk 未收录且无 name 的极罕见场景。
   ⚠ 此路径的产物可能被修饰键污染（如 Ctrl+C 给出 '\x03'），
   属于"知道不可靠但留着以防万一"的容错位。
   边界铁律：永远不许靠它实现新功能（记事本·边界备忘3）。
'''

from utils.vkKeyMap import VK_TO_NAME


def normalizeSingleKey(key) -> str | None:
    """将 pynput 按键事件对象归一化为规范键名字符串（Bug#30 重构核心）。

    判定顺序【不可调换】，三级漏斗从可靠到不可靠：
    ① 特殊键  有 name 属性 → 走别名归一化
      （ctrl_l / f5 / space 等由 normalizeAlias 统一收口，此路原有逻辑不动）
    ② 常规键★ vk 命中 vkKeyMap.VK_TO_NAME → 直接采用规范名
      vk 是物理键位编号，天生免疫修饰键/大写锁定/输入法三种状态污染
      ——这是 Bug#30 重构的全部意义所在。
    ③ char兜底 仅当 vk 未收录且无 name 的极罕见场景。
      ⚠ 此路径的产物可能被修饰键污染（如 Ctrl+C 给出 '\x03'），
      属于"知道不可靠但留着以防万一"的容错位。
      边界铁律：永远不许靠它实现新功能（见记事本·边界备忘3）。

    调用方约定（职责单一，本模块不做合法域裁剪）：
      · 监听端（executor._normalizePressedKeys）：返回 None 即忽略该键；
      · 录入端（「⌨ 录入按键」捕获回调）：None 同样静默忽略；
        返回的名字是否属于可绑定域（LEGAL_KEYS），由录入端自行判定并标注
        ——本模块只负责"如实归一"，判"叫什么"，不判"能不能绑"。

    参数:
        key —— pynput 监听回调交来的按键对象（Key 枚举 / KeyCode / None）
    返回:
        规范键名 str；无法识别返回 None
    """
    if key is None:
        return None

    # ── ① 特殊键：pynput 的 Key 枚举成员才有 name 属性 ─────────────
    name = getattr(key, "name", None)
    if name:
        return normalizeAlias(str(name).lower())

    # ── ② vk 总表查询：录入功能依赖的主路径 ★ ─────────────────────
    vk = getattr(key, "vk", None)
    if vk is not None and vk in VK_TO_NAME:
        return VK_TO_NAME[vk]

    # ── ③ char 最后容错（不可靠路径，勿依赖）─────────────────────
    ch = getattr(key, "char", None)
    if ch:
        return str(ch).lower()

    return None


def normalizeAlias(keyName: str) -> str:
    """统一等价别名，但【不合并左右修饰键】。

    只做等价拼写转换（control → ctrl 等），ctrl_l/ctrl_r 特称原样保留
    ——统称/特称的智能匹配是 executor._is_key_match 的职责，不在本层越权。

    现状备注：utils/actionHandlers.py 因循环导入的历史原因另养了一份
    _SIMULATE_ALIAS_MAP 副本（口径与本表一致）。本轮不动它（另案重构）；
    未来收编时改用本函数即可，副本注释里"修改时需两边同步"的负担随之解除。
    """
    aliasMap = {
        "control": "ctrl",
        "control_l": "ctrl_l",
        "control_r": "ctrl_r",
        "option": "alt",
        "option_l": "alt_l",
        "option_r": "alt_r",
        "command": "cmd",
        "windows": "cmd",
    }
    return aliasMap.get(keyName, keyName)
