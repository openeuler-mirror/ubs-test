# -*- coding: utf-8 -*-
"""OS Reliability utilities stub - to be fully migrated from legacy."""
import json
from typing import Any

from libs.ubturbo.api import docker
from libs.ubturbo.common import basic, json_utils


def ub_graceful_shutdown(node, container_name: str = 'qemu-ub', qmp_port: int = 51000):
    """
      登录指定docker容器，通过qmp方式下电qemu虚机节点
    """
    cmd = f'''sh -c "echo '{{\\"execute\\": \\"qmp_capabilities\\"}}' '{{\\"execute\\": \\"system_powerdown\\"}}' | nc localhost {qmp_port}"'''
    result = docker.exec_out_of_container(node=node, container_name=container_name, cmd=cmd).stdout
    json_list = result.split("\r\n")
    ok = True
    for data in json_list:
        if len(data) == 0:
            continue
        found = json_utils.json_contain(json.loads(data), key="error")
        if found:
            ok = False
            break

    if not ok:
        raise Exception(f"{qmp_port}: 下电失败")


def inject_reboot(node, fault_mock=False, node_list=None):
    basic.run(node, 'reboot -f', returnCode=False, timeout=10)


def inject_panic(node, fault_mock=False, node_list=None):
    basic.run(node, 'echo c > /proc/sysrq-trigger &', returnCode=False, timeout=10)

