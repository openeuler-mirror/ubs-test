#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025
import time

from libs.core.base import TestCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_node import UbsMemNode


class UbsMemHook(TestCase):
    """UBS Memory test hook.

    CRITICAL: No __init__ method. Use _init_from_fixture() after instantiation
    to set required attributes via fixture injection.
    """

    install_path: str = "/home/ci/ubs_mem"
    log_path: str = ""
    nodes: list = []
    packages_list: list = [ "ubs-mem-shmem-*.*.aarch64.rpm"]

    def sleep(self, time_s: float) -> None:
        self.logInfo(f"start waiting for {time_s} seconds")
        time.sleep(time_s)

    def _init_from_fixture(self, nodes: list, custom_params: dict) -> None:
        """Initialize instance attributes from fixture-injected dependencies.

        Called by the package_hook_fixture after instantiation,
        to replace the legacy __init__ pattern.

        Args:
            nodes: List of libs.host.Linux SSH host objects from --resource-config
            custom_params: Dict from --test-params JSON
        """
        self._ssh_hosts = nodes
        self.install_path = custom_params.get("install_path", self.install_path)
        self.log_path = f"{self.install_path}/log"
        self.nodes = [UbsMemNode(host, self.install_path, i) for i, host in enumerate(self._ssh_hosts, start=1)]

    def beforePreTestSet(self, **kwargs):
        self.prepare_env()
        self.install_packages()
        self.clear_obmm_device()
        self.start_test_apps()


    def afterPostTestSet(self, **kwargs):
        pass

    def prepare_env(self):
        for node in self.nodes:
            node.update_sys_time()
            node.set_core_dumped_dir(node.core_dir)
            node.set_history_timestamp()

    def install_packages(self):
        for node in self.nodes:
            node.remove_file(self.install_path)
            node.mkdir(self.install_path)
            node.mkdir(self.log_path)
            node.mkdir(f"{self.install_path}/bin")
            # 把测试工具拷贝过来#todo 待测试，拷贝测试工具到工作目录
            node.copy_file(f"/opt/install/tmp/ubs-mem-dist/ubs_mem_test", f"{self.install_path}/bin/")
            node.chmod(self.install_path, 0o777, True)

    def clear_obmm_device(self):
        for node in self.nodes:
            node.clear_obmm()

    def start_test_apps(self):
        for node in self.nodes:
            node.start_apps(self.nodes[0].default_app_num)
        self.sleep(10)
        for node in self.nodes:
            app_alive = node.app_is_alive(node.default_app_num)
            if not app_alive:
                raise RuntimeError("Failed to start diagnose")