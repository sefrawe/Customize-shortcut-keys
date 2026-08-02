'''配置文件和项目路径管理'''
import json
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
            "currentProfileId": currentNumberOfShortcutKeySchemes  # 从0开始计数，当前快捷键方案的ID为当前已有快捷键方案数量

        },
        "profiles": [

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


# def changeShortcutSchemeConfig_Name(newName,schemeId=None, oldName=None):
#     # 修改配置文件中的快捷键方案名称
#     if oldName is not None and schemeId is None:
#         Config = getShortcutSchemeConfigBySchemeName(oldName)
#         Config["settings"]["name"] = newName
#         # 保存修改后的配置文件
#         saveShortcutSchemeConfig(Config, newName)
#         deleteShortcutSchemeConfig(oldName)
#     if schemeId is not None and oldName is None:
#         Config = getShortcutSchemeConfigById(schemeId)
#         Config["settings"]["name"] = newName
#         # 保存修改后的配置文件
#         saveShortcutSchemeConfig(Config, newName)
# ❌ 旧代码：Config 为 None 时直接崩溃

# ✅ 新代码：加 None 检查，给出清晰的错误提示
# def changeShortcutSchemeConfig_Name(newName, schemeId=None, oldName=None):
#     if oldName is not None and schemeId is None:
#         config = getShortcutSchemeConfigBySchemeName(oldName)
#         if config is None:
#             raise FileNotFoundError(f"找不到方案 '{oldName}' 的配置文件")
#         config["settings"]["name"] = newName
#         saveShortcutSchemeConfig(config, newName)
#         deleteShortcutSchemeConfig(oldName)
#     # ... schemeId 部分加同样的 None 检查
#     if schemeId is not None and oldName is None:
#         config = getShortcutSchemeConfigById(schemeId)
#         if config is None:
#             raise FileNotFoundError(f"找不到方案ID '{schemeId}' 的配置文件")
#         config["settings"]["name"] = newName
#         saveShortcutSchemeConfig(config, newName)
#
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


def deleteShortcutSchemeConfig(schemeName=None, schemeId=None):
    # ✅ 新代码：遍历查找 settings.name 匹配的文件再删除
    if schemeName is not None and schemeId is None:
        for file in configDirectory.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                config = json.load(f)
            if config.get("settings", {}).get("name") == schemeName:
                file.unlink()
                return
        raise FileNotFoundError(f"快捷键方案 '{schemeName}' 的配置文件不存在")
    elif schemeId is not None and schemeName is None:  # ❌ 旧代码：按文件名删除
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


def changeShortcutSchemeConfig(schemeName=None, schemeId=None, newSchemeName=None, newDescription=None,
                               newStartupEnabled=False):
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

# {
#     "settings": {
#         "name": "测试快捷键方案",
#         "description": "测试快捷键方案",
#         "startupEnabled": true,
#         "currentProfileId": 0
#     },
#     "profiles": [
#         {
#             "id": 1,
#             "name": "我的快捷键1",
#             "description": "自定义快捷键1",
#             "type": "custom",
#             "readOnly": false,
#             "shortcuts": [
#                 {
#                     "keyCombination": "ctrl+alt+1",
#                     "action": "copyText",
#                     "actionParams": {"text": "myemail@example.com"},
#                     "enabled": true
#                 }
#             ]
#         },
#         {
#             "id": 2,
#             "name": "我的快捷键2",
#             "description": "自定义快捷键2",
#             "readOnly": false,
#             "type": "custom",
#             "shortcuts": [
#                 {
#                     "keyCombination": "ctrl+alt+2",
#                     "action": "copyText",
#                     "actionParams": {"text": "myemail2@example.com"},
#                     "enabled": true
#                 }
#             ]
#         }
#     ]
# }
