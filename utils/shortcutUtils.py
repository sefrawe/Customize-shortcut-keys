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
    parts.sort()
    return "+".join(parts)


def analyzeConflicts(targetSchemeName, detectionMode, allSchemesData):
    """
    核心冲突检测逻辑（纯数据逻辑，不涉及UI）
    返回一个结构化的“冲突报告”字典。
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
            "mode": detectionMode
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
        if not normKey:  # 空按键组合跳过
            continue
        # 按按键组合分组，把 ID 放进列表
        internalConflictsMap.setdefault(normKey, []).append(sc.get("id"))

    # 剔除只有1个快捷键使用的按键（即没有冲突的）
    internalConflicts = {k: v for k, v in internalConflictsMap.items() if len(v) > 1}

    # ==============================
    # 3. 跨方案冲突检测（看别人）
    # ==============================
    crossConflicts = []

    # 只有在模式不是“关闭”且不是“仅此方案内”时，才进行跨方案检测
    if detectionMode not in ["关闭", "仅此方案内"]:
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
        "scheme_name": targetSchemeName,  # 补上 scheme_name 字段
        "has_internal": len(internalConflicts) > 0,
        "internal_conflicts": internalConflicts,  # 格式: {"ctrl+alt+1": [0, 2]}
        "has_cross": len(crossConflicts) > 0,
        "cross_conflicts": crossConflicts,  # 格式: [{"my_id": 0, "other_scheme": "方案B", "other_id": 1, "key": "ctrl+c"}]
        "mode": detectionMode
    }

