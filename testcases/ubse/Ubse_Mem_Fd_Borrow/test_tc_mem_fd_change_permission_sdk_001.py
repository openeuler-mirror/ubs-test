import pytest
import libs.core.user_ops as user_ops
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemFdChangePermissionSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_fd_change_permission_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口改变fd远端内存permission信息成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
        P3.已存在用户test_user，组test_group
    TestStep:
        S1.调用ubse_mem_fd_create接口创建fd形态的远端内存，传入参数owner=NULL,记录返回的memids，memid_cnt
        S2.调用ubse_mem_fd_permission接口改变fd远端内存，传入参数owner={test_user, test_group, 0}，检查是否更改成功
        S3.检查/dev下的obmm_shmdev文件权限是否正确
    ExpectedResult:
        E1.内存创建成功
        E2.更改成功
        E3.文件权限正确
    """

    def setup_method(self):

        self.logStep("P1.ubse进程已启动")
        self.master_node, self.standby_node, _ = self.ubse_process_ops.return_nodes_by_all_role(self.nodes)

        self.logStep("P2.节点集群状态为ok")
        for node in self.nodes:
            node_status = self.get_node_memory_status(node.nodeId)
            self.assertEqual(node_status, "ok", "内存状态未就绪")
        self.clear_all_borrow_mem()

        self.logStep("P3.已存在用户test_user,组test_group")
        for node in self.nodes:
            user_ops.create_user(node, name="test_user", group="test_group")

    def teardown_method(self):

        self.logStep("清理内存")
        self.clear_all_borrow_mem()


    def test_tc_fd_change_permission_test_name_001(self):

        uid, gid = user_ops.get_uid_gid(self.master_node, username="test_user")
        self.logInfo(f"uid={uid} gid={gid} ")

        self.logStep("S1.调用ubse_mem_fd_create接口创建fd形态的远端内存，参数合法")
        name = "mem_fd_change_permission_sdk_001"
        res = self.mem_fd_borrow(self.nodes[0], name=name)

        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S2.调用ubse_mem_fd_permission接口改变fd远端内存，"
                     "传入参数owner={test_user, test_group, 0}，检查是否更改成功")
        res = self.mem_borrow_common(self.nodes[0], f"fd_permission {name} {uid} {gid} 777")

        self.logStep("E2.更改成功")
        self.assertTrue(res, "更改失败")

        self.logStep("S3.检查/dev下是否有S1中记录的memid_cnt数量的obmm_shmdev**文件（**为memidis数组中对应的元素），"
                     "其中用户和属组为S2中传入参数")
        res2 = self.check_obmm_files(self.nodes[0], 1, uid=uid, gid=gid, perms='777')

        self.logStep("E3.用户和属组为S2中传入参数")
        self.assertTrue(res2, "用户和属组不为S2中传入参数")
