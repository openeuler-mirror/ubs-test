from libs.core.basecase.ubsio.dfc_basecase import DFCBaseCase


class TestUbsioKvcachePut_014(DFCBaseCase):
    """
    CaseNumber:
        UBSIO_KVcache_Put_014
    """

    def setup_method(self):
        self.script_name = "script_UBSIO_KVcache_Put_014.py"
        self.clear_mem_disk()

        self.dfc_node_cli[0].clear_process()

        self.dfc_node_cli[0].delete_file(self.script_name)
        self.dfc_node_cli[0].send_scripts(self.script_name)

    def test_ubsio_kvcache_put_014(self):
        self.logStep("运行脚本" + self.script_name)
        put_result = self.dfc_kv_cli[0].Execute_Python_Scripts(
            self.script_name, "put_value.txt get_value.txt"
        )
        self.assertEqual(put_result[0], "脚本执行成功", "调用脚本失败")

    def teardown_method(self):
        self.dfc_node_cli[0].clear_process()
