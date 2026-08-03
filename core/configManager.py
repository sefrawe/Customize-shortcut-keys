'''配置文件和项目路径管理'''
import json
import re
from pathlib import Path
from tkinter import messagebox

from utils.shortcutUtils import theNumberOfTargetFilesInTheFolder, checkForDuplicateShortcutSchemeNames, \
    getShortcutSchemesNames, getShortcutSchemeConfigBySchemeName, getShortcutSchemeConfigById

# Path(__file__)         → core/config_manager.py
# .resolve()             → 转为绝对路径
# .parent                → core/
# .parent.parent         → 项目根目录
proJectrootDirectory = Path(__file__).resolve().parent.parent
configDirectory = proJectrootDirectory / "config"
globalSettingspath = configDirectory / "Global Settings.json"

currentNumberOfShortcutKeySchemes = theNumberOfTargetFilesInTheFolder(configDirectory)
numberOfNavigationBarItems = currentNumberOfShortcutKeySchemes + 2  # 2表示除了快捷键方案之外，还有首页和设置两个固定导航项


def loadThemeFromConfig():
    with open(globalSettingspath, "r", encoding="utf-8") as f:
        globalSettings = json.load(f)
    return globalSettings.get("appearanceMode", "System")  # 从配置文件中读取外观模式，如果没有找到该配置，则默认返回"System"。


def saveThemeToConfig(choice):
    with open(globalSettingspath, "r+", encoding="utf-8") as f:
        globalSettings = json.load(f)
        globalSettings["appearanceMode"] = choice
        f.seek(0)  # 将文件指针移动到文件开头，以便覆盖原有内容
        json.dump(globalSettings, f, ensure_ascii=False,
                  indent=2)  # 将修改后的配置写回文件，ensure_ascii=False表示允许写入非ASCII字符，indent=2表示使用2个空格进行缩进，使JSON文件更易读
        f.truncate()  # 截断文件，删除文件中指针位置之后的内容，以防止新内容比原内容短而导致文件末尾残留旧数据


def loadGlobalSettings():
    with open(globalSettingspath, "r", encoding="utf-8") as f:
        globalSettings = json.load(f)
    return globalSettings


