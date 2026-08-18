import pytest

from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemNumaCreateByLink001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_numa_create_by_link_001
    RunLevel:
        Level 0
    EnvType:
        2+1组网
    CaseName:
        验证cli指定链路创建numa形态的远端内存成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.计算节点执行ubsectl display topo -t cpu 查询链路
        S2.在计算节点1和计算节点2执行ubsectl create memory -t numa -l xxx -s 1024M -n test进行内存借用，link覆盖所有链路
        S3.调用ubsectl display memory -t borrow_detail，查询账本是否正确
        S4.对上述内存进行读写，查看是否成功
        S5.归还内存
    ExpectedResult:
        E1.查询成功
        E2.内存借用成功
        E3.账本数量正确
        E4.内存读写成功
        E5.内存归还成功
    """

    def setup_method(self):
        self.logStep("P1.ubse进程已启动")
        self.master_node, self.standby_node, self.agents = self.ubse_process_ops.return_nodes_by_all_role(self.nodes)
        self.logStep("P2.节点集群状态为ok")
        for node in self.nodes:
            node_status = self.get_node_memory_status(node.nodeId)
            self.assertEqual(node_status, "ok", "内存状态未就绪")
        self.clear_all_borrow_mem()

    def teardown_method(self):

        self.logStep("清理内存")
        self.clear_all_borrow_mem()

    def test_tc_mem_numa_create_by_link_001(self):
        self.logStep("S1.计算节点执行ubsectl display topo -t cpu 查询链路")
        links = self.cli_api.display_topo_cpu(self.standby_node)

        self.logStep("E1.查询成功")
        self.assertNotEqual(len(links),0, '查询链路失败或链路为空')

        self.logStep("S2.在计算节点1和计算节点2执行ubsectl create memory -t numa -l xxx -s 1024M -n test进行内存借用，link覆盖所有链路")
        for i, link in enumerate(links):
            if link.get('link-id') in [None, '', '-']:
                continue
            borrow_node = [node for node in self.nodes if node.nodeId == link.get('link-id')[0]][0]
            name = f"numa_create_by_link_001_{i}"
            res, _ = self.cli_api.create_numa_memory(borrow_node, name, '1G', link.get('link-id'))
            self.assertTrue(res)
            self.logStep("E2.内存借用成功")

            self.logStep("S3.调用ubsectl display memory -t borrow_detail，查询账本是否正确")
            accounts = self.cli_api.display_mem_borrow_detail(self.master_node)
            account = [e for e in accounts if name == (e.get('name') or '')]
            self.logStep("E3.账本数量正确")
            self.assertEqual(len(account), 1)

            self.logStep("S4.对上述内存进行读写，查看是否成功")
            numa_id = account[0].get('handle', '-').split(',')[0]
            cmd = [f"numa_alloc {numa_id} 64", f"numa_write {numa_id} 0x0 aaaa", f"numa_read {numa_id} 0x0 2",
                   f"numa_free {numa_id}"]
            res = self.mem_tool_exec_multi_cmds(borrow_node, cmd)
            self.assertIn("Write data: aaaa", res[1], "写入内存失败")
            self.assertIn("aaaa", res[2], "读取内存失败")
            self.logStep("E4.内存读写成功")

            self.logStep("S5.归还内存")
            self.cli_api.delete_memory(borrow_node, account[0].get('name'))
            accounts = self.cli_api.display_mem_borrow_detail(self.master_node)
            res = [e for e in accounts if name == (e.get('name') or '')]
            self.logStep("E5.内存归还成功")
            self.assertEqual(len(res), 0)
