"""HCOMBaseCase - Base class for HCOM test cases.

Migrated from: legency/testcase/ubscomm/hcom/lib/basecase/hcom/HCOMBaseCase.py

CRITICAL CHANGE (2026-05-16):
- 移除__init__方法，解决pytest无法收集带__init__测试类的硬限制
- 使用@pytest.fixture(autouse=True)注入外部依赖参数(nodes, resource, custom_params)
- 硬编码路径转为类属性
- 业务参数在fixture中初始化
"""

import os
import json
import random
import ast
import logging
import pytest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

from libs.core.basecase.hcom.turbo_comm_basecase import TurboCommBaseCase
from libs.hcom.constants import HCOM_RESOURCE_PATH, TEST_DATA_PATH
from libs.hcom.stub_params import Params, ConfigAttrs
from libs.hcom.env_check import (
    check_network_between_nodes,
    get_rdma_ip,
    get_ub_ip,
    env_check_between_hccs_nodes,
    get_eid,
)
from libs.hcom.node_run import create_ssh, close_ssh, send_cmd_list
from libs.utils.logger_compat import Log

logger = logging.getLogger(__name__)

CODE_PATCH_PATH = str(Path(__file__).resolve().parents[3])


@pytest.fixture(autouse=True)
def inject_hcom_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入HCOMBaseCase外部依赖参数.
    
    只对HCOMBaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.core.basecase.hcom.hcom_basecase import HCOMBaseCase
    if not isinstance(instance, HCOMBaseCase):
        return
    
    # 注入基础依赖
    instance.nodes = nodes
    instance.resource = resource
    instance.custom_params = custom_params
    
    # Logger初始化
    instance.logger = Log.getLogger(instance.__class__.__name__)
    
    # 从custom_params提取参数
    instance.case_number = custom_params.get("identity", {}).get("id", "")
    instance.case_dir = custom_params.get("case_dir", "perf_test")
    instance.teststub_file = custom_params.get('teststub_file', 'perf_teststub_config.json')
    instance.dataset_file = custom_params.get('dataset_file', 'test_tool.json')
    instance.test_scene = ast.literal_eval(custom_params.get('test_scene', '{}'))
    instance.env_var_keywords = ast.literal_eval(custom_params.get('env_var_keywords', '["basic"]'))
    instance.env_secure_keywords = ast.literal_eval(custom_params.get('env_secure_keywords', '["normalCertChain","normalCertChain"]'))
    instance.expect_index = ast.literal_eval(custom_params.get('expect_index', '[""]'))
    instance.test_stub_dir = custom_params.get('test_stub_dir', '')
    instance.test_type = custom_params.get('test_type', 'v2')
    instance.server_wait = custom_params.get('server_wait', 'Destroy endpoint')
    instance.link_mode = custom_params.get('link_mode', '')
    
    # 硬编码路径
    instance.lib_dir = HCOMBaseCase.LIB_DIR
    instance.base_dir = HCOMBaseCase.BASE_DIR
    
    # 条件路径计算
    instance.run_dir = f"{instance.base_dir}/{instance.case_dir}"
    if instance.test_stub_dir != '':
        instance.run_dir = f"{instance.base_dir}/{instance.test_stub_dir}"
    
    if instance.test_type != '':
        instance.lib_dir = f"{instance.lib_dir}_{instance.test_type}"
    
    # 运行时对象
    instance.executor = ThreadPoolExecutor(max_workers=64)
    
    # 状态变量初始化
    instance.server_rdma_ip = None
    instance.server_ub_ip = None
    instance.server_ubc_eid = None
    instance.client_ubc_eid = None
    instance.datasets = {}
    instance.result_datasets = {}
    
    logger.info(f"HCOMBaseCase initialized: run_dir={instance.run_dir}, class={instance.__class__.__name__}")


