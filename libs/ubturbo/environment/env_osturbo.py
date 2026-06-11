from typing import List, Any
from libs.host.linux import Linux
from libs.ubturbo.common import env
from libs.ubturbo.common import basic
import libs.ubturbo.api.system as system
from libs.ubturbo.environment.env_base import Environment


class EnvOSTurbo(Environment):
    """
    确保安装OSTurbo 清理时不卸载
    """
    def prepare_single_node(self, node: Any, *args: Any, **kwargs: Any) -> Any:
        """

        :param node:
        :param args:
        :param kwargs:
        :return:
        """
        basic.logger.info('检查环境')
        if basic.run(node, 'rpm -qa | grep audit-devel').rc:
            system.yum_install(node, 'audit-devel')
        basic.run(node, 'rpm -qa | grep audit-devel')
        basic.run(node, 'lsmod | grep smap')

        basic.logger.info('安装OSTurbo')
        system.yum_install(node, 'osturbo-daemon')

        basic.logger.info('检查是否安装成功')
        if basic.run(node, 'rpm -qa | grep osturbo').rc:
            raise Exception('OSTurbo安装失败')

        basic.logger.info('启动OSTurbo服务')
        basic.run(node, 'systemctl start osturbo-daemon.service')
        basic.run(node, 'systemctl status osturbo-daemon')

