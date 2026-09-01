'''配置文件管理'''

import json
import re
from tkinter import messagebox

# Path(__file__)         → core/config_manager.py
# .resolve()             → 转为绝对路径
# .parent                → core/
# .parent.parent         → 项目根目录
from core.pathResolver import proJectrootDirectory
from utils.interpreterRegistry import INTERPRETER_REGISTRY
from utils.shortcutUtils import theNumberOfTargetFilesInTheFolder, checkForDuplicateShortcutSchemeNames, \
    getShortcutSchemesNames, getShortcutSchemeConfigBySchemeName, getShortcutSchemeConfigById

configDirectory = proJectrootDirectory / "config"
globalSettingspath = configDirectory / "Global Settings.json"
configDirectory.mkdir(exist_ok=True)

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
            "conflictDetectionMode": "仅此方案内",
            "currentProfileId": currentNumberOfShortcutKeySchemes
        },
        "shortcuts": [

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

        if newSchemeName is not None and newSchemeName.strip() != "":
            # 改名前先查出当前名字
            config = getShortcutSchemeConfigById(schemeId)
            if config is None:
                raise FileNotFoundError(f"找不到方案ID '{schemeId}' 的配置文件")

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
    # 校验在调用该函数的函数中做了
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


def changeShortcutConfig_enabled(schemeName, shortcutId, newStatus):
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
        "description": "新建快捷键，未指定动作",
        "keyCombination": "ctrl+alt+shift",
        "action": "",
        "actionParams": {},
        "enabled": False
    }
    config.get("shortcuts", []).append(newShortcut)
    saveShortcutSchemeConfig(config, schemeName)


def deleteShortcut(schemeName, shortcutId):
    """删除指定快捷键"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        raise FileNotFoundError(f"找不到方案 '{schemeName}' 的配置文件")
    # 遍历快捷键列表，找到对应的快捷键并删除
    for i, shortcut in enumerate(config.get("shortcuts", [])):
        if shortcut.get("id") == shortcutId:
            del config["shortcuts"][i]
            saveShortcutSchemeConfig(config, schemeName)
            return
    raise ValueError(f"在方案 '{schemeName}' 中找不到ID为 '{shortcutId}' 的快捷键")


def resignShortcutIds(schemeName):
    """重新分配快捷键ID，确保ID连续"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        raise FileNotFoundError(f"找不到方案 '{schemeName}' 的配置文件")
    shortcuts = config.get("shortcuts", [])
    for index, shortcut in enumerate(shortcuts):
        shortcut["id"] = index
    saveShortcutSchemeConfig(config, schemeName)

def copyShortcut(schemeName, oldShortcutId, newShortcutName):
    """复制指定快捷键"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        raise FileNotFoundError(f"找不到方案 '{schemeName}' 的配置文件")
    # 遍历快捷键列表，找到对应的快捷键并复制
    for shortcut in config.get("shortcuts", []):
        if shortcut.get("id") == oldShortcutId:
            newShortcut = shortcut.copy()
            # 获取现有快捷键的最大ID
            existingIds = [s.get("id") for s in config.get("shortcuts", []) if isinstance(s.get("id"), int)]
            nextId = max(existingIds, default=-1) + 1
            newShortcut["id"] = nextId
            newShortcut["name"] = newShortcutName
            config.get("shortcuts", []).append(newShortcut)
            saveShortcutSchemeConfig(config, schemeName)
            return
    raise ValueError(f"在方案 '{schemeName}' 中找不到ID为 '{oldShortcutId}' 的快捷键")

def saveShortcutEdit(schemeName, shortcutId, newShortcutData):
    """保存编辑后的快捷键数据（整体覆盖单条快捷键）"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        raise FileNotFoundError(f"找不到方案 '{schemeName}' 的配置文件")
    shortcuts = config.get("shortcuts", [])
    for i, shortcut in enumerate(shortcuts):
        if shortcut.get("id") == shortcutId:
            # 保留原有 id，用新数据覆盖其余字段
            newShortcutData["id"] = shortcutId
            shortcuts[i] = newShortcutData
            saveShortcutSchemeConfig(config, schemeName)
            return
    raise ValueError(f"在方案 '{schemeName}' 中找不到ID为 '{shortcutId}' 的快捷键")


