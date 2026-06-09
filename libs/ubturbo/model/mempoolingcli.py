#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2024. All rights reserved.

import time
from libs.ubturbo.common import basic
from libs.ubturbo.common.string_utils import strip_wait_string, STR_ENTER

REMOTE_MEMPOOLING_CLI_PATH = "/home/mempooling-test/mempooling-cli"


class MempoolingCli:
    def __init__(self, node, cli_path=REMOTE_MEMPOOLING_CLI_PATH, cli_client="cli_client", cli_server="cli_server"):
        """
        封装mempoolingcli工具，使用with语句保证工具正常登入登出。使用示例：
        with MempoolingCli(node) as cli：
            ret = cli.run("XXX")
        :param node:
        :param cli_path: mempooling cli可执行文件路径，默认/home/mempooling-test/mempooling-cli
        :param cli_client: cli_client端二进制文件名，默认cli_client
        :param cli_server: cli_server端二进制文件名，默认cli_server
        """
        self.node = node
        self.cli_path = cli_path
        self.cli_client = cli_client
        self.cli_server = cli_server
        self.default_str_enter = STR_ENTER

    def __enter__(self):
        node = self.node
        cli_path = self.cli_path
        cli_client = self.cli_client
        cli_server = self.cli_server

        # 杀掉旧的cli进程
        basic.run(node, f"pkill -f {cli_server}", timeout=300)
        basic.run(node, f"pkill -f {cli_client}", timeout=300)
        # 修改cli可执行文件权限
        basic.run(node, f"chmod 755 {cli_path}/{cli_server}")
        basic.run(node, f"chmod 755 {cli_path}/{cli_client}")
        # 登入cli
        basic.run(node, f"cd {cli_path}")
        basic.run(node, f"nohup ./{cli_server} &")
        basic.run(node, f"./{cli_client}", waitstr="root:/cli>", returnCode=False)
        # 等待5秒确保服务端就绪
        time.sleep(5)
        basic.run(node, "ls", waitstr="root:/cli", returnCode=False)
        basic.run(node, "attach 777", waitstr="root:/cli>", returnCode=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        node = self.node
        cli_server = self.cli_server
        basic.run(node, "quit", waitstr="root:/cli", returnCode=False)
        basic.run(node, f"pkill -f {cli_server}", timeout=300)

    def run(self, cmd):
        """
        mempooling cli工具中执行命令，并返回回显
        """
        raw_output = basic.run(self.node, cmd, waitstr="root:/cli>", returnCode=False).stdout
        ret = strip_wait_string(raw_output, "root", ":/cli>")
        return ret