import pytest

from libs.core.basecase.ubturbo.container_overcommit_basecase import ContainerOvercommitBaseCase
from libs.ubturbo.common import basic


@pytest.mark.smoke
class TestContainerOvercommitBorrowFuc001(ContainerOvercommitBaseCase):
    """
    CaseNumber:
        Container_Overcommit_Borrow_Fuc_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        借入方socket0-numa0，借用大小1G，借用1次，借出方socket0-numa0可借出内存充足，预期借用成功
    PreCondition:
        P1、各节点rackmanager（scbus）配置为容器超分场景且正常启动；
    TestStep:
        S1、Node0调用借用北向接口，借用1G内存，借入方socket0-numa0；
    ExpectedResult:
        E1、接口调用成功，Node0成功借用到1G内存；
    Author:
        txj
    """

    def setup_method(self):
        super().setup_method()
        self.logStep("P1、各节点rackmanager（scbus）配置为容器超分场景且正常启动；")

    @pytest.mark.case_info(level = 'P0', type = "Functional")
    def test_container_overcommit_borrow_fuc_001(self):
        node0 = self.nodes[0]
        self.src_numa = self.socket2numa[self.socket[0]][0]
        self.logStep("S1、Node0调用借用北向接口，借用1G内存，借入方socket0-numa0；")
        res, entry_list = self.borrow(
            exec_node=node0,
            src_node=self.nodes[0].slot_id,
            src_socket=self.socket[0],
            src_numa=self.src_numa,
            borrow_sizes_gib=[1],
        )

        self.assertNotEqual(len(entry_list), 0, "借用失败")
        self.src_remote_numa = entry_list[0].src_remote_numa

        self.logStep("E1、接口调用成功，Node0成功借用到1G内存；")
        basic.wait_until(
            condition_func=lambda: self.get_numa_info(
                self.nodes[0].slot_id, self.src_remote_numa, "MemTotal"
            )
            == 1024,
            timeout=60,
            timeout_callback=self.fail_callback,
            check_sep=10,
        )

    def teardown_method(self):
        exec_node = self.nodes[0] if self.nodes else None
        if exec_node:
            self.return_all_borrow(exec_node=exec_node, clear_account=True, numa_bind=True)
        super().teardown_method()