def changeShortcutSchemeConfig_conflictDetectionMode(schemeName, newMode):
    """改变快捷键方案的冲突检测模式"""
    config = getShortcutSchemeConfigBySchemeName(schemeName)
    if config is None:
        raise FileNotFoundError(f"找不到方案 '{schemeName}' 的配置文件")
    config["settings"]["conflictDetectionMode"] = newMode
    saveShortcutSchemeConfig(config, schemeName)
# 【改造动机】
# 改造前，"文本 → 字典"的解析逻辑存在两份副本（本文件 loadUserBlacklist
# 与 gui/SettingsPage.saveCustomBlacklist 各一份），且都患同一个病：
# 非法行【静默丢弃】——用户写错一行，保存提示照样"✅ 已保存"，
# 实际那行已经无声消失。对安全功能而言，"用户以为有保护、实际没有"
# 是最大的坑。
#
# 【改造内容】
# 1. 解析与序列化收敛为唯一真相源：
#    · parseBlacklistText  : 文本 → (字典, 丢弃级问题, 警告级问题)
#    · formatBlacklistDict : 字典 → 文本（保存写入与 UI 回显共用）
#    消费方：UI 保存（SettingsPage，把问题现形给用户）、
#            加载（loadUserBlacklist，问题仅控制台日志）。
#    从此格式定义只活在这一个文件里，与它的序列化器同处一室，
#    不可能出现"两份解析器各自漂移"。
# 2. 顺带修复真 bug：解释器名大小写导致黑名单整体失效——旧解析把
#    "[CMD]" 存成键 "CMD"，而匹配端（doCustomCommand）查的键是
#    spec.name（恒小写 "cmd"），永不命中。现在解析时统一 lower，
#    三条路径（UI 保存 / 加载 / 手改 JSON）同时治愈。修复只会扩大
#    保护面，绝不会让原本生效的条目失效。
# 3. 语法检查不做在输入过程（定稿 B7：违背工具短平快定位），只在
#    保存时跑一次解析器拿问题报告，呈现方式由 SettingsPage 决定。
#
# 【与旧实现的判定差异（唯一一处，属修复而非回归）】
# 旧正则 ^\[(.+?)\]\s*(.+)$ 对 "[ ] format" 这类行也能匹配
# （group1=" "），strip 后存成键 ""——永不命中任何 spec.name，
# 还会原样写回 JSON 成为永久死数据。新实现将其归入丢弃级。
# 其余所有旧行为（覆盖语义、注释跳过、关键词滤空）零变化。

# 合法解释器名集合：从注册表实时提取（单点）。未来注册表新增解释器
# 时，语法检查的识别名单自动跟随，不需要维护第二份名单。
# 注：集合里含 "unknown"（getInterpreterSpec 路径未识别时的兜底规格
# 名）。技术上 "[unknown] xxx" 会真的生效（匹配端查得到它），但属于
# 实现细节外溢——定稿拍板：照样警告 + 文案附注，见解析管线第 4 步。
_KNOWN_INTERPRETER_NAMES = {spec.name for spec in INTERPRETER_REGISTRY}

# 提示用名单：排除 unknown——它不是用户应该填的"可用解释器"，
# 列进提示会误导用户真的去写 [unknown]。
_HINT_INTERPRETERS = sorted(
    n for n in _KNOWN_INTERPRETER_NAMES if n != "unknown"
)

# 全角标点检测集合：关键词里出现这些，几乎必然是输入法没切回来。
# 典型事故："format，diskpart"（全角逗号）不会被英文逗号分割，整串
# 变成一个关键词，子串匹配几乎永不命中——隐形失效的经典样本。
# 全角空格不在此列：Python 的 strip() 与 \s 都认 \u3000，作分隔符
# 无实害，警告它属于误报。
_FULLWIDTH_PUNCT = "，、；：（）"


