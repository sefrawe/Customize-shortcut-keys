'''
快捷键相关工具
'''
import json
from pathlib import Path

# from core.configManager import configDirectory 导入此文件会导致循环导入错误，因为 configManager.py 也导入了 shortcutUtils.py。
# 所以这里重新定义
# Path(__file__)         → core/config_manager.py
# .resolve()             → 转为绝对路径
# .parent                → core/
# .parent.parent         → 项目根目录
proJectrootDirectory = Path(__file__).resolve().parent.parent
configDirectory = proJectrootDirectory / "config"
globalSettingspath = configDirectory / "Global Settings.json"

# ==================== 31/33 号新增：保留组合检查导入 ====================
# 导入方向 shortcutUtils -> reservedCombos -> keyNormalizer -> vkKeyMap，
# 纯数据纯函数链，不经过 configManager，无循环导入风险（本文件顶部警示的
# 循环导入只存在于 configManager <-> shortcutUtils 之间）。
from utils.reservedCombos import checkReservedConflict, describeReservedKinds


def theNumberOfTargetFilesInTheFolder(folderPath):
    """统计文件夹中快捷键方案文件的数量（排除软件配置文件和无法解析的文件）"""
    folder = Path(folderPath)
    if not folder.exists() or not folder.is_dir():
        return 0
    count = 0
    for f in folder.iterdir():
        if not f.is_file():
            continue
        if f.suffix != ".json":
            continue
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            # 快捷键方案的标志性特征：顶层有 "shortcuts" 键
            if isinstance(data, dict) and "shortcuts" in data:
                count += 1
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return count


def getShortcutSchemes(folderPath):
    """获取文件夹中所有快捷键方案的文件"""
    folder = Path(folderPath)
    if not folder.exists() or not folder.is_dir():
        return []
    schemes = []
    for f in folder.iterdir():
        if not f.is_file() or f.suffix != ".json":
            continue
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, dict) and "shortcuts" in data:  # <-- 这里改掉
                schemeName = data.get("settings", {}).get("name", f.stem)
                description = data.get("settings", {}).get("description", "")
                schemeId = data.get("settings", {}).get("currentProfileId", 0)
                startupEnabled = data.get("settings", {}).get("startupEnabled", False)
                schemes.append({
                    "name": schemeName,
                    "description": description,
                    "schemeId": schemeId,
                    "startupEnabled": startupEnabled
                })
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

    # 根据id排序
    schemes.sort(key=lambda x: x["schemeId"])
    return schemes


def getShortcutSchemesNames(folderPath):
    """获取文件夹中所有快捷键方案的名称"""
    schemes = getShortcutSchemes(folderPath)
    return [scheme["name"] for scheme in schemes]


def getShortcutSchemesIds(folderPath):
    """获取文件夹中所有快捷键方案的ID"""
    schemes = getShortcutSchemes(folderPath)
    return [scheme["schemeId"] for scheme in schemes]


def getShortcutSchemesStartupEnabled(folderPath):
    """获取文件夹中所有快捷键方案的启动启用状态"""
    schemes = getShortcutSchemes(folderPath)
    return [scheme["startupEnabled"] for scheme in schemes]


def checkForDuplicateShortcutSchemeNames(folderPath):
    '''检查是否有重复名称的快捷键方案'''
    schemes = getShortcutSchemes(folderPath)
    names = [scheme["name"] for scheme in schemes]
    return len(names) != len(set(names))  # 如果长度不一样，说明有重复名称。
    # set() 是一个无序不重复元素集，set(names) 会去掉列表 names 中的重复元素。
    # 如果 names 中有重复名称，那么 set(names) 的长度就会小于 names 的长度，从而返回 True，表示存在重复名称；否则返回 False，表示没有重复名称。


def checkForDuplicateShortcutSchemeIds(folderPath):
    """检查是否有重复ID的快捷键方案"""
    schemes = getShortcutSchemes(folderPath)
    ids = [scheme["schemeId"] for scheme in schemes]
    return len(ids) != len(set(ids))  # 如果长度不一样，说明有重复ID


def checkForMultipleStartupEnabledShortcutSchemes(folderPath):
    """检查是否有多个快捷键方案被设置为启动启用状态"""
    schemes = getShortcutSchemes(folderPath)
    startupEnabledCount = sum(1 for scheme in schemes if scheme["startupEnabled"])
    return startupEnabledCount > 1  # 如果数量大于1，说明有多个被设置为启动启用状态


def getStartupEnabledShortcutScheme(folderPath):
    """获取被设置为启动启用状态的快捷键方案"""
    schemes = getShortcutSchemes(folderPath)
    for scheme in schemes:
        if scheme["startupEnabled"]:
            return scheme
    return None  # 如果没有被设置为启动启用状态的方案，返回 None


def getShortcutSchemeConfigBySchemeName(schemeName):
    # 根据快捷键方案名获取对应的配置文件内容

    for file in configDirectory.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            config = json.load(f)
        if config.get("settings", {}).get("name") == schemeName:
            return config
    return None


