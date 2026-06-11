from typing import List, Any
from libs.host.linux import Linux
from libs.ubturbo.common import env
from libs.ubturbo.common import basic
import libs.ubturbo.api.system as system
from libs.ubturbo.environment.env_base import Environment

smap_config_path = '/dev/shm/smap_config'


class EnvStandardSmap(Environment):
    """
    以标准参数重插smap ko，不做清除
    删除/dev/shm/smap_config文件，确保后续用户均能调用成功
    """
    def prepare_single_node(self, node: Any, *args: Any, **kwargs: Any) -> Any:
        """
        1. 依次停止osturbo、rack以及残余的smap-cli进程，确保ko可以移除
        2. 删除/dev/shm/smap_config文件，确保后续用户均能调用成功
        3. 重插smap ko
            rmmod smap_tiering.ko
            rmmod access-tracking.ko
            rmmod hist-tracking.ko
            rmmod tracking-core.ko

            insmod tracking-core.ko
            insmod access-tracking.ko
            insmod hist-tracking.ko
            insmod smap_tiering.ko node_modes=5,5,5,5,5,5
        :param node:
        :param args:
        :param kwargs:
        :return:
        """
        env_type = env.get_env_type(node)
        services = ['osturbo-daemon.service', 'scbus-daemon.service']
        kos = ['smap_tiering.ko', 'hist-tracking.ko', 'access-tracking.ko', 'tracking-core.ko']  # 按卸载顺序排列
        ko_parameters = {
            'tracking-core.ko': [],
            'access-tracking.ko': [],
            'hist-tracking.ko': [],
            'smap_tiering.ko': ['node_modes=5,5,5,5,5,5']
        }
        if env_type == env.UB_simulation:  # UB仿真需要额外参数
            ko_parameters['access-tracking.ko'].append('smap_scene=2')
            ko_parameters['smap_tiering.ko'].append('smap_scene=2')
            ko_parameters['hist-tracking.ko'].append('smap_scene=2')
        basic.logger.info('停止osturbo、rack服务以及残余的smap-cli进程')
        basic.run(node, "killall smap_client")
        for service in services:
            basic.run(
                node,
                f'systemctl stop {service}',
                timeout={
                    env.UB_simulation: 10 * 60
                }.get(env_type, 3 * 60),
            )
            res = basic.run(node, f'systemctl status {service} --no-pager')
            if 'Active:' not in res.output:
                raise Exception('回显字段异常，服务停止可能超时')
            if 'Active: active (running)' in res.output:
                raise Exception('服务未停止')

        basic.logger.info('删除smap_config配置文件')
        system.rm(node, smap_config_path)

        basic.logger.info('重插smap ko')
        for ko in kos:
            system.rmmod(node, ko)

        basic.run(node, 'cd /lib/modules/smap')
        for ko in reversed(kos):
            params = ko_parameters.get(ko, [])
            system.insmod(node, ko, *params)

        # 还原路径
        basic.run(node, 'cd -')