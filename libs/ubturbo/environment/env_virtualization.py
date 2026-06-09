
from typing import List, Dict, Union, Any
from libs.host.linux import Linux
from libs.ubturbo.common import basic
from libs.ubturbo.common import env
import libs.ubturbo.api.virtualization as virtualization
from libs.ubturbo.environment.env_base import Environment


class EnvHugePages(Environment):
    def __init__(self, node2hugepages: Dict[Linux, Dict[int, int]]) -> None:
        """
        准备大页

        使用示例:
            # 将所有节点numa 0~3的大页数都设为4096
            env_hp = HugePagesEnvironment({node: {i: 4096 for i in range(4)} for node in self.nodes})  # 创建对象
            env_hp.prepare()  # 准备环境
            ...  # 用例代码
            env_hp.clean()  # 还原环境

        :param node2hugepages: 待分配大页大小  示例: {节点: {numa编号: 大页数}}
        """
        super().__init__(list(node2hugepages.keys()))
        # 支持直接使用节点作为键 (key: str = get_node_identity result)
        self.node2hugepages: Dict[str, Any] = {
            env.get_node_identity(node): hugepages
            for node, hugepages in node2hugepages.items()
        }

    def _detect_single_node(self, node: Any, *args: Any, **kwargs: Any) -> Any:
        """检测大页情况"""
        return virtualization.numastat_vm(node)

    def prepare_single_node(self, node: Any, *args: Any, **kwargs: Any) -> None:
        """设置大页数"""
        for numa_id, hugepage in self.node2hugepages[env.get_node_identity(node)].items():
            virtualization.set_huge_pages(node, hugepage, numa_index=numa_id)

    def clean_single_node(self, node: Any, *args: Any, **kwargs: Any) -> None:
        """还原大页数"""
        for numa_id in self.node2hugepages[env.get_node_identity(node)]:
            virtualization.set_huge_pages(
                node,
                int(float(self.init_status[env.get_node_identity(node)]['HugePages_Total'][f'Node {numa_id}']) / 2),
                numa_index=numa_id
            )

