from libs.core.basecase.ubsio.dfc_basecase import DFCBaseCase
from libs.ubsio import get_file_name, put_file_name


class TestUbsiokvcacheDelete001(DFCBaseCase):
    """
    CaseNumber:
        UBSIO_KVcache_Delete_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        删除已经put的对象
    PreCondition:
        P1.boostio+falcon进程启动成功
        P2.pythonclient端初始化成功
    TestStep:
        S1.生成key、value,长度为满足约束的随机长度
        S2.调用put传入正确的key、value；调用get传入key、value查询
        S3.调用S2写入的key、value；再次调用get接口查询是否删除干净
    ExpectedResult:
        E1.生成随机长度满足约束
        E2.回显返回0(put成功)；get查询结果和put写入一致
        E3.删除成功；get删除失败，删除干净
    Design Description:

    Author:
        None
    """

    def setup_method(self):
        self.script_name = "script_UBSIO_KVcache_Delete_001.py"
        self.clear_mem_disk()

        self.dfc_node_cli[0].clear_process()

        self.dfc_node_cli[0].delete_file(self.script_name)
        self.dfc_node_cli[0].send_scripts(self.script_name)

    def test_ubsio_kvcache_delete_001(self):
        self.logStep("运行脚本" + self.script_name)
        put_result = self.dfc_kv_cli[0].Execute_Python_Scripts(self.script_name, f"{put_file_name} {get_file_name}")

        self.logStep("E1.生成随机长度满足约束")
        self.logStep("E2.回显返回0(put成功)；get查询结果和put写入一致")
        self.logStep("E3.删除成功；get删除失败，删除干净")
        self.assertEqual(
            put_result[0],
            "脚本执行成功",
            f"调用脚本{self.script_name}，执行失败，结果为：{put_result[0]}",
        )

    def teardown_method(self):
        self.dfc_node_cli[0].clear_process()
