"""pytest configuration for pvm test package.

遵循框架惯例：basecase 模块内定义 PvmBaseCase 与 inject fixture，
本文件只做 import 导出，使 pvm 下的用例可用。
"""
from libs.modules.pvm.basecase.pvm_basecase import (
    inject_pvm_basecase_dependencies,
)

__all__ = [
    "inject_pvm_basecase_dependencies",
]
