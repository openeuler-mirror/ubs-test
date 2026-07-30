import pytest

from libs.core.basecase.ubturbo.container_overcommit_basecase import (
    ContainerOvercommitBaseCase,
    check_container,
    delete_container,
    start_container,
)
from libs.ubturbo.common import basic


@pytest.mark.smoke
class TestContainerOvercommitMigrateFuc002(ContainerOvercommitBaseCase):
    """
    CaseNumber:
        Container_Overcommit_Migrate_Fuc_002
    RunLevel:
        Level T
    EnvType:

    CaseName:
        不绑定numa场景，smap迁出比例25%，2个容器运行内存型业务进程，借用1块内存上线至remote_numa0，调用迁出接口预期占用
    PreCondition:
        P1、各节点rackmanager（scbus）配置为容器超分场景且正常启动；
    TestStep:
        S1、创建2个容器，记为container0~1；
        S2、container0~1内各自运行stress-ng，2G压力，绑定numa0；
        S3、借用1G内存并记录borrowid；
        S4、调用迁出接口，将所有容器的加压进程号作为参数传入，迁出至借用内存；
        S5、调用归还接口，归还借用内存；
    ExpectedResult:
        E1、创建POD及容器成功；
        E2、加压成功；
        E3、内存借用成功，内存上线至远端numa；
        E4、迁出成功，1024M借用内存投入使用量大于800M；
        E5、迁回成功，归还成功；
    Author:
        txj
    """

    def setup_method(self):
        super().setup_method()
        self.logStep("P1、各节点rackmanager（scbus）配置为容器超分场景且正常启动；")

    @pytest.mark.case_info(level='P1', type="Functional")
    def test_container_overcommit_migrate_fuc_002(self):
        node1 = self.nodes[0]
        self.src_numa = self.socket2numa[self.socket[0]][0]
        self.logStep("S1、创建2个容器，记为container0~1；")
        self.container_map = start_container(node1, 2)

        self.logStep("E1、创建POD及容器成功；")
        self.assertEqual(
            check_container(node=node1, container_map=self.container_map), 0, "创建POD及容器失败"
        )

        self.logStep("S2、container0~1内各自运行stress-ng，2G压力，绑定numa0；")
        stress_pids = []
        for i in range(1, 3):
            container_id = self.container_map[f"container{i}"].id
            stress_value = "2G"
            stress_pids += self.stress_in_container(node1, container_id, stress_value, self.src_numa)

        self.logStep("E2、加压成功；")
        self.assertNotEqual(len(stress_pids), 0, "加压失败，未获取到加压进程pid")

        self.logStep("S3、借用1G内存并记录borrowid；")
        res, entry_list = self.borrow(
            exec_node=node1, src_node=self.nodes[0].slot_id, borrow_sizes_gib=[1]
        )

        self.src_remote_numa = entry_list[0].src_remote_numa

        self.logStep("E3、内存借用成功，内存上线至远端numa；")
        basic.wait_until(
            condition_func=lambda: self.get_numa_info(
                self.nodes[0].slot_id, self.src_remote_numa, "MemTotal"
            )
            == 1024,
            timeout=60,
            timeout_callback=self.fail_callback,
            check_sep=10,
        )

        self.logStep("S4、调用迁出接口，将所有容器的加压进程号作为参数传入，迁出至借用内存；")
        self.migrate(exec_node=node1, entry_list=entry_list, pids=stress_pids, ratio=25)

        self.logStep("E4、迁出成功，1024M借用内存投入使用量大于800M；")
        basic.wait_until(
            condition_func=lambda: self.get_numa_info(
                self.nodes[0].slot_id, self.src_remote_numa, "MemUsed"
            )
            > 800,
            timeout=60,
            timeout_callback=self.fail_callback,
            check_sep=10,
        )

        self.logStep("S5、调用归还接口，归还借用内存；")
        return_results = self.return_all_borrow(node1)

        self.logStep("E5、迁回成功，归还成功；")
        for i in return_results:
            self.assertEqual(self.judge_call_res(i), 0)
        basic.wait_until(
            condition_func=lambda: self.get_numa_info(
                node1.slot_id, entry_list[0].src_remote_numa, "MemTotal"
            )
            == 0,
            timeout=30,
            timeout_callback=self.fail_callback,
            check_sep=5,
        )

    def teardown_method(self):
        exec_node = self.nodes[0] if self.nodes else None
        if exec_node:
            self.return_all_borrow(exec_node=exec_node, clear_account=True)
        delete_container(getattr(self, 'container_map', None))