def parseBlacklistText(raw_text: str):
    """
    用户黑名单文本格式解析器（15 号新增，唯一真相源）。

    输入格式（每行）：
        [解释器名] 关键词1, 关键词2
        空行与 # 开头的行视为注释/空白，静默跳过（合法语法，不算问题）

    返回值三元组：
        blacklist_dict: dict
            解析成功的黑名单。键已 lower 归一化（治 [CMD] 永不命中的
            真 bug）；值保留关键词原大小写——匹配端 keyword.lower()
            本就大小写免疫，保留书写形态对用户更友好（PowerShell 的
            PascalCase 惯例不破坏）。
        drops: list[tuple[int, str, str]]
            【丢弃级】问题列表，元素为 (行号, 原因, 原始行)。
            丢弃级行不进字典——丢弃本身与旧行为一致（旧的是静默丢），
            差别是现在现形，由调用方决定呈现（SettingsPage 弹确认、
            loadUserBlacklist 打日志）。
        warns: list[str]
            【警告级】文案列表（已含行号）。警告级行照常进字典，
            仅提示用户可能写错了。

    设计纪律：
    - 一次收集全部问题再返回（keyValidator "省得用户来回试错"同款
      思路），不做逐行 fail-fast；
    - 静默跳过（空行/注释）不算问题——它们本来就是合法语法；
    - 与 keyValidator 的"默认拒 + 强制保存逃生口"方向相反：这里
      默认保（部分行无效不影响其余行），全丢时才要求用户确认——
      因为静默才是病，丢弃本身是合理行为。
    """
    blacklist_dict: dict[str, list[str]] = {}
    drops: list[tuple[int, str, str]] = []
    warns: list[str] = []

    # 已见解释器名集合，用于"多行同解释器"警告。
    # （旧实现的隐含行为：同解释器出现多行时后者覆盖前者，数据无声
    # 丢失。本轮保持覆盖语义零行为变化，仅让它现形为警告。）
    seen_interpreters: set[str] = set()

    for lineno, raw_line in enumerate(raw_text.split('\n'), start=1):
        line = raw_line.strip()

        # ── 第0步：空白与注释 → 合法语法，静默跳过（不计问题）──
        if not line or line.startswith('#'):
            continue

        # ── 第1步：结构识别 ──
        # 正则比旧版拆成两段语义：^\[(.*?)\] 认结构、(.*)$ 收剩余。
        # 好处是错误文案各归各位：
        #   "cmd format"   → 不匹配 → "缺少 [解释器名] 前缀"
        #   "【cmd】format" → 不匹配（全角括号）→ 同上
        #   "[cmd]"        → 匹配但剩余为空 → "没有任何有效关键词"
        #   （旧正则会把 "[cmd]" 误报成"缺少前缀"，文案与实情不符）
        match = re.match(r'^\[(.*?)\](.*)$', line)
        if not match:
            drops.append((lineno, "缺少 [解释器名] 前缀", line))
            continue

        interpreter = match.group(1).strip()
        keywords_str = match.group(2).strip()

        # ── 第2步：解释器名不能为空 ──
        # 旧实现会把这种行存成键 ""——永不命中任何 spec.name，还会
        # 原样写回 JSON 成为永久死数据（本轮唯一的行为差异点，修复）。
        if not interpreter:
            drops.append((lineno, "[ ] 内解释器名为空", line))
            continue

        # ── 第3步：关键词不能全空 ──
        # [cmd] 或 [cmd] , , 这类行，旧实现因 if keywords 不成立而
        # 静默消失，现形为丢弃级。
        keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
        if not keywords:
            drops.append((lineno, "方括号后没有任何有效关键词", line))
            continue

        # ── 归一化：解释器名 lower（真 bug 修复点）──
        # 匹配端查的是 spec.name（恒小写），键不 lower 永不命中。
        interpreter_lower = interpreter.lower()

        # ── 第4步（警告级）：解释器名不在注册表 ──
        # 拼写错误（cmds→cmd）保存不报错就永远不命中，必须现形。
        # unknown 特例照样警告，附一句兜底说明（定稿拍板第 3 项）。
        if interpreter_lower not in _KNOWN_INTERPRETER_NAMES:
            hint = " / ".join(_HINT_INTERPRETERS)
            text = (f"第 {lineno} 行：解释器名 '{interpreter}' 不在支持列表"
                    f"（可用：{hint}）")
            if interpreter_lower == "unknown":
                text += "（unknown 是路径未识别时的兜底解释器，一般无需专门配置）"
            warns.append(text)

        # ── 第5步（警告级）：关键词含全角标点 ──
        # 只检查关键词内部。全角逗号作分隔符是最常见的输入法事故：
        # "format，diskpart" 被当成一个关键词，子串匹配几乎永不命中。
        for kw in keywords:
            hit = [ch for ch in _FULLWIDTH_PUNCT if ch in kw]
            if hit:
                warns.append(
                    f"第 {lineno} 行：关键词 '{kw}' 含全角标点"
                    f"（{''.join(hit)}）——若本意是分隔多个关键词，"
                    f"请改用英文逗号"
                )

        # ── 第6步（警告级）：同行重复关键词 → 去重 + 提示 ──
        # 大小写不敏感判重（format/FORMAT 语义相同），保留首个书写
        # 形态（定稿拍板第 4 项）。判重用小写副本，收集重复形态用于
        # 展示，原文形态重复（format, format）只展示一次。
        deduped: list[str] = []
        seen_kw_lower: set[str] = set()
        duplicated: list[str] = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in seen_kw_lower:
                if kw not in duplicated:
                    duplicated.append(kw)
                continue
            seen_kw_lower.add(kw_lower)
            deduped.append(kw)
        if duplicated:
            warns.append(
                f"第 {lineno} 行：重复关键词 {'、'.join(duplicated)}"
                f"（已自动去重）"
            )

        # ── 第7步（警告级）：多行同解释器 → 保持覆盖语义 + 现形 ──
        # 旧实现后行覆盖前行、数据无声丢失。本轮行为不变（覆盖），
        # 仅补警告。"仅最后一行生效"的措辞在任意行都准确（解析时
        # 不知道后面还有没有同名行，用结果性描述避开时序问题）。
        if interpreter_lower in seen_interpreters:
            warns.append(
                f"第 {lineno} 行：解释器 [{interpreter_lower}] 出现多次，"
                f"仅最后一行生效"
            )
        seen_interpreters.add(interpreter_lower)

        # ── 落库（警告级行照常进字典）──
        blacklist_dict[interpreter_lower] = deduped

    return blacklist_dict, drops, warns