def getShortcutSchemeConfigById(id):
    # 根据快捷键方案ID获取对应的配置文件内容
    for file in configDirectory.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            config = json.load(f)
        if config.get("settings", {}).get("currentProfileId") == id:
            return config
    return None


def getConfigInfo(config):
    # 获取配置文件中的信息
    settings = config.get("settings", {})
    name = settings.get("name", "")
    description = settings.get("description", "")
    schemeId = settings.get("currentProfileId", 0)
    startupEnabled = settings.get("startupEnabled", False)
    return {
        "name": name,
        "description": description,
        "schemeId": schemeId,
        "startupEnabled": startupEnabled
    }


def getShortcutBySchemeName(schemeName):
    """根据快捷键方案名获取对应的快捷键列表"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        return []
    # 直接获取顶层的 shortcuts 列表
    shortcuts = config.get("shortcuts", [])
    return shortcuts


def getStartupEnabledShortcutBySchemeName(schemeName):
    """根据方案名字获取被设置为启用状态的快捷键列表"""
    shortcuts = getShortcutBySchemeName(schemeName)
    enabledShortcuts = [s for s in shortcuts if s.get("enabled", False)]
    return enabledShortcuts


def getStartupEnabledShortcutNameBySchemeName(schemeName):
    """根据方案名字获取被设置为启用状态的快捷键名称列表"""
    enabledShortcuts = getStartupEnabledShortcutBySchemeName(schemeName)
    enabledShortcutNames = [s.get("name", "") for s in enabledShortcuts]
    return enabledShortcutNames


def getShortcutByShortcutId(schemeName, shortcutId):
    """根据快捷键方案名和快捷键ID获取对应的快捷键"""
    shortcuts = getShortcutBySchemeName(schemeName)
    for shortcut in shortcuts:
        if shortcut.get("id") == shortcutId:
            return shortcut
    return None  # 如果没有找到对应的快捷键，返回 None


def getshortcut(shortcut):
    """根据快捷键获取对应的快捷键信息"""
    if shortcut is None:
        return {}
    shortcutInfo = {
        "id": shortcut.get("id", 0),
        "name": shortcut.get("name", ""),
        "description": shortcut.get("description", ""),
        "enabled": shortcut.get("enabled", False),
        "keyCombination": shortcut.get("keyCombination", ""),
        "action": shortcut.get("action", "")
    }
    return shortcutInfo


def getAllSchemesWithShortcuts(folderPath):
    """
    获取所有方案的完整数据（包含快捷键列表），用于冲突检测。
    """
    folder = Path(folderPath)
    if not folder.exists() or not folder.is_dir():
        return []

    all_schemes = []
    for f in folder.iterdir():
        if not f.is_file() or f.suffix != ".json":
            continue
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                if isinstance(data, dict) and "shortcuts" in data:
                    settings = data.get("settings", {})
                    all_schemes.append({
                        "name": settings.get("name", f.stem),
                        "startupEnabled": settings.get("startupEnabled", False),
                        "conflictDetectionMode": settings.get("conflictDetectionMode", "关闭"),  # <-- 新增这一行
                        "shortcuts": data.get("shortcuts", [])
                    })
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

    return all_schemes


def normalize_key_combination(key_str):
    """
    【按键归一化】
    用于解决用户手写时顺序不一致的问题，比如 "ctrl+alt+1" 和 "alt+ctrl+1"。
    思路：转小写 -> 按 '+' 拆分 -> 去除首尾空格 -> 排序 -> 重新拼接。
    这样在比对时，只要按键一样，顺序无所谓。
    """
    if not key_str:
        return ""
    parts = [p.strip().lower() for p in key_str.split('+') if p.strip()]
    #将转义的 'plus' 还原为真实的 '+' 字符
    parts = ["+" if p == "plus" else p for p in parts]
    parts.sort()
    return "+".join(parts)


def analyzeConflicts(targetSchemeName, detectionMode, allSchemesData):
    """ 核心冲突检测逻辑（纯数据逻辑，不涉及UI）
    返回一个结构化的“冲突报告”字典。

    31/33 号新增字段：
        has_reserved / reserved_conflicts —— 保留组合冲突。与检测模式无关的
        硬事实（绑了就会被 executor 路由永久截胡），无条件计算，渲染层据此
        在包括"关闭"在内的所有模式下显示警告。
    """
    # 1. 找到当前方案的数据
    currentScheme = None
    for scheme in allSchemesData:
        if scheme["name"] == targetSchemeName:
            currentScheme = scheme
            break

    # 如果找不到当前方案，返回空报告
    if currentScheme is None:
        return {
            "scheme_name": targetSchemeName,
            "has_internal": False,
            "internal_conflicts": {},
            "has_cross": False,
            "cross_conflicts": [],
            "has_reserved": False,          # 31/33 新增，保持报告形状一致
            "reserved_conflicts": [],       # 31/33 新增
            "mode": detectionMode,
            "no_other_enabled_scheme": False,
        }

    # 获取当前方案中“已启用”的快捷键
    currentEnabledShortcuts = [s for s in currentScheme.get("shortcuts", []) if s.get("enabled", False)]

    # ==============================
    # 2. 内部冲突检测（只看自己）
    # ==============================
    internalConflictsMap = {}
    for sc in currentEnabledShortcuts:
        # 【关键】：使用归一化后的按键进行分组
        normKey = normalize_key_combination(sc.get("keyCombination", ""))
        if not normKey:
            continue
        internalConflictsMap.setdefault(normKey, []).append(sc.get("id"))

    internalConflicts = {k: v for k, v in internalConflictsMap.items() if len(v) > 1}

    # ==============================
    # 2.5 保留组合冲突检测（31/33 号新增）
    # ==============================
    # 校验语义 = checkReservedConflict（别名归一 + 统称通配感知），与
    # keyValidator 同源 —— 单点真相源，此处禁止重写第二份匹配逻辑。
    # 注意与内部冲突同口径：只查"已启用"的快捷键。
    reservedConflicts = []
    for sc in currentEnabledShortcuts:
        rawKey = sc.get("keyCombination", "")
        if not rawKey:
            continue
        # 直接拆原始串喂给校验器（它内部做别名归一，不依赖 normalize_key_combination）
        tokens = [p.strip().lower() for p in rawKey.split('+') if p.strip()]
        is_reserved, _msg, kinds = checkReservedConflict(tokens)
        if is_reserved:
            reservedConflicts.append({
                "id": sc.get("id"),
                "key": rawKey,
                "kinds_text": describeReservedKinds(kinds),
            })

    # ==============================
    # 3. 跨方案冲突检测（看别人）
    # ==============================
    crossConflicts = []
    # 【新增】用于前端提醒：当前模式为"当前启用的方案与此方案"时，是否存在其他已启用的方案
    no_other_enabled_scheme = False

    # 只有在模式不是"关闭"且不是"仅此方案内"时，才进行跨方案检测
    if detectionMode not in ["关闭", "仅此方案内"]:

        # 【新增】若是"当前启用的方案与此方案"模式，先统计除自己外是否有任何启用方案
        if detectionMode == "当前启用的方案与此方案":
            otherEnabledSchemes = [
                s for s in allSchemesData
                if s["name"] != targetSchemeName and s.get("startupEnabled", False)
            ]
            no_other_enabled_scheme = len(otherEnabledSchemes) == 0

        # ==================== 顺带修复（本轮发现④）====================
        # 原代码在此处的外层 "for scheme in allSchemesData:" 循环体内，又嵌套
        # 了一层完全相同的外循环（内层变量遮蔽外层），导致每对跨方案冲突被
        # 重复追加 (方案数-1) 次 —— 只有两个方案时恰好只跑一遍所以从未暴露，
        # 三个及以上方案时报告里同一冲突出现多行。修复：删除外层循环，
        # 只保留一遍遍历。语义与文件头部架构文档（"看别人"单遍比对）一致。
        # =============================================================
        for scheme in allSchemesData:

            # 不和自己比较
            if scheme["name"] == targetSchemeName:
                continue

            # 如果模式是“当前启用的方案与此方案”，则跳过未启动启用的方案
            if detectionMode == "当前启用的方案与此方案" and not scheme.get("startupEnabled", False):
                continue

            # 获取对方方案中“已启用”的快捷键
            otherEnabledShortcuts = [s for s in scheme.get("shortcuts", []) if s.get("enabled", False)]

            # 构建对方方案 按键 -> ID 的索引
            otherKeyMap = {}
            for otherSc in otherEnabledShortcuts:
                otherNormKey = normalize_key_combination(otherSc.get("keyCombination", ""))
                if otherNormKey:
                    otherKeyMap.setdefault(otherNormKey, []).append(otherSc.get("id"))

            # 遍历当前方案进行比对
            for mySc in currentEnabledShortcuts:
                myNormKey = normalize_key_combination(mySc.get("keyCombination", ""))
                if myNormKey and myNormKey in otherKeyMap:
                    for otherId in otherKeyMap[myNormKey]:
                        crossConflicts.append({
                            "my_id": mySc.get("id"),
                            "other_scheme": scheme["name"],
                            "other_id": otherId,
                            "key": mySc.get("keyCombination", "")
                        })

    # ==============================
    # 4. 组装并返回报告
    # ==============================
    return {
        "scheme_name": targetSchemeName,
        "has_internal": len(internalConflicts) > 0,
        "internal_conflicts": internalConflicts,
        "has_cross": len(crossConflicts) > 0,
        "cross_conflicts": crossConflicts,
        "has_reserved": len(reservedConflicts) > 0,       # 31/33 新增
        "reserved_conflicts": reservedConflicts,          # 31/33 新增
        "mode": detectionMode,
        "no_other_enabled_scheme": no_other_enabled_scheme,
    }

