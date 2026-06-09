"""
Migrated from legacy: memorypooling_node_resource_collection_001
"""
import pytest
from libs.core.basecase.ubturbo.mempooling_basecase import MempoolingBaseCase
import libs.ubturbo.api.mempooling as mempooling_common
from libs.ubturbo.common import basic
import libs.ubturbo.api.mempooling_api as api
from libs.ubturbo.hooks import hook_mem_pooling

@pytest.mark.smoke
@pytest.mark.mempooling
class TestMemorypoolingNodeResourceCollection001(MempoolingBaseCase):
    """
    CaseNumber:
        memorypooling_node_resource_collection_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        验证本地+远端单numa基础信息动态采集准确性
    PreCondition:

    TestStep:
        S1、查看节点一物理节点内存池大小，分配大页
            1）查看内存池大小：cat /sys/module/obmm/parameters/mempool_size
            2）环境配置为2numa 内存池16g时 节点一numa0分配10g大页，节点二numa0分配10g大页
            echo 5120 > /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages
            echo 5120 > /sys/devices/system/node/node1/hugepages/hugepages-2048kB/nr_hugepages
        S2、在节点一上调用内存借用策略函数，借用内存为256M，借入方为节点一的numa0，打印并检查函数出参
        S3、调用内存借用执行函数，借用内存为256M，借入方为节点一的numa0，借出方为节点二的numa0（根据实际情况选择与节点一的numa0同平面的numa）
        S4、在节点一通过numastat -cvm查看节点内存信息
        S5、在节点一调用节点信息采集南向接口
        S6、校对S4和S5的本地numa信息的一致性
    ExpectedResult:
        E1、分配成功
        E2、返回码200，预期策略返回从节点二的与节点一的numa0同平面的numa借用256M内存
        E3、返回码200
        E4、记录两个本地numa 和 一个远端numa的内存总量、空闲内存、大页总量、空闲大页数量
        E5、状态码为200，记录两个本地numa 和 一个远端numa的内存总量、空闲内存、大页总量、空闲大页数量
        E6、S4和S5记录的信息一致

    Author:
    h00889334
    """

    # No __init__ method - dependencies injected via fixture

    def setup_method(self):
        """Legacy: preTestCase"""
        hook_mem_pooling.mk_mp_work_dir(self.nodemaster)
        hook_mem_pooling.download_qcow(self.nodemaster)
        mempooling_common.pre_test(self.nodemaster)

    def test_memorypooling_node_resource_collection_001(self):
        """
        memorypooling_node_resource_collection_001
        """

        self.logStep("S1、环境配置为2numa 内存池16g时 节点一numa0分配10g大页，节点二numa0分配10g大页")
        ret = basic.run(self.nodemaster, "cat /sys/module/obmm/parameters/mempool_size").stdout.strip("\n")
        if ret.endswith("G"):
            ret = ret + "B"
        if self.num_of_local_numas == 2:
            self.assertEqual(ret, "16GB")
        elif self.num_of_local_numas == 4:
            self.assertEqual(ret, "32GB")
        else:
            raise Exception("本地numa数不符合预期")
        ret = mempooling_common.alloc_hugePage_with_check(self.nodemaster, 0, 5120)
        ret |= mempooling_common.alloc_hugePage_with_check(self.nodeagent, 0, 5120)
        self.assertEqual(ret, True, "分大页失败")
        self.logStep("E1、分配成功")

        self.logStep("S2、在节点一上调用内存借用策略函数，借用内存为256M，借入方为节点一的numa0，打印并检查函数出参")
        ret = api.function_borrow_strategy(self.nodemaster, 0, mempooling_common.get_socketid(self.nodemaster, 0), 0,
                                           262144)
        self.assertEqual(ret, 200, "借用策略失败")
        borrow_strategy_response = api.parse_borrow_strategy_response(self.nodemaster, ret)
        self.logStep("E2、返回码200，预期策略返回从节点二的与节点一的numa0同平面的numa借用256M内存")

        self.logStep("S3、调用内存借用执行函数，借用内存为256M，借入方为节点一的numa0，借出方为节点二的numa0（根据实际情况选择与节点一的numa0同平面的numa）")
        ret = api.function_borrow_execute(self.nodemaster, borrow_strategy_response)
        self.assertEqual(ret, 200, "借用执行失败")
        borrowids, presentNumaId = api.parse_borrow_execute_response_full(self.nodemaster, ret)
        remote_numa_id_x = presentNumaId[0]
        self.logStep("E3、返回码200")

        self.logStep("S4、在节点一通过numastat -cvm查看节点内存信息")
        basic.run(self.nodemaster, "numastat -cvm")
        tmp_numa_ground_truths = mempooling_common.get_numaInfos(self.nodemaster)
        numa_ground_truths = {}
        numa_list = []
        for truth in tmp_numa_ground_truths:
            numa_ground_truths[truth['name']] = truth
            numa_list.append(truth['name'])
        self.logStep("E4、记录两个本地numa 和 一个远端numa的内存总量、空闲内存、大页总量、空闲大页数量")

        self.logStep("S5、在节点一调用节点信息采集南向接口")
        code, raw_numa_json = api.function_node_info(self.nodemaster)
        self.assertEqual(code, 200, "调用numa查询接口失败")
        tmp_numa_infos = raw_numa_json['numaInfos']
        self.assertEqual(len(tmp_numa_infos), 1 + self.num_of_local_numas, "numa查询结果不符预期")
        numa_infos = {}
        for numa_info in tmp_numa_infos:
            numaId = "Node " + numa_info['metaData'][0]['numaId']
            numa_infos[numaId] = {}
            numa_infos[numaId]['MemFree'] = int(numa_info['metaData'][0]['memFree']) / 1024
            numa_infos[numaId]['MemTotal'] = int(numa_info['metaData'][0]['memTotal']) / 1024
            huge_pages_total = 0
            huge_pages_free = 0
            numa_huge_page_info = numa_info['metaData'][0].get('numaHugePageInfo', [])
            for hp in numa_huge_page_info:
                if hp.get('pageSize') == "2048":
                    huge_pages_total = int(hp.get('hugePageTotal', 0)) * 2
                    huge_pages_free = int(hp.get('hugePageFree', 0)) * 2
                    break
            numa_infos[numaId]['HugePages_Total'] = huge_pages_total
            numa_infos[numaId]['HugePages_Free'] = huge_pages_free
        self.logStep("E5、状态码为200，记录两个本地numa 和 一个远端numa的内存总量、空闲内存、大页总量、空闲大页数量")

        self.logStep("S5、校对S4和S5的本地numa信息的一致性")
        fields = {'MemFree', 'MemTotal', 'HugePages_Total', 'HugePages_Free' }
        for id in numa_list:
            ret = mempooling_common.check_info(numa_ground_truths, numa_infos, id, fields)
            self.assertTrue(ret, "numa信息不一致")
        self.logStep("S5、S4和S5记录的信息一致")

    def teardown_method(self):
        """Legacy: postTestCase"""
        mempooling_common.post_test(self.nodes)