def saveGlobalSettings(settings):
    with open(globalSettingspath, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def createNewShortcutSchemeConfig(newName):
    # 主窗口中创建新的快捷键方案的配置
    refresgCurrentNumberOfShortcutKeySchemes()  # 防止新建多个快捷键方案不重启导致多个快捷键方案id相同

    if checkForDuplicateShortcutSchemeNames(configDirectory) or newName in getShortcutSchemesNames(configDirectory):
        raise ValueError(f"快捷键方案名称 '{newName}' 已存在，请更换名称")
    newConfig = {
        "settings": {
            "name": newName,
            "description": "这是一个新建快捷键方案",
            "startupEnabled": False,
            "currentProfileId": currentNumberOfShortcutKeySchemes
        },
        "shortcuts": [  # <-- 把 "profiles" 改成 "shortcuts"
        ]
    }
    return newConfig



def refresgCurrentNumberOfShortcutKeySchemes():
    global currentNumberOfShortcutKeySchemes
    currentNumberOfShortcutKeySchemes = theNumberOfTargetFilesInTheFolder(configDirectory)


def saveShortcutSchemeConfig(newConfig, newName):
    newFilePath = configDirectory / f"{newName}.json"
    with open(newFilePath, "w", encoding="utf-8") as f:
        json.dump(newConfig, f, ensure_ascii=False, indent=2)


def changeShortcutSchemeConfig_Name(newName, schemeId=None, oldName=None):
    """修改配置文件中的快捷键方案名称"""
    if oldName is not None and schemeId is None:
        # ===== 第1步：查找目标文件 =====
        # 先按 settings.name 遍历查找
        targetFile = None
        Config = None
        for file in configDirectory.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if config.get("settings", {}).get("name") == oldName:
                    targetFile = file
                    Config = config
                    break
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        # ★ 关键：如果按内容找不到，回退到按文件名查找
        if targetFile is None:
            targetFile = configDirectory / f"{oldName}.json"
            if targetFile.exists():
                with open(targetFile, "r", encoding="utf-8") as f:
                    Config = json.load(f)
            else:
                raise FileNotFoundError(f"找不到方案 '{oldName}' 的配置文件")

        # ===== 第2步：修改名称并保存新文件 =====
        Config["settings"]["name"] = newName
        saveShortcutSchemeConfig(Config, newName)

        # ===== 第3步：删除旧文件（直接用路径删除，不再调用 deleteShortcutSchemeConfig）=====
        targetFile.unlink()

    elif schemeId is not None and oldName is None:
        # 按 ID 查找（同理改为直接遍历）
        targetFile = None
        Config = None
        for file in configDirectory.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if config.get("settings", {}).get("currentProfileId") == schemeId:
                    targetFile = file
                    Config = config
                    break
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        if targetFile is None:
            raise FileNotFoundError(f"找不到方案ID '{schemeId}' 的配置文件")

        Config["settings"]["name"] = newName
        saveShortcutSchemeConfig(Config, newName)
        targetFile.unlink()


def changeShortcutSchemeConfig_Description(newDescription="", schemeId=None, name=None):
    # 修改配置文件中的快捷键方案描述
    if name is not None and schemeId is None:
        # 按方案名查找
        config = getShortcutSchemeConfigBySchemeName(name)
        if config is None:
            raise FileNotFoundError(f"找不到方案 '{name}' 的配置文件")
        config["settings"]["description"] = newDescription
        # 保存 (注意：此时文件名应该和 schemeName 是一致的，如果改名后还没刷新可能会报错，但正常流程没问题)
        saveShortcutSchemeConfig(config, name)
    elif schemeId is not None and name is None:
        # 按ID查找
        config = getShortcutSchemeConfigById(schemeId)
        if config is None:
            raise FileNotFoundError(f"找不到方案ID '{schemeId}' 的配置文件")
        config["settings"]["description"] = newDescription
        saveShortcutSchemeConfig(config, config["settings"]["name"])


def changeShortcutSchemeConfig_StartupEnabled(name=None, schemeId=None, newStartupEnabled=False):
    # 修改配置文件中的快捷键方案启动启用状态
    if name is not None and schemeId is None:
        for file in configDirectory.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                config = json.load(f)
            if config.get("settings", {}).get("name") == name:
                config["settings"]["startupEnabled"] = newStartupEnabled
                saveShortcutSchemeConfig(config, name)
                return
        raise FileNotFoundError(f"快捷键方案 '{name}' 的配置文件不存在")
    elif schemeId is not None and name is None:
        for file in configDirectory.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                config = json.load(f)
            if config.get("settings", {}).get("currentProfileId") == schemeId:
                config["settings"]["startupEnabled"] = newStartupEnabled
                saveShortcutSchemeConfig(config, config["settings"]["name"])
                return
        raise FileNotFoundError(f"快捷键方案ID '{schemeId}' 的配置文件不存在")
    else:
        try:
            if name is not None and schemeId is not None:
                raise ValueError("只能指定方案名称或方案ID中的一个，不能同时指定两个")
        except ValueError as e:
            messagebox.showerror("错误", str(e))



def changeShortcutSchemeConfig(schemeName=None, schemeId=None, newSchemeName=None, newDescription=None,
                               newStartupEnabled=None):
    # 修改快捷键方案的配置
    # 当 schemeName 不为 None 且 schemeId 为 None 时，使用 schemeName 来修改配置
    if schemeName is not None and schemeId is None:
        if newSchemeName is not None and newSchemeName.strip() != "":
            changeShortcutSchemeConfig_Name(newName=newSchemeName, oldName=schemeName)
        if newDescription is not None and newDescription.strip() != "":
            changeShortcutSchemeConfig_Description(newDescription=newDescription, name=schemeName)
        if newStartupEnabled is not None:
            changeShortcutSchemeConfig_StartupEnabled(name=schemeName, newStartupEnabled=newStartupEnabled)
    # 当 schemeId 不为 None 且 schemeName 为 None 时，使用 schemeId 来修改配置
    if schemeId is not None and schemeName is None:
        if newSchemeName is not None and newSchemeName.strip() != "":
            changeShortcutSchemeConfig_Name(newName=newSchemeName, schemeId=schemeId)
        if newDescription is not None and newDescription.strip() != "":
            changeShortcutSchemeConfig_Description(newDescription=newDescription, schemeId=schemeId)
        if newStartupEnabled is not None:
            changeShortcutSchemeConfig_StartupEnabled(schemeId=schemeId, newStartupEnabled=newStartupEnabled)
    # 当 schemeName 和 schemeId 都为 None 时，抛出异常
    try:
        if schemeName is not None and schemeId is not None:
            raise ValueError("只能指定方案名称或方案ID中的一个，不能同时指定两个")
    except ValueError as e:
        messagebox.showerror("错误", str(e))
    # 当 schemeName 和 schemeId 都为 None 时，抛出异常
    try:
        if schemeName is None and schemeId is None:
            raise ValueError("必须且只能指定方案名称或方案ID中的一个")
    except ValueError as e:
        messagebox.showerror("错误", str(e))


def changeShortcutSchemeConfig(schemeName=None, schemeId=None, newSchemeName=None,
                               newDescription=None, newStartupEnabled=None):
    if schemeName is not None and schemeId is None:
        # 记录实际要操作的方案名（如果改了名，后续用新名字）
        effectiveName = schemeName
        if newSchemeName is not None and newSchemeName.strip() != "":
            changeShortcutSchemeConfig_Name(newName=newSchemeName, oldName=schemeName)
            effectiveName = newSchemeName  # ★ 改名后，后续操作用新名字
        if newDescription is not None and newDescription.strip() != "":
            changeShortcutSchemeConfig_Description(newDescription=newDescription,
                                                   name=effectiveName)  # ★ 用 effectiveName
        if newStartupEnabled is not None:  # ★ 默认 None，不传就不执行
            changeShortcutSchemeConfig_StartupEnabled(name=effectiveName,
                                                      newStartupEnabled=newStartupEnabled)  # ★ 用 effectiveName
    if schemeId is not None and schemeName is None:
        effectiveName = None  # 需要先查出当前名字
        if newSchemeName is not None and newSchemeName.strip() != "":
            # 改名前先查出当前名字
            config = getShortcutSchemeConfigById(schemeId)
            if config is None:
                raise FileNotFoundError(f"找不到方案ID '{schemeId}' 的配置文件")
            oldName = config["settings"]["name"]
            changeShortcutSchemeConfig_Name(newName=newSchemeName, schemeId=schemeId)
            effectiveName = newSchemeName
        else:
            config = getShortcutSchemeConfigById(schemeId)
            if config is None:
                raise FileNotFoundError(f"找不到方案ID '{schemeId}' 的配置文件")
            effectiveName = config["settings"]["name"]
        if newDescription is not None and newDescription.strip() != "":
            changeShortcutSchemeConfig_Description(newDescription=newDescription, name=effectiveName)
        if newStartupEnabled is not None:
            changeShortcutSchemeConfig_StartupEnabled(name=effectiveName, newStartupEnabled=newStartupEnabled)
    try:
        if schemeName is not None and schemeId is not None:
            raise ValueError("只能指定方案名称或方案ID中的一个，不能同时指定两个")
    except ValueError as e:
        messagebox.showerror("错误", str(e))
    try:
        if schemeName is None and schemeId is None:
            raise ValueError("必须且只能指定方案名称或方案ID中的一个")
    except ValueError as e:
        messagebox.showerror("错误", str(e))

def copyShortcutSchemeConfig(newSchemeName, schemeName):
    """复制快捷键方案配置文件"""
    #校验在调用该函数的函数中做了
    # 获取原方案配置
    originalConfig = getShortcutSchemeConfigBySchemeName(schemeName)
    if originalConfig is None:
        raise FileNotFoundError(f"找不到方案 '{schemeName}' 的配置文件")
    # 创建新配置
    newConfig = originalConfig.copy()
    newConfig["settings"]["name"] = newSchemeName
    # newConfig["settings"]["description"] = originalConfig["settings"]["description"]
    refresgCurrentNumberOfShortcutKeySchemes()
    newConfig["settings"]["startupEnabled"] = False  # 新方案默认不启用
    newConfig["settings"]["currentProfileId"] = currentNumberOfShortcutKeySchemes  # 新方案的ID为当前数量
    saveShortcutSchemeConfig(newConfig, newSchemeName)


def deleteShortcutSchemeConfig(schemeName=None, schemeId=None):
    # 遍历查找 settings.name 匹配的文件再删除
    if schemeName is not None and schemeId is None:
        for file in configDirectory.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                config = json.load(f)
            if config.get("settings", {}).get("name") == schemeName:
                file.unlink()
                return
        raise FileNotFoundError(f"快捷键方案 '{schemeName}' 的配置文件不存在")
    elif schemeId is not None and schemeName is None:  # 按文件名删除
        for file in configDirectory.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                config = json.load(f)
            if config.get("settings", {}).get("currentProfileId") == schemeId:
                file.unlink()  # 删除文件
                return
        raise FileNotFoundError(f"快捷键方案ID '{schemeId}' 的配置文件不存在")
    else:
        try:
            if schemeName is not None and schemeId is not None:
                raise ValueError("只能指定方案名称或方案ID中的一个，不能同时指定两个")
        except ValueError as e:
            messagebox.showerror("错误", str(e))

def changeShortcutConfig_enabled(schemeName, shortcutId,newStatus):
    """切换快捷键的在配置中的启用状态"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        raise FileNotFoundError(f"找不到方案 '{schemeName}' 的配置文件")
    # 遍历快捷键列表，找到对应的快捷键并修改其 enabled 状态
    for shortcut in config.get("shortcuts", []):
        if shortcut.get("id") == shortcutId:
            shortcut["enabled"] = newStatus
            saveShortcutSchemeConfig(config, schemeName)
            return
    raise ValueError(f"在方案 '{schemeName}' 中找不到ID为 '{shortcutId}' 的快捷键")

def addShortcut(schemeName, shortcutName):
    """添加新的快捷键"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        raise FileNotFoundError(f"找不到方案 '{schemeName}' 的配置文件")
    # 获取现有快捷键的最大ID
    existingIds = []
    for shortcut in config.get("shortcuts", []):
        shortcutId = shortcut.get("id")
        if isinstance(shortcutId, int):
            existingIds.append(shortcutId)
        elif isinstance(shortcutId, str):
            match = re.search(r"(\d+)$", shortcutId)
            if match:
                existingIds.append(int(match.group(1)))
    nextId = max(existingIds, default=-1) + 1
    # 创建新的快捷键
    newShortcut = {
        "id": nextId,
        "name": shortcutName,
        "description": "这是注释",
        "keyCombination": "ctrl+alt+shift",
        "action": "",
        "actionParams": {},
        "enabled": False
    }
    config.get("shortcuts", []).append(newShortcut)
    saveShortcutSchemeConfig(config, schemeName)
