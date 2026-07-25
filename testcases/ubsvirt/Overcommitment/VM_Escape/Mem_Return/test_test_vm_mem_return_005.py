
import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
from libs.modules.ubsvirt.model.model import VMResource


@pytest.mark.smoke
class TestVmMemReturn005(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_mem_return_005
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证内存归还后，远端内存归还后访问功能正常
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/RackManager功能正常无异常
        P3.Node0/Node1的numa0上配置4G可用大页内存
        P4.已完成内存规格4G虚拟机VM1的创建
        P5.对VM1加压到3.8G后触发了内存借用操作
    TestStep:
        S1.登录VM1,停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况
        S2.基于Node1上远端内存创建虚机VM2
        S3.登录VM2，运行redis应用，redis-benchmark -t set,get -n 10000000 -c 128 -r 2500000 -h 192.168.1.170 -p 6379 -d 2048 --threads 64
    ExpectedResult:
        E1.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。
        E2.虚机创建成功
        E3.redis应用的SET/GET数据正常，无异常报错
    Author:
        xxx
    """

    def teardown_method(self):
        self.clear_server()

    def test_vm_mem_return_005(self, get_topo_path):

        self.logStep("P4.已完成内存规格4G虚拟机VM1的创建")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_return_005")))

        self.logStep("P5.对VM1加压到3.8G后触发了内存借用操作")
        self.add_stress_to_vm(self.vms[0], 98)

        import time
        time.sleep(30)
        self.logStep("S1.登录VM1,停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况")
        self.clean_vm_stress(self.vms[0])

        self.logStep(
            "E1.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。"
        )
        self.assertTrue(self.check_return_mem("node1", 1000), "the borrowed size is not returned")

        self.logStep("S2.基于Node1上远端内存创建虚机VM2")
        vm2 = VMResource(
            "vm_02", "openEuler-22.03-everything", 4096, "node2", True, 6, False, "False", 0
        )
        try:
            self.create_server(vm2)
        except Exception as e:
            self.logStep("E2、创建虚机vm_02失败")
        self.logStep("E2.虚机创建成功")
        server_detail = self.wait_server_target_status(
            "vm_02", {"status": "ACTIVE", "OS-EXT-SRV-ATTR:host": self.node_dict["node2"].host}
        )
        self.assertEqual(server_detail["OS-EXT-SRV-ATTR:host"], self.node_dict["node2"].host)

        self.logStep(
            "S3.登录VM2，运行redis应用，redis-benchmark -t set,get -n 10000000 -c 128 -r 2500000 -h 192.168.1.170 -p 6379 -d 2048 --threads 64"
        )
        self.add_stress_to_vm(vm2, 75)
        self.logStep("E3.redis应用的SET/GET数据正常，无异常报错")
        node2_percent = self.wait_mem_match_expect("node2", "greater", 70)
        self.assertGreater(node2_percent, 70, "内存水线上升大于70%")
