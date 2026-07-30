import time

import pytest

from libs.core.basecase.ubturbo.container_overcommit_basecase import ContainerOvercommitBaseCase


@pytest.mark.smoke
class TestContainerOvercommitReturnFuc001(ContainerOvercommitBaseCase):
    """
    CaseNumber:
        Container_Overcommit_Return_Fuc_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        不绑定numa场景，3个borrowid，无待排除进程号，借用内存均未使用，调用归还接口，预期归还成功
    PreCondition:
        P1、各节点rackmanager（scbus）配置为容器超分场景且正常启动；
    TestStep:
        S1、Node0调用借用北向接口，借用3G内存[1G, 1G, 1G]，并保存borrowId；
        S2、调用归还接口，归还这3块borrowId；
    ExpectedResult:
        E1、借用成功
        E2、归还成功
    Author:
        txj
    """

    def setup_method(self):
        super().setup_method()
        self.logStep("P1、各节点rackmanager（scbus）配置为容器超分场景且正常启动；")

    @pytest.mark.case_info(level='P1', type="Functional")
    def test_container_overcommit_return_fuc_001(self):
        node0 = self.nodes[0]
        self.logStep("S1、Node0调用借用北向接口，借用3G内存[1G, 1G, 1G]，并保存borrowId；")
        res, entry_list = self.borrow(
            exec_node=node0, src_node=node0.slot_id, borrow_sizes_gib=[1, 1, 1]
        )
        self.assertNotEqual(len(entry_list), 0, "借用失败")
        self.borrow_remote_numa = entry_list[0].src_remote_numa
        self.logStep("E1、借用成功")
        remote_numa_list = set([])
        for entry in entry_list:
            remote_numa_list.add(entry.src_remote_numa)
        total_borrow = 0
        for remote_numa in remote_numa_list:
            total_borrow += self.get_numa_info(self.nodes[0].slot_id, remote_numa, "MemTotal")
        self.assertTrue(total_borrow == 3072, "借用大小不符合预期")

        self.logStep("S2、调用归还接口，归还这3块borrowId；")
        return_results = self.return_all_borrow(exec_node=node0)
        self.logStep("E2、归还成功")
        for i in return_results:
            self.assertEqual(self.judge_call_res(i), 0)
        time.sleep(10)
        self.assertEqual(
            self.get_numa_info(node0.slot_id, self.borrow_remote_numa, "MemTotal"), 0, "归还失败"
        )

    def teardown_method(self):
        exec_node = self.nodes[0] if self.nodes else None
        if exec_node:
            self.return_all_borrow(exec_node=exec_node, clear_account=True)
        super().teardown_method()