def formatBlacklistDict(blacklist: dict) -> str:
    """
    用户黑名单字典 → 文本格式序列化器（15 号新增，唯一真相源）。
    供 saveUserBlacklist（写 JSON）与 SettingsPage._loadCustomBlacklist
    （UI 回显）共用——回显的就是实际存储格式，归一化成果（解释器名
    lower、去重）会自然"回写"到用户视野（验收项 B14）。
    """
    lines = []
    for interpreter, keywords in blacklist.items():
        if keywords:  # 只序列化有关键词的解释器（与旧实现等价）
            keywords_str = ", ".join(keywords)
            lines.append(f"[{interpreter}] {keywords_str}")
    return "\n".join(lines)


def loadUserBlacklist():
    """
    从 Global Settings.json 读取用户自定义黑名单（文本格式）。
    返回值：dict，如 {"cmd": ["format", "diskpart"], ...}
    如果配置文件中没有该字段，返回空字典（向后兼容）。

    15 号改造：解析逻辑平移至 parseBlacklistText（单点），本函数
    签名与返回值不变——doCustomCommand 的匹配路径零感知。加载路径
    的丢弃/警告仅控制台 print（本函数可能运行在任意上下文，弹窗
    既不合适也不必要；UI 校验只服务保存路径，定稿"不做清单"第 3 条）。
    但解释器名 lower 归一化在本路径同样生效——真 bug 修复的三条
    路径之一（手改 JSON 写 [CMD] 也能被治愈，验收项 C2）。
    """
    with open(globalSettingspath, "r", encoding="utf-8") as f:
        globalSettings = json.load(f)

    raw_text = globalSettings.get("userBlacklist", "")
    if not raw_text.strip():
        return {}

    blacklist_dict, drops, warns = parseBlacklistText(raw_text)

    # 手改 JSON 的存量脏数据在此现形（仅日志，静默容错现状保留）
    for lineno, reason, raw in drops:
        print(f"[黑名单加载] 第 {lineno} 行无法解析已跳过（{reason}）: {raw}")
    for w in warns:
        print(f"[黑名单加载] 警告: {w}")

    return blacklist_dict