class HCOMBaseCase(TurboCommBaseCase):
    """Base class for HCOM test cases.
    
    Provides HCOM-specific initialization:
    - Dataset loading from resource/test_data
    - Test scene initialization
    - IP/EID initialization for RDMA/UB/HCCS
    - Environment variable configuration
    - Input/output expectation handling
    
    CRITICAL: This class NO LONGER has __init__ method.
    pytest cannot collect test classes with __init__ (even with default args).
    
    Initialization is handled by fixture injection (@pytest.fixture(autouse=True)).
    """
    
    # 类属性 - 硬编码路径
    LIB_DIR = "/usr/lib64"
    BASE_DIR = "/home/ubs-comm/hcom"
    
    def preTestCase(self) -> None:
        self.logStep("Initializing test datasets")
        self.datasets = self.init_datasets(self.dataset_file)
    
    def init_datasets(self, dataset_file: str) -> dict:
        """Load test datasets from JSON file."""
        teststub_config = os.path.join(HCOM_RESOURCE_PATH, self.teststub_file)
        with open(teststub_config, encoding='utf-8') as fd:
            data = json.load(fd)
        config_list = {}
        for k, v in data.items():
            config_list[k] = ConfigAttrs.from_dict(v)
        
        datasets = {}
        dataset_path = os.path.join(TEST_DATA_PATH, dataset_file)
        self.logInfo(f"Reading dataset {dataset_path}")
        with open(dataset_path, encoding='utf-8') as fd:
            datasets_json = json.load(fd)
        for key, value in datasets_json.items():
            datasets[key] = Params(config_list, value)
        return datasets
    
    def init_test_scene(self, datasets: dict, test_scene: dict) -> None:
        """Initialize test scene with parameters."""
        self.logInfo(f"Initializing test scene: {test_scene}")
        for data in datasets.values():
            for key, value in test_scene.items():
                data.set_attr_value(key, value)
    
    def init_ip_eid(self, local_ip: str, **kwargs) -> tuple:
        """Initialize IP/EID based on driver/oob type."""
        if kwargs.get("driver_type") == "RDMA":
            self.env_check(link_type="rdma")
            return self.server_rdma_ip, self.server_rdma_ip
        elif kwargs.get("driver_type") == "UBOE":
            self.env_check(link_type="ub")
            return self.server_ub_ip, self.server_ub_ip
        elif kwargs.get("oob_type") == "NET_OOB_UB":
            self.get_eid(ubep_dev="bonding_dev_0")
            return self.server_ubc_eid, self.server_ubc_eid
        elif kwargs.get("oob_type") == "NET_OOB_UDS":
            if kwargs.get("port") == '0':
                return "shm_test", "shm_test"
            else:
                return f"{self.run_dir}/shm_test", f"{self.run_dir}/shm_test"
        elif self.link_mode == "IP_OVER_URMA":
            self.get_eid(ubep_dev="bonding_dev_0")
            return self.server_ubc_eid, self.server_ubc_eid
        else:
            return local_ip, local_ip
    
    def init_env_variable(self, keywords: list, cert_name: list, **kwargs) -> tuple:
        """Initialize environment variables for HCOM."""
        server_env = ""
        client_env = ""
        
        if "basic" in keywords:
            server_env += f"export LD_LIBRARY_PATH={self.lib_dir}:$LD_LIBRARY_PATH;"
            client_env += f"export LD_LIBRARY_PATH={self.lib_dir}:$LD_LIBRARY_PATH;"
        
        if "secure" in keywords:
            server_env += (f"export HCOM_OPENSSL_PATH=/home/TurboComm/automation/hcom/secure/scflib;"
                           f"export LD_LIBRARY_PATH=$HCOM_OPENSSL_PATH:$LD_LIBRARY_PATH;"
                           f"export TLS_CERT_PATH=/home/TurboComm/automation/hcom/secure/opensslcrt/{cert_name[0]};")
            client_env += (f"export HCOM_OPENSSL_PATH=/home/TurboComm/automation/hcom/secure/scflib;"
                           f"export LD_LIBRARY_PATH=$HCOM_OPENSSL_PATH:$LD_LIBRARY_PATH;"
                           f"export TLS_CERT_PATH=/home/TurboComm/automation/hcom/secure/opensslcrt/{cert_name[1]};")
        
        if "pkt_seg" in keywords:
            server_env += f"export HCOM_ENABLE_SPLIT_SEND=1;"
            client_env += f"export HCOM_ENABLE_SPLIT_SEND=1;"
        
        if "rndv_seg" in keywords:
            server_env += f"export HCOM_RNDV_THRESHOLD={kwargs['hcom_rndv_seg']};"
            client_env += f"export HCOM_RNDV_THRESHOLD={kwargs['hcom_rndv_seg']};"
        
        if "set_log" in keywords:
            server_env += f"export HCOM_SET_LOG_LEVEL={kwargs['hcom_set_log_level']};"
            client_env += f"export HCOM_SET_LOG_LEVEL={kwargs['hcom_set_log_level']};"
        
        self.logInfo(f"server env: {server_env}")
        self.logInfo(f"client env: {client_env}")
        return server_env, client_env
    
    def init_inputs_expects(self, expect_list: dict, input: str, waitstr: str) -> tuple:
        """Initialize input and expectation lists."""
        if input != "":
            input_res = [input, waitstr, "q", "@#>"]
        else:
            input_res = ["q", "@#>"]
        self.logInfo(f"command input: {input_res}")
        
        expect_res = [expect_list[input]]
        self.logInfo(f"command expected: {expect_res}")
        return input_res, expect_res
    
    def init_ssh_inputs_expects(self, expect_list: dict, input: str) -> tuple:
        """Initialize SSH input and expectation lists."""
        input_res = [input, "q"]
        self.logInfo(f"command input: {input_res}")
        
        expect_res = [expect_list[input]]
        self.logInfo(f"command expected: {expect_res}")
        return input_res, expect_res
    
    def check_dataset_result(self, result_datasets: dict) -> None:
        """Check all dataset results for failures."""
        for key, value in result_datasets.items():
            self.assertNotIn("fail", value.values(), f"Dataset {key} failed")
    
    def env_check(self, link_type: str = "tcp") -> None:
        """Environment check for tcp/rdma/hshmem/hccs/ub."""
        self.logStep("Starting environment check")
        
        if link_type == "tcp":
            res = check_network_between_nodes(self.nodes)
            self.assertTrue(res)
        elif link_type == "rdma":
            self.server_rdma_ip = get_rdma_ip(self.nodes[0], self.nodes[1])
            self.assertNotEqual(self.server_rdma_ip, None)
        elif link_type == "hshmem":
            res = env_check_between_hccs_nodes(self.nodes, check_urma=False)
            self.assertTrue(res)
        elif link_type == "hccs":
            res = env_check_between_hccs_nodes(self.nodes)
            self.assertTrue(res)
        elif link_type == "ub":
            self.server_ub_ip = get_ub_ip(self.nodes[0], self.nodes[1])
            self.assertNotEqual(self.server_ub_ip, None)
        
        self.logStep("Environment check complete, environment OK")
    
    def env_check_ubc(self, node_ip=None) -> int:
        """Check if environment is UBOE or UB simulation."""
        protocol = 6
        if (self.server_ub_ip == '1.2.3.4' or self.server_ub_ip == '1.2.3.5' or
                self.server_ub_ip == '1.2.4.4' or self.server_ub_ip == '1.2.4.5'):
            protocol = 7
        return protocol
    
    def get_pid(self, executor, server, ps_msg: str) -> str:
        """Get process PID from server."""
        ch, ssh = create_ssh(server)
        cmd_get_pid = f"ps -ef|grep {ps_msg}|grep -v grep\n"
        
        self.logStep(f"Checking process info on {server.localIP}")
        executor.submit(send_cmd_list, ch, cmd_get_pid, time1=5, inputs=None, time2=0)
        
        from time import sleep
        sleep(2)
        
        self.logStep("Getting PID from ps output")
        res = ch.recv(65535000000).decode("utf-8")
        self.logDebug(f"ps_message: {res}")
        pid = res.split("root")[2].split()[0]
        
        close_ssh([ch, ssh])
        return pid
    
    def get_eid(self, ubep_dev: str = "udma0") -> None:
        """Get URMA endpoint EID."""
        self.server_ubc_eid, self.client_ubc_eid = get_eid(self.nodes[0], self.nodes[1], ubep_dev)