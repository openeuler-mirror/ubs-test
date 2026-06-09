#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

import time
from typing import Optional

from libs.ubturbo.common import basic, file_transport, string_utils


DEFAULT_PS1 = r"\u@#>"

AUTO_LOGIN_READY = 2
AUTO_LOGIN_NOT_READY = 1
LOGIN_FAILED = 0

SSH_ARGS = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"


def ssh_login(node, vm_user, vm_ip, timeout=60, port=None):
    """ssh命令登录"""
    cmd = f"ssh {SSH_ARGS} {vm_user}@{vm_ip}"
    if port:
        cmd += f" -p {port}"
    return basic.run(node, cmd, timeout=timeout, waitstr="password:", returnCode=False)


def ssh_exit(node):
    """退出登录"""
    return basic.run(node, "exit", timeout=5)


def init_login(node, ip, usr, passwd, login_func=ssh_login, check_sep=10, timeout=3 * 60):
    """第一次登录，使用名称密码进行验证"""
    def try2login():
        res = login_func(node, usr, ip)
        if "System load:" in res.output:
            basic.logger.info("虚拟机已配置免密登录")
            return AUTO_LOGIN_READY
        elif "password:" in res.output:
            basic.logger.info("输入密码")
            basic.run(
                node,
                passwd,
                waitstr=f"]#|{node.username}{string_utils.DEFAULT_WAIT_STRING}",
                returnCode=False,
            )
            return AUTO_LOGIN_NOT_READY
        return LOGIN_FAILED

    login_status = basic.wait_until(try2login, check_sep=check_sep, timeout=timeout, msg="登录回显")
    if not login_status:
        raise Exception("登录失败")

    return login_status


def generate_rsa(node) -> Optional[str]:
    """检测/root/.ssh下是否有rsa密钥文件，如果没有则创建，返回公钥字符串"""
    import libs.ubturbo.api.system as system  # 延迟导入，避免循环依赖
    fp_rsa_pub = "/root/.ssh/id_rsa.pub"
    if not system.is_path_exist(node, fp_rsa_pub):
        basic.run(
            node,
            "ssh-keygen -t rsa -b 2048 -f ~/.ssh/id_rsa",
            waitstr="Enter passphrase",
            input=["\n", "Enter same passphrase again:", "\n"],
        )
    return system.read_file(node, fp_rsa_pub)


def add_public_key(node, pub_key):
    """配置免密登录"""
    import libs.ubturbo.api.system as system  # 延迟导入，避免循环依赖
    folder = "~/.ssh"
    fp_authorized_keys = f"{folder}/authorized_keys"
    basic.logger.info(f"将主机公钥加入虚拟机{fp_authorized_keys}文件")
    if pub_key in system.read_file(node, fp_authorized_keys):
        basic.logger.info("已加入，跳过")
        return
    system.mkdir(node, folder)
    file_transport.dump_text(node, pub_key, fp_authorized_keys, append=True)


def execute(node, vm_user, vm_ip, cmd: str, **kwargs) -> basic.Result:
    """通过ssh执行命令"""
    cmd = cmd.replace("'", r"'\''")
    cmd = f"ssh {SSH_ARGS} {vm_user}@{vm_ip} '{cmd}'"
    return basic.run(node, cmd, **kwargs)


def set_ps1(node):
    """设置终端回显字符串"""
    fn = "~/.bashrc"
    file_transport.dump_text(node, f'export PS1="{DEFAULT_PS1}"', fn, append=True)
    basic.run(node, f"source {fn}")