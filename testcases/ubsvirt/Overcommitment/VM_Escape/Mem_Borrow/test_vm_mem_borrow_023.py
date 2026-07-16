"""
Migrated from legacy: test_vm_mem_borrow_023
"""

import time

import pytest
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase

VM_PLUGIN_LOG = "/var/log/ubse/virt_agent_plugin.log"


@pytest.mark.smoke
class TestVmMemBorrow023(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_mem_borrow_023
    RunLevel:
        Level 1
    EnvType:
        None
    CaseName:
        验证16G虚拟机加压触发OOM紧急借用后，内存借用成功
    PreCondition:
        P1、环境中存在2个及以上节点
        P2、OpenStack/RackManager功能正常无异常
        P3、Node0上配置16G可用大页内存
        P4、已完成不同节点内存规格16G虚拟机VM1的创建
    TestStep:
        S1、登录VM1，执行加压命令对VM1加压，使得内存压力接近100%，查看水位线告警、借用策略、借入借出点水位线告警变化情况
        S2、水位线降低后，加压使得内存压力接近100%，再次触发内存借用
    ExpectedResult:
        E1、存在水位线告警，存在OOM事件，触发内存借用操作，借用1G，水位线降低，内存借出点水线会上涨
        E2、存在水位线告警，预期借用收益1G，借用账本借用量2G，触发内存借用操作，水位线会降低，内存借出点水线会上涨
    Author:
        fq
    """

    def teardown_method(self):
        self.clear_server()
        client.oom_service_status_change(self.master, "stop")

    def test_vm_mem_borrow_023(self, get_topo_path):

        sysSentry_status, xalarmd_status = client.oom_service_status_change(self.master, "start")
        assert sysSentry_status == "running", "启动sysSentry失败"
        assert xalarmd_status == "running", "启动xalarmd失败"

        self.logStep("P4、已完成不同节点内存规格16G虚拟机VM1的创建")
        self.vms = self.prepare_topo(str(get_topo_path("test_vm_mem_borrow_023")))

        self.logStep("S1、登录虚拟机对虚拟机进行加压至95%，借用1G内存")
        res = client.echo_hugePage(self.node_dict["node2"].ssh_node, 0, 512)
        assert res, "大页配置失败"
        start_time = client.get_date_timestamp(self.controller)
        self.add_stress_to_vm(self.vms[0], 100)
        node1_percent = self.wait_mem_match_expect("node1", "greater", 99, 900)
        assert node1_percent > 99, f"node1 waterline is {node1_percent}, not greater than 99"
        time.sleep(20)
        res = client.echo_hugePage(self.node_dict["node2"].ssh_node, 0, 10000)
        assert res, "大页配置失败"
        time.sleep(30)
        self.logStep("E1、存在水位线告警，存在OOM事件，触发内存借用操作，借用1G，水位线降低，内存借出点水线会上涨")
        log = client.get_assign_log(self.master, VM_PLUGIN_LOG, start_time, '"oomEventFlag":1')
        assert "oom" in log, "没有OOM触发决策的日志"
        assert self.check_borrowed_numa_size("node1", 1000, 2048 * 0.9), "the borrowed size is not 1024M"
