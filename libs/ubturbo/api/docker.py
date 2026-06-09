#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

from typing import Dict, List
import json
from libs.ubturbo.common import string_utils
from libs.ubturbo.common import basic
import libs.ubturbo.api.ssh as ssh


def start_service(node):
    basic.run(node, 'systemctl start docker')


def load_image(node, path_image):
    """加载本地镜像"""
    basic.run(node, f'docker load < {path_image}')


def get_all_images(node):
    """获取所有镜像名"""
    stdout = basic.run(node, 'docker images').stdout
    tb = string_utils.get_table_content(stdout, slice(1, None), slice(0, 1))
    names = [i[0] for i in tb]
    return names


def get_all_containers(node) -> List[Dict[str, str]]:
    """
    获取所有的容器信息
    通过--format参数降低解析难度
    docker ps -a --format "{{json .}}"

    参数：
        ID      容器ID
        Names   容器名
        Image   镜像ID
        Ports   端口映射
    其他参数：
        ['Command', 'CreatedAt', 'Labels', 'LocalVolumes', 'Mounts', 'Networks', 'RunningFor', 'Size', 'Status']

    :param node:
    :return: 示例：[{'ID': '6e34bae37561', ...}, ...]
    """
    res = basic.run(node, 'docker ps -a --format "{{json .}}"')
    content = []
    for line in res.stdout.splitlines():
        if line:
            content.append(json.loads(line))
    return content


def create_container(node, image_name, container_name=None, arg: str = '-d') -> str:
    """
    生成并运行容器
    :param node:
    :param image_name: 镜像名
    :param container_name: 指定容器名
    :param arg: 命令行参数
    :return: 容器id
    """
    if container_name:
        arg = f'--name {container_name} ' + arg
    res = basic.run(node, f'docker run -itd {arg} {image_name} tail -f /dev/null')
    return res.stdout


def start_container(node, container_id: str):
    """
    启动容器
    :param node:
    :param container_id:
    :return:
    """
    return basic.run(node, f'docker start {container_id}')


def stop_container(node, container_id):
    """
    关闭容器
    :param node:
    :param container_id:
    :return:
    """
    return basic.run(node, f'docker stop {container_id}', timeout=60 * 3)


def remove_container(node, container_id):
    """
    关闭容器
    :param node:
    :param container_id:
    :return:
    """
    return basic.run(node, f'docker rm {container_id}', timeout=60 * 3)


def execute_in_container(node, container_id: str, cmd: str, cmd_arg: str = None, **kwargs) -> basic.Result:
    """
    容器执行一行命令
    :param node:
    :param container_id: 容器id
    :param cmd: 待运行命令
    :param cmd_arg: 其他参数
    :return: 运行结果
    """
    command = f'docker exec -it {container_id} {cmd}'
    if cmd_arg:
        command += f' {cmd_arg}'
    return basic.run(node, command, **kwargs)


def docker_ssh_login(node, container_id: str, ip: str, username: str = 'root'):
    """
    通过docker ssh登录qemu虚拟机
    :param node:
    :param container_id: 容器id
    :param ip: qemu虚拟机在docker容器内ip
    :param username: 用户名
    :return:
    """
    return execute_in_container(node, container_id, f'ssh {username}@{ip}')


def docker_init_login(node, container_id: str, ip: str, password: str, username: str = 'root'):
    """docker登录配置免密"""
    public_key = ssh.generate_rsa(node)
    ssh.init_login(
        node,
        ip=ip,
        usr=username,
        passwd=password,
        login_func=lambda node_, ip_, usr_name: docker_ssh_login(node_, container_id, ip_, usr_name)
    )
    ssh.add_public_key(node, public_key)


def exec_out_of_container(node, container_name: str, cmd: str, **kwargs) -> basic.Result:
    """
    不进入容器执行一行命令
    :param node:
    :param container_name: 容器名
    :param cmd: 待运行命令
    :return: 运行结果
    """
    command = f'docker exec {container_name} {cmd}'
    return basic.run(node, command, **kwargs)


