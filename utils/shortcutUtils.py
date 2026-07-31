'''
快捷键相关工具
'''
import json
from pathlib import Path

def theNumberOfTargetFilesInTheFolder(folderPath):
    """统计文件夹中快捷键方案文件的数量（排除软件配置文件和无法解析的文件）"""
    folder = Path(folderPath)
    if not folder.exists() or not folder.is_dir():
        return 0
    count = 0
    for f in folder.iterdir():
        if not f.is_file():
            continue
        if f.suffix != ".json":#检查文件的后缀名是否为 ".json"，如果不是，则跳过该文件，继续下一个文件的处理。
            continue
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            # 快捷键方案的标志性特征：顶层有 "profiles" 键
            if isinstance(data, dict) and "profiles" in data:#检查解析后的数据是否为字典类型，并且是否包含 "profiles" 键，如果满足条件，则认为该文件是一个有效的快捷键方案文件，计数器加1。
                count += 1
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 跳过无法解析的文件
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
            if isinstance(data, dict) and "profiles" in data:
                # 顺便把方案名也取出来，方便后续直接用
                schemeName = data.get("settings", {}).get("name", f.stem)#获取方案名，如果配置文件中没有设置方案名，则使用文件名（不带扩展名）作为方案名。
                schemes.append({
                    # "filePath": f,#暂时不需要文件路径，后续如果需要再加上
                    "name": schemeName
                })
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return schemes

# 快捷键方案文件数量: 2
# 快捷键方案列表: [{'name': '测试快捷键方案'}, {'name': '测试快捷键方案2'}]
