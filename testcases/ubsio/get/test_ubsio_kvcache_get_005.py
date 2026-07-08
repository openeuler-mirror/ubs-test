from libs.core.basecase.ubsio.dfc_basecase import DFCBaseCase
from libs.ubsio import DOCKER_NAME, get_file_name, put_file_name


class TestUbsioKvcacheGet005(DFCBaseCase):
    """
    CaseNumber:
        UBSIO_KVcache_Get_005
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        对同一对象多次读取
    PreCondition:
        P1.boostio+falcon进程启动成功
        P2.pythonclient端初始化成功
    TestStep:
        S1.生成key、value,长度为满足约束的随机长度
        S2.调用put传入正确的key、value
        S3.调用100次get传入key、value查询
    ExpectedResult:
        E1.生成随机长度满足约束
        E2.回显返回0(put成功)
        E3.100次查询结果均和put写入一致
    Design Description:

    Author:
        None
    """

    def setup_method(self):
        self.script_name = "script_UBSIO_KVcache_Get_005.py"
        self.clear_mem_disk()

        self.dfc_node_cli[0].clear_process()

        self.dfc_node_cli[0].delete_file(self.script_name)
        self.dfc_node_cli[0].send_scripts(self.script_name)

    def test_ubsio_kvcache_get_005(self):
        self.logStep("S1.生成key、value,长度为满足约束的随机长度")
        self.logStep("S2.调用put传入正确的key、value")
        self.logStep("S3.调用100次get传入key、value查询")
        self.logStep(f"运行脚本{self.script_name}，执行S1-S6的步骤")
        put_result = self.dfc_kv_cli[0].Execute_Python_Scripts(
            self.script_name, f"{put_file_name} {get_file_name}"
        )
        self.logStep("E1.生成随机长度满足约束")
        self.logStep("E2.回显返回0(put成功)")
        self.logStep("E3.100次查询结果均和put写入一致")
        self.assertEqual(
            put_result[0],
            "脚本执行成功",
            f"调用脚本{self.script_name}，执行失败，结果为：{put_result}",
        )

    def teardown_method(self):
        self.dfc_node_cli[0].clear_process()
