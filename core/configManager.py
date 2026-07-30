'''配置文件和项目路径管理'''
import json
from pathlib import Path

# Path(__file__)         → core/config_manager.py
# .resolve()             → 转为绝对路径
# .parent                → core/
# .parent.parent         → 项目根目录
proJectrootDirectory = Path(__file__).resolve().parent.parent
configDirectory = proJectrootDirectory / "config"
globalSettingspath = configDirectory / "Global Settings.json"

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