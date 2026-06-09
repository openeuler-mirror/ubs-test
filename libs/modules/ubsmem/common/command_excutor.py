#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import time
from dataclasses import dataclass

from libs.utils.logger_compat import Log


@dataclass
class ExecuteResult:
    std_rc: int
    std_out: str
    std_err: str


class CommandExecutor:
    def __init__(self, ssh_host):
        self._ssh_host = ssh_host
        self.logger = Log.getLogger(str(self.__module__))

    @staticmethod
    def _split_stdout(std_out, start_index: int = 0, end_index: int = None) -> str:
        """
        对stdout输出进行切片
        @param std_out: 命令的所有输出
        @param start_index: stdout的起始行数
        @param end_index: stdout的结束函数(不包含)
        """
        return '\n'.join([x.strip() for x in std_out.split('\n')][start_index:end_index])

    def run(self, cmd: str):
        pass

    def get_ssh_host(self):
        return self._ssh_host

    def sleep(self, time_s: float):
        self.logger.info(f"start waiting for {time_s} seconds")
        time.sleep(time_s)