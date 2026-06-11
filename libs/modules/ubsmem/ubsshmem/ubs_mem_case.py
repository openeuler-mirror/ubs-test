#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
"""UBS Memory test case base - migrated from legacy UbsMemCase.

Migrated from: legency/testcase/ubsmem/Lib/UbsShmem/ubs_mem_case.py
"""
import pytest
import time
from typing import Any, Dict, List

from libs.core.base import TestCase


@pytest.fixture(autouse=True)
def inject_ubs_mem_case_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """Inject UbsMemCase dependencies. Only injects for UbsMemCase and its subclasses."""
    if isinstance(request.instance, UbsMemCase):
        request.instance._setup_with_fixtures(nodes, resource, custom_params)


class UbsMemCase(TestCase):
    """UBS Memory test case base class - migrated from legacy UbsMemCase."""
    
    # Class-level defaults (overridable via custom_params)
    install_path: str = "/home/ci/ubs_mem"
    log_bak_path: str = "/home/ubs_mem_log_bak"
    tls_path: str = "/usr/local/ubs_mem/.pkey"
    cache_num: int = 5
    memory_unit: int = 128 * 1024 * 1024
    default_region: str = "default"
    _host_name_list: List[str] = []
    _node_id_list: List[int] = []

    def _setup_with_fixtures(self, nodes, resource, custom_params):
        """Initialize instance attributes from fixture-injected dependencies.
        
        Called by inject_ubs_mem_case_dependencies fixture.
        Replaces legacy __init__ pattern by receiving pytest fixtures directly.
        """
        from libs.modules.ubsmem.ubsshmem.ubs_mem_node import UbsMemNode

        self.nodes = nodes if nodes else []
        self.resource = resource
        self.install_path = custom_params.get("install_path", self.install_path)
        self.log_bak_path = custom_params.get("log_bak_path", self.log_bak_path)
        self.tls_path = custom_params.get("tls_path", self.tls_path)

        self.host_nodes = [UbsMemNode(host, self.install_path, index)
                           for index, host in enumerate(self.nodes, start=1)]
        self.node_count = len(self.host_nodes)

        self._core_file_count = 0
        self._init_host_name()
        self._init_host_id()

    def sleep(self, time_s: float) -> None:
        self.logInfo(f"start waiting for {time_s} seconds")
        time.sleep(time_s)
    
    def setup_method(self):
        self.check_env()
        self._core_file_count = self.get_core_file_count()
    
    def teardown_method(self):
        """Legacy: postTestCase."""
        self.check_env()
        new_count = self.get_core_file_count()
        self.assertEqual(self._core_file_count, new_count)
    
    def check_env(self):
        for node in self.host_nodes:
            result = node.ubsm_service_active()
            self.assertEqual(result, True)
            result = node.ubse_service_active()
            self.assertEqual(result, True)
            node.run(f"ps -ef | grep --color=never {node.app_name}")
    
    def get_core_file_count(self) -> int:
        core_count = 0
        for node in self.host_nodes:
            core_count = node.get_core_dumped_num() + core_count
        return core_count
    
    def find_master_index(self) -> int:
        master_list = []
        for i, node in enumerate(self.host_nodes):
            if not node.ubsm_service_active():
                self.logWarn(f"The node({node.node_id}) status is abnormal, it has been excluded.")
                continue
            if node.is_lock_master():
                master_list.append(i)
        if len(master_list) == 1:
            return master_list[0]
        else:
            self.logError(f"Found multiple primary nodes: {master_list}")
            return -1
    
    def find_ubse_master_index(self) -> int:
        master_index_set = set()
        for node in self.host_nodes:
            if not node.ubse_service_active():
                self.logInfo(f"The node({node.node_id}) status is abnormal")
                continue
            master_name = node.find_ubse_master()
            if not master_name:
                continue
            master_index_set.add(self._host_name_list.index(master_name))
        if len(master_index_set) != 1:
            raise RuntimeError("Multiple ubse master node were found.")
        return master_index_set.pop()
    
    def wait_ubse_master_ok(self, timeout: int) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                self.find_ubse_master_index()
            except RuntimeError:
                self.sleep(20)
                continue
            return True
        self.logInfo("Wait for ubse master to be ready failed.")
        return False
    
    def find_client_index(self) -> int:
        client_list = []
        for i, node in enumerate(self.host_nodes):
            if node.is_lock_client():
                client_list.append(i)
        if len(client_list) == 1:
            return client_list[0]
        else:
            self.logError(f"Found multiple primary nodes: {client_list}")
            return -1
    
    def lock_is_ready(self) -> bool:
        master_index = self.find_master_index()
        client_index = self.find_client_index()
        self.assertNotEqual(master_index, client_index)
        for _ in range(10):
            master_ready = self.host_nodes[master_index].apps[0].lock_is_ready()
            client_ready = self.host_nodes[client_index].apps[0].lock_is_ready()
            if master_ready and client_ready:
                return True
            self.sleep(20)
        return False
    
    def get_slave_list(self, master_index: int) -> List[int]:
        return [i for i in range(len(self.host_nodes)) if i != master_index]
    
    def wait_rack_mem_ok(self, timeout: int) -> bool:
        node_list = [node.node_id for node in self.host_nodes]
        start_time = time.time()
        while time.time() - start_time < timeout:
            ok_count = 0
            for node in self.host_nodes:
                mem_ok = node.check_rack_mem_ok_by_id(node_list)
                if mem_ok:
                    ok_count = ok_count + 1
            if ok_count == len(self.host_nodes):
                return True
            self.sleep(60)
        self.logInfo("Wait for rack memory to be ready failed.")
        return False
    
    def wait_some_node_rack_mem_ok(self, timeout: int, node_id_list: list) -> bool:
        node_list = [node for node in self.host_nodes if node.node_id in node_id_list]
        start_time = time.time()
        while time.time() - start_time < timeout:
            ok_count = 0
            for node in node_list:
                self.logInfo(f"node_id: {node.node_id}, node_list: {node_id_list}")
                mem_ok = node.check_rack_mem_ok_by_id(node_id_list)
                if mem_ok:
                    ok_count = ok_count + 1
            if ok_count == len(node_list):
                return True
            self.sleep(60)
        self.logInfo("Wait for rack memory to be ready failed.")
        return False
    
    def find_index_by_host(self, host_name: str) -> int:
        return self._host_name_list.index(host_name)
    
    def find_index_by_slot(self, slot_id: int) -> int:
        return self._node_id_list.index(slot_id)
    
    def _init_host_name(self):
        if len(self._host_name_list) == 0:
            for node in self.host_nodes:
                name = node.get_host_name()
                self._host_name_list.append(name)
        else:
            self.logInfo("The hostname has been obtained.")
        for name, node in zip(self._host_name_list, self.host_nodes):
            node.set_host_name(name)
    
    def _init_host_id(self):
        if len(self._node_id_list) == 0:
            for node in self.host_nodes:
                node_id = node.get_node_id(node.host_name)
                if node_id == -1:
                    self._node_id_list.clear()
                    return
                self._node_id_list.append(node_id)
        else:
            self.logInfo("The node id has been obtained.")
        for node_id, node in zip(self._node_id_list, self.host_nodes):
            node.set_node_id(node_id)