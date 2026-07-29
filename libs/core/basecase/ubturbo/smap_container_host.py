#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import re
from datetime import datetime, timezone
from enum import Enum
from typing import List

from libs.core.basecase.ubturbo.smap_node_executor import SmapNodeExecutor


class ContainerStatus(Enum):
    CREATED = 0
    RESTARTING = 1
    RUNNING = 2
    REMOVING = 3
    PAUSED = 4
    EXITED = 5
    DEAD = 6
    STOPPED = 7


class ContainerNode(SmapNodeExecutor):

    def __init__(self, host_node: SmapNodeExecutor, ssh_host, container_name: str, install_path):
        super().__init__(ssh_host)
        self._host_node = host_node
        self._name = container_name
        self._bound_numa_nodes = []
        self._container_ip = ""
        self._container_status_dic = {
            "created": ContainerStatus.CREATED,
            "restarting": ContainerStatus.RESTARTING,
            "running": ContainerStatus.RUNNING,
            "removing": ContainerStatus.REMOVING,
            "paused": ContainerStatus.PAUSED,
            "exited": ContainerStatus.EXITED,
            "dead": ContainerStatus.DEAD,
        }
        self._install_path = install_path

    def run(self, cmd: str, timeout=180, work_dir: str = ""):
        container_command = f"docker exec {self._name} bash -c \"{cmd}\""
        return self._ssh_host.run({"command": [container_command], "timeout": timeout, "directory": f"{work_dir}"})

    def check_container_running_status(self) -> bool:
        return self._get_container_status() == ContainerStatus.RUNNING

    def check_container_real_status(self) -> bool:
        # 能进入虚拟机执行ip a命令
        result = self.run("ip a")
        return self._container_ip in self._get_stdout(result)

    def _get_container_status(self) -> ContainerStatus:
        output = self._host_node.run(f"docker inspect --format '{{{{ .State.Status }}}}' {self._name}")
        if self._get_rc(output) == 0:
            match = re.search(rf'(\S+)', self._get_stdout(output))
            if match:
                return self._container_status_dic[match.group(1)]
        return ContainerStatus.STOPPED

    def get_container_ip(self) -> str:
        if self._container_ip == "":
            return self._get_container_control_ip()
        return self._container_ip

    def _get_container_control_ip(self) -> str:
        output = self._host_node.run(f"docker inspect --format '{{{{ .NetworkSettings.IPAddress }}}}' {self._name}")
        if self._get_rc(output) != 0:
            raise RuntimeError("Failed to get container ip!")
        match = re.search(r'(\d{1,3}\.){3}\d{1,3}', self._get_stdout(output))
        if match is not None:
            ip = match.group(0)
            ip_available = self._host_node.ping_ip(ip)
            if ip_available:
                self._container_ip = ip
                return ip
        raise RuntimeError("Failed to get container ip!")


class SmapContainerNode(ContainerNode):
    def __init__(self, host_node: SmapNodeExecutor, ssh_host, container_name: str, install_path):
        super().__init__(host_node, ssh_host, container_name, install_path)
        self._redis_path = f"{install_path}/redis"
        self.redis_result_log = ""

    @staticmethod
    def _get_time_string() -> str:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H:%M:%S")

    def start_redis_with_numa_nodes(self, numa_nodes: List[int], port: int) -> bool:
        """
        根据numa_id 启动redis-server进程，redis-server绑定 numa id 对应的cpu
        :param numa_nodes: 绑定的numa_id，没有则认为不绑定cpu
        :param port: redis server端口号
        """
        if not self.copy_file(f"{self._redis_path}/redis.conf", f"/tmp/redis_{port}.conf"):
            return False
        if not self.__update_config_item(f"/tmp/redis_{port}.conf", "bind", "0.0.0.0", " "):
            return False
        if not self.__update_config_item(f"/tmp/redis_{port}.conf", "port", f"{port}", " "):
            return False
        cmd_prefix = ""
        if len(numa_nodes) != 0:
            cpu_list = self._host_node.get_cpu_list(numa_nodes)
            if len(cpu_list) == 0:
                raise RuntimeError("There are no CPUs available")
            cmd_prefix = "taskset -c " + ','.join(list(map(lambda _: str(_), cpu_list)))
        redis_log = f"/tmp/redis_{port}" + datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H:%M:%S") + ".log"
        output = self.run(
            f"{cmd_prefix} {self._redis_path}/redis-server /tmp/redis_{port}.conf >> {redis_log} 2>&1 & disown")
        return self._get_rc(output) == 0

    def __update_config_item(self, config_path: str, config_key: str, new_value: str, separator: str) -> bool:
        """
        修改key:value格式的配置文件
        """
        return self.change_config_line(config_path, config_key, f"{config_key}{separator}{new_value}", separator)