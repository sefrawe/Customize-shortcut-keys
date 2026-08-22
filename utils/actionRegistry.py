''' 动作注册表：集中定义所有动作的元数据（标识、显示名称、参数结构） '''

from dataclasses import dataclass, field
from typing import Any, Callable

@dataclass # 定义一个数据类，用于描述单个动作参数的规格
class ParamSpec:
    """描述单个动作参数的规格"""
    key: str                  # 在 actionParams 字典里的键名
    label: str                # 显示给用户的标签 (如 "要粘贴的文本")
    widget: str = "entry"     # 控件类型: entry(单行), multiline(多行) 等
    default: Any = ""         # 默认值
    required: bool = False    # 是否必填
    options: list[str] = field(default_factory=list)  # 给 combobox 用的选项列表
    placeholder: str = ""  #  单行输入框的灰色提示文字


@dataclass
class ActionDef:
    """描述一个完整的动作定义"""
    key: str                  # 动作标识 (存入 JSON 的 action 字段，如 "pasteText")
    displayName: str          # 展示名称 (下拉框显示用，如 "粘贴文本")
    params: list[ParamSpec] = field(default_factory=list)

    # 规定 handler 接收一个字典参数 (actionParams)
    handler: Callable[[dict], None] = None

# ──────────────── 动作注册表 ────────────────
# 目前只包含“无动作”和“粘贴文本”，未来扩展只需在这里追加
ACTION_REGISTRY: list[ActionDef] = [
    ActionDef(
        key="",
        displayName="（无动作）",
        params=[]
    ),

    ActionDef(
        key="pasteText",
        displayName="粘贴文本",
        params=[
            ParamSpec(
                key="text",
                label="要粘贴的文本",
                widget="multiline",
                default="",
                required=True
            )
        ]
    ),

    ActionDef(
        key="openPath",
        displayName="打开路径/网址",
        params=[
            ParamSpec(
                key="path",
                label="目标路径",
                widget="entry",
                default="",
                required=True,
                placeholder="支持网址、文件夹、文件、程序"  # ★ 增加提示 ★
            ),
            ParamSpec(
                key="mode",
                label="打开模式",
                widget="combobox",  # ★ 使用下拉框 ★
                default="系统默认行为",
                options=["系统默认行为", "强制打开新窗口"]
            )
        ]
    )
]

# 方便快速查询的映射字典
_ACTION_MAP_BY_KEY: dict[str, ActionDef] = {a.key: a for a in ACTION_REGISTRY}
_ACTION_MAP_BY_NAME: dict[str, ActionDef] = {a.displayName: a for a in ACTION_REGISTRY}
# print的结果是
# {'': ActionDef(key='', displayName='（无动作）', params=[]), 'pasteText': ActionDef(key='pasteText', displayName='粘贴文本', params=[ParamSpec(key='text', label='要粘贴的文本', widget='multiline', default='', required=True)])}
# {'（无动作）': ActionDef(key='', displayName='（无动作）', params=[]), '粘贴文本': ActionDef(key='pasteText', displayName='粘贴文本', params=[ParamSpec(key='text', label='要粘贴的文本', widget='multiline', default='', required=True)])}

def getAllActionDisplayNames() -> list[str]:
    """获取所有动作的展示名称，用于填充下拉框"""
    return [a.displayName for a in ACTION_REGISTRY]

def getActionDefByKey(key: str) -> ActionDef | None:
    """根据动作标识获取动作定义"""
    return _ACTION_MAP_BY_KEY.get(key)

def getActionDefByDisplayName(displayName: str) -> ActionDef | None:
    """根据展示名称获取动作定义"""
    return _ACTION_MAP_BY_NAME.get(displayName)

def registerActionHandler(key: str, handler: Callable[[dict], None]):
    """将执行函数绑定到注册表对应的 ActionDef 上"""
    actionDef = getActionDefByKey(key)
    if actionDef:
        actionDef.handler = handler

# print结果是
# ['（无动作）', '粘贴文本']
# ActionDef(key='pasteText', displayName='粘贴文本', params=[ParamSpec(key='text', label='要粘贴的文本', widget='multiline', default='', required=True)])
# ActionDef(key='pasteText', displayName='粘贴文本', params=[ParamSpec(key='text', label='要粘贴的文本', widget='multiline', default='', required=True)])

# if __name__ == "__main__":
#     print(_ACTION_MAP_BY_KEY)
#     print(_ACTION_MAP_BY_NAME)
#     print(getAllActionDisplayNames())
#     print(getActionDefByKey("pasteText"))
#     print(getActionDefByDisplayName("粘贴文本"))
