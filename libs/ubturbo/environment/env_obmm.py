
from typing import Any, Dict, Optional
from libs.host.linux import Linux
from libs.ubturbo.common import env
from libs.ubturbo.common import basic
import libs.ubturbo.api.system as system
from libs.ubturbo.environment.env_base import Environment


class EnvObmm(Environment):
    def __init__(self, node2insmod_args: Dict[Linux, str]) -> None:
        """
        强制重插obmm ko
        还原环境时, 插入obmm ko时不使用参数, 因为目前无法获取初始环境中插入的参数
        :param node2insmod_args: 传入字典: {节点: 插入参数}
        """
        super().__init__(list(node2insmod_args.keys()))
        self.node2insmod_args = {
            env.get_node_identity(node): insmod_args
            for node, insmod_args in node2insmod_args.items()
        }

    def _detect_single_node(self, node: Any, *args: Any, **kwargs: Any) -> Any:
        """
        仅检测是否已插入OBMM，暂无检测不同插入参数的方法
        :param node:
        :return: 初始是否插入obmm ko
        """
        return basic.run(node, 'lsmod | grep obmm').rc == 0

    def prepare_single_node(self, node: Any, *args: Any, **kwargs: Any) -> None:
        """
        确保插入obmm ko
        :param node:
        :return:
        """
        data = self.init_status[env.get_node_identity(node)]
        if data:
            system.rmmod(node, 'obmm.ko')
        system.insmod(
            node,
            '/lib/modules/$(uname -r)/obmm/obmm.ko',
            self.node2insmod_args[env.get_node_identity(node)]
        )

    def clean_single_node(self, node: Any, init_status: bool, insmod_args: Optional[str] = None, *args: Any, **kwargs: Any) -> None:
        """
        还原单个节点obmm ko状态
        :param node:
        :param init_status:
        :param insmod_args:
        :return:
        """
        system.rmmod(node, 'obmm.ko')
        if init_status:
            system.insmod(node, '/lib/modules/$(uname -r)/obmm/obmm.ko', insmod_args or "")

    def clean(self, insmod_args: Optional[str] = None) -> None:
        """
        还原obmm ko状态
        :param insmod_args:
        :return:
        """
        for node in self.nodes:
            self.clean_single_node(node, self.init_status[env.get_node_identity(node)], insmod_args=insmod_args)

