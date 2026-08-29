''' 动作注册表：集中定义所有动作的元数据（标识、显示名称、参数结构） '''
from dataclasses import dataclass, field
from typing import Any, Callable

@dataclass # 定义一个数据类，用于描述单个动作参数的规格
class ParamSpec:
    """描述单个动作参数的规格"""
    key: str # 在 actionParams 字典里的键名
    label: str # 显示给用户的标签 (如 "要粘贴的文本")
    widget: str = "entry" # 控件类型: entry(单行), multiline(多行) 等
    default: Any = "" # 默认值
    required: bool = False # 是否必填
    options: list[str] = field(default_factory=list) # 给 combobox 用的选项列表
    placeholder: str = "" # 单行输入框的灰色提示文字
    # 滑块控件的取值范围
    from_: int = 0
    to: int = 100

@dataclass
class ActionDef:
    """描述一个完整的动作定义"""
    key: str # 动作标识 (存入 JSON 的 action 字段，如 "pasteText")
    displayName: str # 展示名称 (下拉框显示用，如 "粘贴文本")
    params: list[ParamSpec] = field(default_factory=list)
    # 规定 handler 接收一个字典参数
    handler: Callable[[dict, dict | None], None] = None
    # 是否在主快捷键编辑窗的动作下拉框中显示
    show_in_shortcut: bool = True
    # 是否在动作组步骤编辑窗的步骤下拉框中显示
    show_in_action_group: bool = True

    # ==================== 设计26：新增 hint 提示字段 ====================
    # 仅用于在编辑界面提示用户该动作的注意事项，由开发者在注册表里写死。
    # 不写入用户的 JSON 配置文件。UI 层会把它渲染到一个只读的 Textbox 里。
    hint: str = ""
    # =============================================================

