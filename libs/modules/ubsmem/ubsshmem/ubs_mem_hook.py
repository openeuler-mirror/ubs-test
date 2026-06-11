#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025
import time
import logging

from libs.modules.ubsmem.common.multi_task import MultiTask
from libs.modules.ubsmem.ubsshmem.ubs_mem_node import UbsMemNode
from libs.core.base import TestCase


class UbsMemHook(TestCase):
    """UBS Memory test hook.

    CRITICAL: No __init__ method. Use _init_from_fixture() after instantiation
    to set required attributes via fixture injection.
    """

    install_path: str = "/home/ci/ubs_mem"
    log_path: str = ""
    cmc_package_path: str = "/ko/matrix_shmem"
    nodes: list = []
    packages_list: list = ["ubs-comm-lib-*-*.*.aarch64.rpm", "ubs-comm-devel-*-*.*.aarch64.rpm",
                           "ubs-engine-1.0.0-*.aarch64.rpm", "ubs-engine-client-libs-*.*.aarch64.rpm",
                           "ubs-engine-client-devel-*.*.aarch64.rpm", "ubs-mem-memfabric-*.*.aarch64.rpm"]
    node_count: int = 0

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
        self.cmc_package_path = custom_params.get("cmc_package_path", self.cmc_package_path)
        self.nodes = [UbsMemNode(host, self.install_path, i) for i, host in enumerate(self._ssh_hosts, start=1)]
        self.node_count = len(self.nodes)
        self.obmm_path = f"{self.install_path}/bin/ub_clear_obmm"

    def beforePreTestSet(self, **kwargs):
        self.prepare_env()
        self.remove_packages()
        self.install_packages()
        self.obmm_device_clear()
        self.modify_ubse_config()
        self.start_ubse_service()
        self.modify_ubsm_config()
        self.turn_on_tls_and_modify_config()
        self.start_ubsm_service()
        self.start_diagnose()

    def turn_on_tls_and_modify_config(self):
        install_path = "/usr/local/ubs_mem"
        base_path = f"{install_path}/.pkey"
        ca_path = f"{base_path}/ca"
        cert_path = f"{base_path}/cert"
        revoked_path = f"{base_path}/revoked"
        crl_path = f"{base_path}/crl"

        for node in self.nodes:
            node.remove_file(base_path)
            node.mkdir(ca_path)
            node.mkdir(cert_path)
            node.mkdir(revoked_path)
            node.mkdir(crl_path)

        ca_file = self.nodes[0].generate_tls_ca_path(ca_path)
        cert_res = self.nodes[0].generate_tls_cert_path(ca_path, cert_path)
        revoked_cert = self.nodes[0].generate_tls_revoked_cert_path(ca_path, revoked_path)
        crl_file = self.nodes[0].generate_tls_crl_path(crl_path, ca_path, revoked_cert)

        for node in self.nodes[1:]:
            self.nodes[0].sftp(base_path, node, install_path, True)

        for node in self.nodes:
            node.chown(f"{install_path}", "ubsmd", "ubsmd", True)
            node.modify_ubsmd_config("ubsm.server.tls.enable", "on")
            node.modify_ubsmd_config("ubsm.server.tls.ca.path", ca_file)
            node.modify_ubsmd_config("ubsm.server.tls.cert.path", cert_res[0])
            node.modify_ubsmd_config("ubsm.server.tls.key.path", cert_res[1])
            node.modify_ubsmd_config("ubsm.server.tls.crl.path", crl_file)

            pkey_res = node.generate_private_key(f"{install_path}/bin/", f"{install_path}/config")
            node.modify_ubsmd_config("ubsm.server.tls.keypass.path", pkey_res[0])
            node.modify_ubsmd_config("ubsm.server.tls.ksf.master.path ", pkey_res[1])
            node.modify_ubsmd_config("ubsm.server.tls.ksf.standby.path", pkey_res[2])

            node.modify_ubsmd_config("ubsm.lock.tls.enable", "on")
            node.modify_ubsmd_config("ubsm.lock.tls.ca.path", ca_file)
            node.modify_ubsmd_config("ubsm.lock.tls.cert.path", cert_res[0])
            node.modify_ubsmd_config("ubsm.lock.tls.key.path", cert_res[1])
            node.modify_ubsmd_config("ubsm.lock.tls.crl.path", crl_file)

            node.modify_ubsmd_config("ubsm.lock.tls.keypass.path", pkey_res[0])
            node.modify_ubsmd_config("ubsm.lock.tls.ksf.master.path", pkey_res[1])
            node.modify_ubsmd_config("ubsm.lock.tls.ksf.standby.path", pkey_res[2])

    def afterPostTestSet(self, **kwargs):
        pass

    def createMetadata(self):
        self.addParameter(name="cmc_package_path",
                          description="specifies cmc package information.",
                          type="Text",
                          default_value="/ko/matrix_shmem")

    def prepare_env(self):
        for node in self.nodes:
            node.update_sys_time()
            node.remove_file(self.install_path)
            node.mkdir(self.install_path)
            node.mkdir(self.log_path)
            node.run("yum install -y libboundscheck")
            node.set_core_dumped_dir(node.core_dir)
            node.set_history_timestamp()
        for node in self.nodes:
            if node.is_borrow_from_1G_huge():
                continue
            if not node.is_borrow_from_huge():
                continue
            numa_count = len(node.get_loacl_numa())
            for i in range(numa_count):
                node.assign_huge_pages(i, 2048, 40960)
                node.show_numa_stat()

    def install_packages(self):
        for node in self.nodes:
            for package in self.packages_list:
                node.run(f"rpm -ivh {self.cmc_package_path}/{package} --force")
            node.unzip(f"{self.cmc_package_path}/ubs_mem_test.zip", self.install_path)
            node.copy_file(f"{self.cmc_package_path}/stress-ng", node.stress_ng_path)
            node.chmod(self.install_path, 0o777, True)

    def modify_ubse_config(self):
        for node in self.nodes:
            node.modify_rack_config("log.level", "DEBUG")
            node.modify_rack_config("node.num", f"{len(self.nodes)}")
            node.modify_rack_config("log.fileNums", f"200")
            node.modify_rack_config("heartbeat.timeInterval", "15000")
            node.modify_rack_config("cert.use", "false")
            node.comment_rack_config("cluster.ipList")
            if node.is_borrow_from_1G_huge():
                node.uncomment_rack_config("obmm.memory.block.size")
                node.modify_rack_config("obmm.memory.block.size", "1024")

    def modify_ubsm_config(self):
        for node in self.nodes:
            remote_ip = [f"{remote.node_ip}:7301" for remote in self.nodes if remote != node]
            remote_ip_str = ",".join(remote_ip)
            node.modify_ubsmd_config("ubsm.server.rpc.local.ipseg", f"{node.node_ip}:7301")
            node.modify_ubsmd_config("ubsm.lock.enable", "on")
            node.modify_ubsmd_config("ubsm.server.rpc.remote.ipseg", remote_ip_str)
            node.modify_ubsmd_config("ubsm.server.log.rotation.file.count", "50")
            node.modify_ubsmd_config("ubsm.server.log.rotation.file.size", "100")
            node.modify_ubsmd_config("ubsm.lock.dev.name", f"bonding_dev_0")
            urma_eid = node.get_urma_eid()
            node.modify_ubsmd_config("ubsm.lock.dev.eid", urma_eid)
            node.modify_ubsmd_config("ubsm.discovery.min.nodes", str(int(self.node_count / 2 + 1)))
            node.modify_ubsmd_config("ubsm.server.tls.enable", "off")
            node.modify_ubsmd_config("ubsm.lock.expire.time", "300")
            node.modify_ubsmd_config("ubsm.server.log.level", "DEBUG")
            node.modify_ubsmd_config("ubsm.lock.tls.enable", "off")
            node.modify_ubsmd_config("ubsm.hcom.max.connect.num", "256")
            node.modify_ubsmd_config("ubsm.performance.statistics.enable", "on")
            node.modify_ubsmd_config("ubsm.server.lease.cache.enable", "off")
            node.modify_ubsmd_config("ubsm.lock.enable", "off")

    def remove_packages(self):
        task = MultiTask(self.nodes)
        task.clear_all_app()
        task.ubsm_service_stop()
        task.run("rpm -e ubs_mem")
        task.clear_ubsm_records()
        task.ubse_service_stop()
        task.run("rpm -e ubs-engine")
        task.run("rpm -e ubs-engine-client-devel")
        task.run("rpm -e ubs-engine-client-libs")
        task.remove_file("/etc/ubse/*")
        task.run("rpm -e ubs-comm-devel")
        task.run("rpm -e ubs-comm-lib")

    def obmm_device_clear(self):
        for node in self.nodes:
            node.clear_obmm()

    def wait_rack_mem_ok(self, timeout: int):
        node_name_list = [node.get_host_name() for node in self.nodes]
        self.logger.info(f"Waiting for rack mem ok, host name: {node_name_list}")
        start_time = time.time()
        mem_ok = False
        for node in self.nodes:
            while time.time() - start_time < timeout:
                mem_ok = node.check_rack_mem_ok_by_name(node_name_list)
                if mem_ok:
                    break
                self.sleep(60)
            if not mem_ok:
                raise RuntimeError(f"Rack mem plugin initialization failed")

    def start_ubse_service(self):
        task = MultiTask(self.nodes)
        task.ubse_service_start()
        self.sleep(20)
        self.wait_rack_mem_ok(600)

    def start_ubsm_service(self):
        task = MultiTask(self.nodes)
        task.ubsm_service_start()
        for node in self.nodes:
            ubsmd_active = node.wait_ubsm_active(120)
            if not ubsmd_active:
                raise RuntimeError("Failed to start ubsm service")

    def start_diagnose(self):
        for node in self.nodes:
            node.start_apps(self.nodes[0].default_app_num)
            node.start_cli_server()
        self.sleep(10)
        for node in self.nodes:
            app_alive = node.app_is_alive(node.default_app_num)
            if not app_alive:
                raise RuntimeError("Failed to start diagnose")