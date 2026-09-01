'''项目目录解析'''
'''
历史上 configManager 与 shortcutUtils 各持一份路径定义（因循环导入），
frozen 重定向只加在了 configManager 一侧，导致打包后 shortcutUtils 的
configDirectory 指向 _internal/config。本模块不导入任何项目内模块，
供双方安全共享，从根源上消除循环导入与副本漂移。
'''
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # 打包后：exe 所在目录就是项目根（config 与 exe 并排）。
    # 用 sys.executable 而非 __file__：onedir 模式代码在 _internal/ 里，
    # __file__ 指向那里，exe 在上一层。
    proJectrootDirectory = Path(sys.executable).resolve().parent
else:
    # 开发环境：core/ 的上一级就是项目根
    proJectrootDirectory = Path(__file__).resolve().parent.parent