# ──────────────── 动作注册表 ────────────────
ACTION_REGISTRY: list[ActionDef] = [
    ActionDef(
        key="",
        displayName="（无动作）",
        params=[],
        hint="不执行任何操作，可用于临时禁用某个快捷键。"
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
        ],
        hint="将指定文本写入剪贴板，并模拟按下 Ctrl+V 进行粘贴。\n支持多行文本和特殊字符。"
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
                placeholder="支持网址、文件夹、文件、程序"
            ),
            ParamSpec(
                key="mode",
                label="打开模式",
                widget="combobox",
                default="系统默认行为",
                options=["系统默认行为", "强制打开新窗口"]
            )
        ],
        hint="智能识别网址或本地路径并调用系统 API 打开。\n如果是网址，默认使用系统默认浏览器打开。"
    ),
    ActionDef(
        key="mediaControl",
        displayName="媒体与音量控制",
        params=[
            ParamSpec(
                key="action",
                label="控制操作",
                widget="combobox",
                default="播放/暂停",
                options=["播放/暂停", "上一首", "下一首", "音量加", "音量减", "静音"]
            )
        ],
        hint="模拟按下多媒体控制键，适用于大多数音乐播放器和系统音量控制。"
    ),
    ActionDef(
        key="insertDateTime",
        displayName="插入日期时间",
        params=[
            ParamSpec(
                key="format",
                label="时间格式",
                widget="entry",
                default="%Y-%m-%d %H:%M:%S",
                required=True,
                placeholder="例: %Y年%m月%d日 %H:%M:%S"
            )
        ],
        hint="按指定格式插入当前时间，通过模拟键盘输入实现。\n格式参考 Python 官方文档：time.strftime 格式化指令:\nhttps://docs.python.org/zh-cn/3/library/time.html#time.strftime"
    ),
    ActionDef(
        key="customCommand",
        displayName="执行自定义命令",
        params=[
            ParamSpec(
                key="command",
                label="命令语句",
                widget="multiline",
                default="",
                required=True,
                placeholder="如: ping baidu.com 或 echo hello"
            ),
            ParamSpec(
                key="interpreterType",
                label="解释器类型",
                widget="combobox",
                options=["cmd", "powershell", "python"],
                default="cmd",
                required=True
            ),
            ParamSpec(
                key="executablePath",
                label="执行程序绝对路径",
                widget="entry",
                default=r"C:\Windows\System32\cmd.exe",
                required=True,
                placeholder=r"PowerShell默认: C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            ),
            ParamSpec(
                key="execMode",
                label="执行模式",
                widget="combobox",
                options=["后台静默执行", "弹出终端并保持", "弹出终端执行后关闭"],
                default="后台静默执行"
            ),
            ParamSpec(
                key="workingDir",
                label="工作目录",
                widget="entry",
                default="",
                required=True,
                placeholder="必填，须为有效的绝对路径"
            ),
            ParamSpec(
                key="needConfirm",
                label="执行前需要确认",
                widget="checkbox",
                default=True
            )
        ],
        hint="面向开发者的快捷终端入口，目前仅支持 cmd/powershell/python。\n参数多，记得往下滑\n解释器类型与.exe的名字不符会拒绝执行\n系统自带PowerShell默认位置: C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\n安全机制：执行前会依次经过 强制黑名单 -> 用户自定义黑名单 -> 常规确认 三层拦截。\n注意：工作目录必须填写有效路径，否则拒绝执行。\n命中黑名单的命令无论如何都会被拦截，然后弹窗询问或直接拒绝执行。"
    ),
    ActionDef(
        key="mouseMoveTo",
        displayName="鼠标-移动到指定坐标",
        params=[
            ParamSpec(key="x", label="X 坐标", widget="entry", required=True, placeholder="左上角为原点,x向右y向下为正,支持负数"),
            ParamSpec(key="y", label="Y 坐标", widget="entry", required=True, placeholder="左上角为原点,x向右y向下为正,支持负数"),
            ParamSpec(key="duration", label="平滑耗时(秒,0为瞬移)", widget="entry", default="0", placeholder="如填0.3表示用0.3秒匀速移动过去")
        ],
        hint="移动后的点击请用鼠标-模拟点击动作。\n负数坐标适用于多显示器环境"
    ),
    ActionDef(
        key="mouseMoveStep",
        displayName="鼠标-步进移动(微调)",
        params=[
            ParamSpec(key="direction", label="方向", widget="combobox", options=["上", "下", "左", "右"], default="右"),
            ParamSpec(key="distance", label="步进距离(像素)", widget="slider", default=50, from_=1, to=500)
        ],
        hint="相对当前位置移动指定像素，适合微调鼠标位置。\n负数坐标适用于多显示器环境"
    ),
    ActionDef(
        key="mouseClick",
        displayName="鼠标-模拟点击",
        params=[
            ParamSpec(key="button", label="按键", widget="combobox", options=["左键", "右键", "中键", "侧键前进", "侧键后退"], default="左键"),
            ParamSpec(key="count", label="次数", widget="combobox", options=["单击", "双击"], default="单击"),
            ParamSpec(key="moveToFirst", label="点击前是否移动到坐标?", widget="checkbox", default=False),
            ParamSpec(key="x", label="X 坐标", widget="entry", placeholder="左上角为原点,x向右y向下为正,支持负数"),
            ParamSpec(key="y", label="Y 坐标", widget="entry", placeholder="左上角为原点,x向右y向下为正,支持负数")
        ],
        hint="若勾选了'点击前移动'，请确保填写了有效的坐标,移动采用瞬移方式。\n负数坐标适用于多显示器环境"
    ),
    ActionDef(
        key="mouseScroll",
        displayName="鼠标-滚轮滚动",
        params=[
            ParamSpec(key="direction", label="方向", widget="combobox", options=["向上", "向下"], default="向上"),
            ParamSpec(key="amount", label="滚动量(格)", widget="entry", default="3", required=True)
        ],
        hint="模拟鼠标滚轮滚动指定格数。"
    ),
    ActionDef(
        key="mouseDrag",
        displayName="鼠标-拖拽",
        params=[
            ParamSpec(key="startX", label="起点 X", widget="entry", required=True, placeholder="左上角为原点,x向右y向下为正,支持负数"),
            ParamSpec(key="startY", label="起点 Y", widget="entry", required=True, placeholder="左上角为原点,x向右y向下为正,支持负数"),
            ParamSpec(key="endX", label="终点 X", widget="entry", required=True, placeholder="左上角为原点,x向右y向下为正,支持负数"),
            ParamSpec(key="endY", label="终点 Y", widget="entry", required=True, placeholder="左上角为原点,x向右y向下为正,支持负数")
        ],
        hint="模拟按住左键从起点拖拽到终点后松开。\n负数坐标适用于多显示器环境"
    ),
    # ==================== 新增：键盘-模拟按键（仅动作组内可选） ====================
    # 定位说明：
    #   本动作是"动作组"的补充件，不是独立快捷键动作。
    #   设为 show_in_shortcut=False 后，主编辑窗下拉框(getAllActionDisplayNames)
    #   自动过滤掉它；show_in_action_group=True 让动作组编辑窗(_getAvailableActions)
    #   自动放行。两处过滤均零 UI 改动，纯数据驱动生效。
    ActionDef(
        key="simulateKeys",
        displayName="键盘-模拟按键",  # 与"鼠标-xxx"系列命名风格保持一致
        params=[
            ParamSpec(
                key="keys",
                label="按键组合",
                widget="entry",
                default="",
                required=True,
                placeholder="如: ctrl+shift+s 、ctrl+alt+="
            )
        ],
        show_in_shortcut=False,  # 【关键】主快捷键编辑窗不显示
        show_in_action_group=True,  # 【关键】仅在动作组步骤下拉框中可选
        hint=(
            "模拟按键：向当前活动窗口发送【单个】按键组合，仅动作组内可用。\n"
            "• 写法：多个键用 + 连接，如 ctrl+s、shift+f5、ctrl+numpad_divide。键名口径与方案备注里的快捷键录入规则完全一致\n"
            "• ⚠ 保存时不做格式校验，错误要到运行时才暴露，共有两条反馈路径：▶ 试运行：日志当场指出错在哪个键、该怎么写；正式执行：失败和报错会汇入执行结束的「动作组执行报告」弹窗。\n"
            "• 连发多组：复制本步骤后改键名即可，节奏靠每步的「步骤间延迟」控制。关键落点前建议留 300～500ms，给目标程序留反应时间，太快会被吃键。\n"
            "• 输入法：字母键可能被接管变成候选词，指令型组合（ctrl+s、f5 等）一般不受影响；大段文字请用「粘贴文本」（走剪贴板，不经输入法）。需要临时切输入法时用配方：切输入法键 → 步骤延迟300ms → 本动作 → 切回来。\n"
            "• 向管理员权限的程序发送可能无效。\n"
            "• 每次发送前会自动释放你物理按住的 Ctrl/Shift/Alt（Win 键除外），避免模拟出来的组合被残留修饰键污染"
        )
    ),
    # =============================================================================

    # ==================== 设计25：拆分操作软件自身动作 ====================
    ActionDef(
        key="appControl",
        displayName="操作软件自身",
        params=[
            ParamSpec(
                key="command",
                label="控制指令",
                widget="combobox",
                # 移除了 "启用指定方案" 选项，该功能已独立为 switchScheme
                options=[
                    "显示主窗口",
                    "隐藏主窗口",
                    "刷新执行器",
                    "退出软件",
                    "切换到上一个方案",
                    "切换到下一个方案",
                ],
                default="显示主窗口",
                required=True
            )
            # 移除了 targetSchemeSelect 和 targetSchemeManual
        ],
        show_in_action_group=False, # 【关键】禁止在动作组中使用！防止宏执行一半把自己杀了或切了方案导致状态崩溃
        hint="用于通过快捷键控制软件本身，形成闭环。\n注意：包含退出软件、切换方案等危险操作，建议建立一个专门的'全局控制'方案来存放这些快捷键。\n切换方案是意思是按排名的顺序切换到下一个/上一个启用方案\n记得在要启用的方案那里设置好同样的切换启用功能，否则自己容易犯懵\n如果想直接切换到指定方案，请使用独立的'切换启用方案'动作。\n推荐自己建一个专门的启用指定快捷键方案的方案来切换方案。"
    ),
    # =================================================================

    ActionDef(
        key="appControlSafe",
        displayName="操作软件自身(安全版)",
        params=[
            ParamSpec(
                key="command",
                label="控制指令",
                widget="combobox",
                options=[
                    "显示主窗口",
                    "隐藏主窗口",
                    "刷新执行器"
                ],
                default="显示主窗口",
                required=True
            )
        ],
        show_in_shortcut=False, # 【关键】主界面不需要看到它，它是动作组的专属辅助动作
        hint="仅供动作组使用：仅包含显隐窗口、刷新执行器等安全指令，防止宏执行期间意外退出或切方案。"
    ),

    # ==================== 设计25：新增独立的切换方案动作 ====================
    ActionDef(
        key="switchScheme",
        displayName="切换启用方案",
        params=[
            ParamSpec(
                key="targetSchemeSelect",
                label="目标方案\n(下拉选择)",
                widget="dynamic_combobox_schemes", # 特殊控件，UI 层会动态注入方案名列表
                default="",
                required=False
            )
            # 移除了 targetSchemeManual，简化为单一下拉框，选择“（无）”即禁用所有方案
        ],
        show_in_action_group=False, # 同样禁止在动作组中使用，防止状态崩溃
        hint="用于通过快捷键一键转跳启用其他快捷键方案。\n下拉框中的“（无）”选项代表禁用所有方案。\n启用新方案会自动禁用其他所有方案。\n推荐自己建一个专门的启用指定快捷键方案的方案来切换方案。"
    ),
    # =================================================================

    ActionDef(
        key="actionGroup",
        displayName="动作组",
        params=[
            ParamSpec(
                key="stopOnError",
                label="单步失败时",
                widget="combobox",
                options=["停止整个动作组", "跳过当前步继续"],
                default="停止整个动作组",
                required=True
            ),
            ParamSpec(
                key="loopCount",
                label="循环执行次数",
                widget="entry",
                default="1",
                required=True
            ),
            ParamSpec(
                key="maxExecutionTime",
                label="总超时限制(秒)",
                widget="entry",
                default="60",
                required=True
            ),
            ParamSpec(
                key="confirmAllAtOnce",
                label="执行前统一确认危险命令",
                widget="checkbox",
                default=False
            )
        ],
        show_in_action_group=False,
        hint="按顺序执行多个步骤，支持循环、超时限制和平滑/强制停止。\n适合处理包含键盘+鼠标+等待的复杂重复性任务。\n平滑停止的意思是，执行完当前步骤才停止。\n在执行包含模拟按键的动作组时，如果想停止，推荐到托盘或设置界面点击停止按钮，模拟按键执行前后会清空你当前物理按下的键的记录防止污染\n延迟的意思是，在执行完步骤后的等待时间。\n注意：动作组执行期间，软件会被锁定为忙碌状态，禁止切换方案或执行其他快捷键。\n单次执行最多50步，不可改；超时最长可以设置120秒\n限制时间和步数除了防止宏执行过程中出现死循环或无限等待，还防止用户设计过于复杂的操作，这不是快捷键该干的事\n执行前统一确认针对的是执行自定义命令动作的确认。\n命中黑名单的自定义命令无论如何都会被拦截，然后弹窗询问或直接拒绝执行\n由于切换动作类型会清空原参数，为避免绕过必填参数限制，步骤会自动转为禁用状态。\n试运行期间全局快捷键仍在监听，模拟按键可能触发其他快捷键。试运行中两条停止组合键均等效于强制停止；也可以点编辑窗里同一个按钮（此时▶应该变成了⏹）停止。"
    )
]

# 方便快速查询的映射字典
_ACTION_MAP_BY_KEY: dict[str, ActionDef] = {a.key: a for a in ACTION_REGISTRY}
_ACTION_MAP_BY_NAME: dict[str, ActionDef] = {a.displayName: a for a in ACTION_REGISTRY}


def getAllActionDisplayNames() -> list[str]:
    """获取所有在主快捷键编辑窗中显示的动作展示名称，用于填充下拉框"""
    return [a.displayName for a in ACTION_REGISTRY if a.show_in_shortcut]


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
