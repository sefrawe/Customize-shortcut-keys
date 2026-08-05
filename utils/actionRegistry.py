''' 动作注册表：集中定义所有动作的元数据（标识、显示名称、参数结构） '''

from dataclasses import dataclass, field
from typing import Any

@dataclass # 定义一个数据类，用于描述单个动作参数的规格
class ParamSpec:
    """描述单个动作参数的规格"""
    key: str                  # 在 actionParams 字典里的键名
    label: str                # 显示给用户的标签 (如 "要粘贴的文本")
    widget: str = "entry"     # 控件类型: entry(单行), multiline(多行) 等
    default: Any = ""         # 默认值
    required: bool = False    # 是否必填

@dataclass
class ActionDef:
    """描述一个完整的动作定义"""
    key: str                  # 动作标识 (存入 JSON 的 action 字段，如 "pasteText")
    displayName: str          # 展示名称 (下拉框显示用，如 "粘贴文本")
    params: list[ParamSpec] = field(default_factory=list)

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
