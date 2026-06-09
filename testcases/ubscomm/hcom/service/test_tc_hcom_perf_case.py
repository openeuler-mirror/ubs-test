"""
Migrated from legacy: TC_HCOM_perf_Case

Parametrized test covering 12 testset instances:
- TC_HCOM_PERF_Service_UB_001
- TC_HCOM_PERF_Service_UB_002
- TC_HCOM_PERF_Service_UB_003
- TC_HCOM_PERF_Service_UB_004
- TC_HCOM_PERF_Service_UB_005
- TC_HCOM_PERF_Service_UB_006
- TC_HCOM_PERF_Transport_UB_001
- TC_HCOM_PERF_Transport_UB_002
- TC_HCOM_PERF_Transport_UB_003
- TC_HCOM_PERF_Transport_UB_004
- TC_HCOM_PERF_Transport_UB_005
- TC_HCOM_PERF_Transport_UB_006
"""

import pytest

from libs.core.basecase.hcom.hcom_basecase import HCOMBaseCase
from libs.hcom.constants import (
    client_input_expect_server_v2,
    quit_waitstr,
    server_input,
    server_waitstr,
)


TEST_SCENES_UB = [
    pytest.param(
        "TC_HCOM_PERF_Service_UB_001",
        {
            "case": "service_send_lat",
            "mode": "1",
            "data_size": "2048",
        },
        id="Service_UB_001",
    ),
    pytest.param(
        "TC_HCOM_PERF_Service_UB_002",
        {
            "case": "service_write_lat",
            "mode": "1",
            "data_size": "1048576",
        },
        id="Service_UB_002",
    ),
    pytest.param(
        "TC_HCOM_PERF_Service_UB_003",
        {
            "case": "service_read_lat",
            "mode": "1",
            "data_size": "1048576",
        },
        id="Service_UB_003",
    ),
    pytest.param(
        "TC_HCOM_PERF_Service_UB_004",
        {
            "case": "service_send_lat",
            "mode": "0",
            "data_size": "32768",
        },
        id="Service_UB_004",
    ),
    pytest.param(
        "TC_HCOM_PERF_Service_UB_005",
        {
            "case": "service_write_lat",
            "mode": "0",
            "data_size": "1048576",
        },
        id="Service_UB_005",
    ),
    pytest.param(
        "TC_HCOM_PERF_Service_UB_006",
        {
            "case": "service_read_lat",
            "mode": "0",
            "data_size": "1048576",
        },
        id="Service_UB_006",
    ),
    pytest.param(
        "TC_HCOM_PERF_Transport_UB_001",
        {
            "case": "transport_send_lat",
            "mode": "1",
            "data_size": "2048",
        },
        id="Transport_UB_001",
    ),
    pytest.param(
        "TC_HCOM_PERF_Transport_UB_002",
        {
            "case": "transport_write_lat",
            "mode": "1",
            "data_size": "1048576",
        },
        id="Transport_UB_002",
    ),
    pytest.param(
        "TC_HCOM_PERF_Transport_UB_003",
        {
            "case": "transport_read_lat",
            "mode": "1",
            "data_size": "1048576",
        },
        id="Transport_UB_003",
    ),
    pytest.param(
        "TC_HCOM_PERF_Transport_UB_004",
        {
            "case": "transport_send_lat",
            "mode": "0",
            "data_size": "32768",
        },
        id="Transport_UB_004",
    ),
    pytest.param(
        "TC_HCOM_PERF_Transport_UB_005",
        {
            "case": "transport_write_lat",
            "mode": "0",
            "data_size": "1048576",
        },
        id="Transport_UB_005",
    ),
    pytest.param(
        "TC_HCOM_PERF_Transport_UB_006",
        {
            "case": "transport_read_lat",
            "mode": "0",
            "data_size": "1048576",
        },
        id="Transport_UB_006",
    )
]


@pytest.mark.smoke
class TestTcHcomPerfCase(HCOMBaseCase):
    """
    CaseNumber:
        TC_HCOM_V2_Service_UB_Case (generic)
    RunLevel:
        Level 2
    EnvType:
        integration
    CaseName:
        HCOM V2 Service UB协议基础用例（参数化测试）
    PreCondition:
        1. 两台带有RDMA/UB网卡的节点
        2. 网络正常，ip可以ping通
        3. HCOM动态库存在且加载环境变量
    TestStep:
        1. 初始化测试场景和测试数据集
        2. 设置hcom环境变量
        3. 获取IP/EID
        4. 运行server和client测试程序
        5. 验证测试结果
        6. 清理进程
        7. 校验数据集结果
    ExpectedResult:
        1. server和client运行成功
        2. 测试结果验证通过
    Author:
        Legacy migration
    """


    def setup_method(self):
        self.logStep("初始化测试场景")
        super().preTestCase()

    @pytest.mark.parametrize("case_id, test_scene_param", TEST_SCENES_UB)
    def test_tc_hcom_perf_case(self, case_id: str, test_scene_param: dict):
        """
        TC_HCOM_V2_Perf_Case - Parametrized test for HCOM Perf scenarios
        """
        self.case_number = case_id
        self.init_test_scene(self.datasets, test_scene_param)
        server_node, client_node = self.nodes[0], self.nodes[1]

        for dataset_name, data in self.datasets.items():
            self.logStep(f"获取ip_eid")
            server_ip, client_ip = self.init_ip_eid(
                server_node.localIP,
                driver_type=data.driver_type.value,
                oob_type="NET_OOB_TCP",
            )
            self.logStep(f"验证 {self.case_number} 场景, 基本功能：{dataset_name}")
            server_command = data.get_run_cmd(server_type="server", ip=server_ip, server_name="hcom_perf", client_name="hcom_perf")
            client_command = data.get_run_cmd(server_type="client", ip=client_ip, server_name="hcom_perf", client_name="hcom_perf")
            cmd_s = (f"cd {self.run_dir}; stdbuf -oL {server_command} | tee -a server.log\n")
            cmd_c = (f"cd {self.run_dir}; stdbuf -oL {client_command} | tee -a client.log\n")

            result_dataset = self.base_run_ssh(
                server=server_node,
                client=client_node,
                executor=self.executor,
                cmd_s=cmd_s,
                cmd_c=cmd_c,
                inputs_s=["q"],
                inputs_c=None,
                expects_lat=data.data_size.value,
                not_expects_c=["ERROR"],
            )
            self.result_datasets[dataset_name] = result_dataset

            self.logStep("删除进程")
            self.base_kill(
                nodes=self.nodes,
                executor=self.executor,
                run_dir=self.run_dir,
                cmd_s=server_command,
                cmd_c=client_command,
            )

        self.logStep("校验数据集结果")
        self.check_dataset_result(self.result_datasets)
