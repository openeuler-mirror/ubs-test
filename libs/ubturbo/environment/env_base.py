
from typing import Any
from libs.ubturbo.common import env


class Environment:
    def __init__(self, nodes: list):
        """
        环境准备接口,减少环境准备部分重复代码,提升编码效率

        工作过程:
            1. 检测环境初始状态
                将环境信息存储在self.init_status字典中: {节点id: 信息}
                # 节点id可以通过lib.common.env.get_node_identity(节点对象)来获取
            2. 准备环境
                更改环境配置
            3. 还原环境
                根据self.init_status中的信息还原环境

        如何编写接口:
            每个节点准备步骤:
                1.一样, 实现: _detect_single_node, prepare_single_node, clean_single_node
                2.不同, 实现: _detect, prepare(需要在prepare内运行_detect), clean

        使用示例:
            env = XXXEnv(环境参数)  # 创建对象
            env.prepare()  # 准备环境
            ...  # 运行用例
            env.clean()  # 还原环境

        :param nodes: 待处理节点列表
        """
        self.init_status = {}
        self.nodes = nodes

    def _detect_single_node(self, node, *args, **kwargs) -> Any:
        """
        检测单个节点状态
        :param node:
        :return: 节点状态, 将被作为环境初始值, 储存在self.init_status[节点id]中
        """

    def prepare_single_node(self, node, *args, **kwargs) -> Any:
        """
        准备单个节点的环境
        :param node:
        :return:
        """

    def clean_single_node(self, node, init_status, *args, **kwargs) -> Any:
        """
        还原单个节点的环境, 可以使用self.init_status的值
        :param node:
        :param init_status: 传入节点对应初始状态，用于恢复环境
        :return:
        """

    def _detect(self, *args, **kwargs):
        """
        对每个节点进行检测, 将结果放入self.init_status中
        :param args:
        :param kwargs:
        :return:
        """
        for node in self.nodes:
            self.init_status[env.get_node_identity(node)] = self._detect_single_node(node)

    def prepare(self, *args, **kwargs):
        """
        对每个节点进行环境准备
        :param args:
        :param kwargs:
        :return:
        """
        self._detect()
        for node in self.nodes:
            self.prepare_single_node(node)

    def clean(self, *args, **kwargs):
        """
        还原每个节点
        :param args:
        :param kwargs:
        :return:
        """
        for node in self.nodes:
            self.clean_single_node(node, self.init_status[env.get_node_identity(node)])
