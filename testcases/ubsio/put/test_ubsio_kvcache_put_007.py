from libs.core.basecase.ubsio.dfc_basecase import DFCBaseCase


class TestUbsioKvcachePut007(DFCBaseCase):
    """
    CaseNumber:
        UBSIO_KVcache_Put_007
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        调用put传入key、value长度为0
    PreCondition:
        P1.boostio+falcon进程启动成功
        P2.pythonclient端初始化成功
    TestStep:
        分别生成1、2、1000、16384组key、value，长度为满足约束的随机长度，执行：
        S1.调用batch put传入key列表、value列表
        S2.调用batch get 传入key列表、value列表查询
    ExpectedResult:
        E1.回显返回0(batch put成功)
        E2.batch get查询结果和put写入一致
    Design Description:

    Author:
        None
    """

    def setup_method(self):
        self.script_name = "single_batch_put_random_kv.py"
        self.batch_num_dict = {1: 1, 2: 1, 100: 10, 256: 15}
        self.clear_mem_disk()

        self.dfc_node_cli[0].clear_process()
        self.dfc_node_cli[0].delete_file(self.script_name)
        self.dfc_node_cli[0].send_scripts(self.script_name)

    def test_ubsio_kvcache_put_007(self):
        self.logStep("运行脚本" + self.script_name)
        for put_num, wait_time in self.batch_num_dict.items():
            self.logStep(f"传入{put_num}组key、value，执行batch put和batch get")
            put_result = self.dfc_kv_cli[0].Execute_Python_Scripts(
                self.script_name, f"{put_num} put_value.txt get_value.txt", wait_time
            )
            self.assertEqual(put_result[0], "脚本执行成功", f"调用脚本失败，批量数为{put_num}")

    def teardown_method(self):
        self.dfc_node_cli[0].clear_process()
