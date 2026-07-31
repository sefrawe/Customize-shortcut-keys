'''配置文件和项目路径管理'''
import json
from pathlib import Path

from utils.shortcutUtils import theNumberOfTargetFilesInTheFolder

# Path(__file__)         → core/config_manager.py
# .resolve()             → 转为绝对路径
# .parent                → core/
# .parent.parent         → 项目根目录
proJectrootDirectory = Path(__file__).resolve().parent.parent
configDirectory = proJectrootDirectory / "config"
globalSettingspath = configDirectory / "Global Settings.json"

currentNumberOfShortcutKeySchemes = theNumberOfTargetFilesInTheFolder(configDirectory)
numberOfNavigationBarItems =currentNumberOfShortcutKeySchemes+2# 2表示除了快捷键方案之外，还有首页和设置两个固定导航项

def loadThemeFromConfig():
    with open(globalSettingspath, "r", encoding="utf-8") as f:
        globalSettings = json.load(f)
    return globalSettings.get("appearanceMode", "System")#从配置文件中读取外观模式，如果没有找到该配置，则默认返回"System"。

def saveThemeToConfig(choice):
    with open(globalSettingspath, "r+", encoding="utf-8") as f:
        globalSettings = json.load(f)
        globalSettings["appearanceMode"] = choice
        f.seek(0)#将文件指针移动到文件开头，以便覆盖原有内容
        json.dump(globalSettings, f, ensure_ascii=False, indent=2)#将修改后的配置写回文件，ensure_ascii=False表示允许写入非ASCII字符，indent=2表示使用2个空格进行缩进，使JSON文件更易读
        f.truncate()#截断文件，删除文件中指针位置之后的内容，以防止新内容比原内容短而导致文件末尾残留旧数据


def loadGlobalSettings():
    with open(globalSettingspath, "r", encoding="utf-8") as f:
        globalSettings = json.load(f)
    return globalSettings

def saveGlobalSettings(settings):
    with open(globalSettingspath, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def createNewShortcutSchemeConfig(newName):
    # 主窗口中创建新的快捷键方案的配置
    newConfig = {
        "settings": {
            "name": newName,
            "description": "这是一个新建快捷键方案",
            "startupEnabled": False,
            "currentProfileId": currentNumberOfShortcutKeySchemes#从0开始计数，当前快捷键方案的ID为当前已有快捷键方案数量
        },
        "profiles": [

        ]
    }
    return newConfig

def saveShortcutSchemeConfig(newConfig, newName):
    newFilePath = configDirectory / f"{newName}.json"
    with open(newFilePath, "w", encoding="utf-8") as f:
        json.dump(newConfig, f, ensure_ascii=False, indent=2)


    # {
    #     "settings": {
    #         "name": "测试快捷键方案",
    #         "description": "测试快捷键方案",
    #         "startupEnabled": true,
    #         "currentProfileId": 1
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


