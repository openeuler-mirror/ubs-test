#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import re

from libs.modules.ubsmem.common.command_excutor import CommandExecutor


class CliInteractor(CommandExecutor):
    def __init__(self, ssh_host, cli_cmd: str, app_id: int):
        super().__init__(ssh_host)
        self.cli_cmd = cli_cmd
        self.app_id = app_id

    def run(self, cmd: str, timeout=650) -> str:
        result = self._ssh_host.run({"command": [self.cli_cmd],
                                     "waitstr": "cli>",
                                     "timeout": timeout,
                                     "input": [f"attach {self.app_id}", "cli>", cmd, "cli>", "exit"]})
        if result['stderr']:
            raise Exception("cli命令执行失败:%s" % result)
        return self._split_stdout(result['stdout'], 3)

    @staticmethod
    def _get_func_ret_code(output: str) -> int:
        match = re.search(r'ret\((-?\d+)\)', output)
        if not match:
            raise RuntimeError(f"Failed to match the return value.")
        return int(match.group(1))