#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025
import time
from pathlib import Path
from libs.core.base import TestCase
from libs.modules.ubse.common.ubse_process_ops import create_directory_and_upload

class MEM_Pooling_Hook(TestCase):

    def _init_from_fixture(self, nodes: list, custom_params: dict) -> None:
        """Initialize instance attributes from fixture-injected dependencies.

        Called by the package_hook_fixture after instantiation,
        to replace the legacy __init__ pattern.

        Args:
            nodes: List of libs.host.Linux SSH host objects from --resource-config
            custom_params: Dict from --test-params JSON
        """
        self.nodes = nodes

    def beforePreTestSet(self, **kwargs):
        create_directory_and_upload(
            nodes=self.nodes,
            files=["ubse_mem_app.py"],
            relative_path="resource/ubse",
            dir_path="/home/autotest"
        )
        for node in self.nodes:
            res = node.run({'command': ["lscpu | grep 'NUMA node(s)' | awk '{print $NF}'"]}).get("stdout")
            if res:
                numa_num = int(res.replace("root@#>", "").strip())
            for numa_id in range(numa_num):
                command = f"echo 20000 >/sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages"
                node.run({'command': command})

    def afterPostTestSet(self, **kwargs):
        pass
