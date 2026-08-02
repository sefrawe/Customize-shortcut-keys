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


# def getShortcutSchemesDescriptions(folderPath):
#     """获取文件夹中所有快捷键方案的描述"""
#     schemes = getShortcutSchemes(folderPath)
#     return [scheme["description"] for scheme in schemes]

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


# def getShortcutSchemeConfigBySchemeName(schemeName):
#     # 根据快捷键方案名获取对应的配置文件内容# ❌ 旧代码：按文件名查找，文件名≠方案名时就返回 None
#     schemeFilePath = configDirectory / f"{schemeName}.json"
#     if not schemeFilePath.exists():
#         return None
#     with open(schemeFilePath, "r", encoding="utf-8") as f:
#         config = json.load(f)
#     return config
# ✅ 新代码：遍历所有 JSON，按 settings.name 匹配（和 getShortcutSchemeConfigById 同思路）
def getShortcutSchemeConfigBySchemeName(schemeName):
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


def getProfileBySchemeName(schemeName):
    """根据快捷键方案名获取对应的配置文件中的profiles列表"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        return []
    profiles = config.get("profiles", [])
    return profiles

def getProfileInfoBySchemeName(schemeName):
    """根据快捷键方案名获取对应的配置文件中的profiles列表，并返回每个profile的基本信息"""
    profiles = getProfileBySchemeName(schemeName)
    profileInfoList = []
    for profile in profiles:
        profileInfo = {
            "id": profile.get("id", 0),
            "name": profile.get("name", ""),
            "description": profile.get("description", ""),
            "type": profile.get("type", ""),
            "readOnly": profile.get("readOnly", False),
            "shortcutsCount": len(profile.get("shortcuts", []))
        }
        profileInfoList.append(profileInfo)
    return profileInfoList

if __name__=="__main__":
    print(getProfileInfoBySchemeName("方案1"))
    print("\n")
    print(getProfileBySchemeName("方案1"))
    print("\n")
    print(getShortcutBySchemeName("方案1"))
