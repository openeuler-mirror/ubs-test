"""ATBaseCase - Base class for ubturbo AT test cases.

Migrated from legacy lib/basecase/ATBaseCase.py
Integrated with libs.core.base.TestCase to eliminate duplicate functionality.

CRITICAL: This class NO LONGER has __init__ method.
pytest cannot collect test classes with __init__ (even with default args).

Initialization is handled by fixture injection (@pytest.fixture(autouse=True)).
"""

import logging
import pytest
from typing import Any, Dict, List

from libs.core.base import TestCase
from libs.utils.logger_compat import Log
import libs.ubturbo.AT.at_common as AT_AW

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_at_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入ATBaseCase外部依赖参数.
    
    只对ATBaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.core.basecase.ubturbo.at_basecase import ATBaseCase
    if not isinstance(instance, ATBaseCase):
        return
    
    instance.resource = resource
    instance.customParam = custom_params or {}
    instance.nodes = nodes if nodes else []
    
    instance._init_nodes_aliases()
    
    instance.logger = Log.getLogger(instance.__class__.__name__)
    
    instance.at_aw = AT_AW
    instance.parameters = {}
    instance.testcase_params = instance._parse_custom_params()
    
    logger.info(f"ATBaseCase initialized: {len(instance.nodes)} nodes, class={instance.__class__.__name__}")


class ATBaseCase(TestCase):
    """Base class for ubturbo AT test cases.

    继承 TestCase (libs.core.base.TestCase) 而不是 UniAutos.TestEngine.Case，
    避免与已有的 TestCase 断言方法、日志方法等功能重复。

    节点初始化通过 fixture 注入实现，支持：
    - self.nodes: 节点列表
    - self.node: 单节点
    - self.nodemaster: 主节点
    - self.nodeagent: agent节点
    - self.nodeagent02, self.nodeagent03: 其他agent节点

    节点配置示例：
        1) 4p(2节点):
            host_role=master
            host_role=agent01
        2) 8p(4节点):
            host_role=master
            host_role=agent01
            host_role=agent02
            host_role=agent03

    使用示例：
        basic.run(self.nodes[6], 'ls /')  # 查看第7个节点的"/"目录
    """

    def _init_nodes_aliases(self) -> None:
        """从 self.nodes 初始化节点别名。"""
        if not self.nodes:
            self.node = None
            self.nodemaster = None
            self.nodeagent = None
            self.nodeagent02 = None
            self.nodeagent03 = None
            return

        self.node = self.nodes[0]

        self.nodemaster, self.nodeagent, self.nodeagent02, self.nodeagent03 = [
            self.nodes[index] if index < len(self.nodes) else None for index in range(4)
        ]

    def _parse_custom_params(self) -> Dict[str, str]:
        """解析 customParam 为字典。

        通过 self.customParam 变量，解析用例 xml 中定义的参数为字典。
        本函数实现与 TestCase.getParameter() 类似功能，
        但保留 legacy 签名以兼容已迁移的测试代码。

        :return: 放入所有 name、value 的一个字典
        """
        if isinstance(self.customParam, dict):
            return self.customParam
        elif isinstance(self.customParam, list):
            return {
                item["name"]: item["value"]
                for item in self.customParam
                if "name" in item and "value" in item
            }
        return {}

    def get_params(self) -> Dict[str, str]:
        """Legacy method alias for _parse_custom_params().

        保持与 legacy ATBaseCase.get_params() 方法签名兼容。
        """
        return self._parse_custom_params()