def saveUserBlacklist(blacklist: dict):
    """
    将用户自定义黑名单字典写入 Global Settings.json。

    15 号改造：文本序列化收敛至 formatBlacklistDict（单点）。
    参数：
        blacklist: 字典，如 {"cmd": ["format", "diskpart"], ...}
    """
    with open(globalSettingspath, "r+", encoding="utf-8") as f:
        globalSettings = json.load(f)

        globalSettings["userBlacklist"] = formatBlacklistDict(blacklist)

        # 保存（r+ 写回三件套：seek 归零 → 覆盖写 → truncate 防残留）
        f.seek(0)
        json.dump(globalSettings, f, ensure_ascii=False, indent=2)
        f.truncate()

# ==================== 窗口大小设置管理 ====================

# 默认窗口配置常量，防止旧版本配置文件缺少字段时报错
DEFAULT_WINDOW_SETTINGS = {
    "mainWindow": {"maximized": True, "width": 1000, "height": 800},
    "editWindow": {"maximized": False, "width": 600, "height": 400},
    "searchWindow": {"maximized": False, "width": 600, "height": 600}
}


def loadWindowSettings():
    """从 Global Settings.json 读取窗口大小配置"""
    with open(globalSettingspath, "r", encoding="utf-8") as f:
        globalSettings = json.load(f)

    # 如果配置文件中还没有 windowSettings 字段，直接返回默认值
    if "windowSettings" not in globalSettings:
        return DEFAULT_WINDOW_SETTINGS

    settings = globalSettings["windowSettings"]
    # 安全校验：补全可能缺失的字段，防止旧版本配置导致 KeyError
    for win_key, default_val in DEFAULT_WINDOW_SETTINGS.items():
        if win_key not in settings:
            settings[win_key] = default_val
        else:
            for k, v in default_val.items():
                if k not in settings[win_key]:
                    settings[win_key][k] = v
    return settings


def saveWindowSettings(settings: dict):
    """将窗口大小配置保存到 Global Settings.json"""
    with open(globalSettingspath, "r+", encoding="utf-8") as f:
        globalSettings = json.load(f)
        globalSettings["windowSettings"] = settings
        f.seek(0)
        json.dump(globalSettings, f, ensure_ascii=False, indent=2)
        f.truncate()


def center_window(window, width, height):
    """
    通用工具函数：将窗口居中显示在屏幕上
    参数 window: CTk 或 CTkToplevel 实例
    参数 width, height: 期望的窗口宽高
    """
    # 1. 先更新窗口的内部状态，确保能获取到准确的屏幕尺寸
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    # 2. 计算居中坐标 (左上角坐标)
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2

    # 3. 设置窗口大小和位置 (格式: "宽x高+X坐标+Y坐标")
    window.geometry(f"{width}x{height}+{x}+{y}")

def _ensureBareMinimum():
    """首次运行/配置被删时，补齐最低限度运行条件"""
    configDirectory.mkdir(exist_ok=True)
    if not globalSettingspath.exists():
        saveGlobalSettings({
            "appearanceMode": "暗",
            "windowSettings": DEFAULT_WINDOW_SETTINGS,
            "userBlacklist": "",
        })

_ensureBareMinimum()

