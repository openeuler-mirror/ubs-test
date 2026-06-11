"""
Migrated from legacy: memorypooling_vm_resource_collection_001
"""
import pytest
from libs.core.basecase.ubturbo.mempooling_basecase import MempoolingBaseCase
import libs.ubturbo.api.mempooling as mempooling_common
from libs.ubturbo.common import basic
import libs.ubturbo.api.libvirt as lv_api
import libs.ubturbo.api.mempooling_api as api
import re
from libs.ubturbo.hooks import hook_mem_pooling

@pytest.mark.smoke
@pytest.mark.mempooling
class TestMemorypoolingVmResourceCollection001(MempoolingBaseCase):
    """
    CaseNumber:
        memorypooling_vm_resource_collection_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        验证单虚机单NUMA基础信息采集与配置一致性
    PreCondition:

    TestStep:
        S1、查看节点一物理节点内存池大小，分配大页
            1）查看内存池大小：cat /sys/module/obmm/parameters/mempool_size
            2）环境配置为2numa 内存池16g时 节点一numa0分配10g大页：
            echo 5120 > /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages
        S2、节点一numa0上创建虚机A，虚机规格为1u2g，内存分配策略均为立即分配
        virsh create {vm}.xml
        S3、在节点一观察虚机进程、虚机内存信息、虚机配置信息，记录基础信息：物理节点id、物理节点hostName、虚机进程PID、虚拟机uuid、虚拟机name、虚机状态、cpu对应socketID、cpu对应的NumaId、虚机创建时间、虚机申请内存、虚机页大小、本地numaid、本地使用内存；具体查看命令如下:
            1）获取虚机的进程信息：ps aux | grep qemu
            2）查看虚机的内存分配情况：virsh dominfo {vm}
            3）查看虚机的XML配置：
            virsh dumpxml {vm}
            4）lscpu查看xml中虚机绑定的物理CPU对应的socketid信息和numaid信息
        S4、在节点一调用查询vm信息南向接口，获取以下信息：物理节点id、物理节点hostName、虚机进程PID、虚拟机uuid、虚拟机name、虚机状态、cpu对应socketID、cpu对应的NumaId、虚机创建时间、虚机申请内存、虚机页大小、本地numaid、本地使用内存、远端numaid
            curl --unix-socket /var/run/ubse/ubseAgentUds.socket -X GET "http://localhost/rest/rackagent/v1/matrix_virt/vmInfo" -w "%{http_code}"
        S5、校对S3和S4的信息的信息一致性
    ExpectedResult:
        E1、分配成功
        E2、创建虚机成功
        E3、记录查询到的信息
        E4、记录状态码和虚机信息
        E5、南向接口的状态码为200，且S3、S4的信息一致

    Author:
    h00889334
    """

    # No __init__ method - dependencies injected via fixture

    def setup_method(self):
        """Legacy: preTestCase"""
        mempooling_common.pre_test(self.nodemaster)

    def test_memorypooling_vm_resource_collection_001(self):
        """
        memorypooling_vm_resource_collection_001
        """

        self.logStep("S1、查看内存池大小, 环境配置为2numa, 内存池16g, 节点一numa0分配10g大页")
        ret1 = basic.run(self.nodemaster, "cat /sys/module/obmm/parameters/mempool_size").stdout.strip("\n")
        if ret1.endswith("G"):
            ret1 = ret1 + "B"
        if self.num_of_local_numas == 2:
            self.assertEqual(ret1, "16GB")
        elif self.num_of_local_numas == 4:
            self.assertEqual(ret1, "32GB")
        else:
            raise Exception("本地numa数不符合预期")
        ret2 = mempooling_common.alloc_hugePage_with_check(self.nodemaster, 0, 5120)
        self.assertEqual(ret2, True)
        self.logStep("E1、分配成功")

        self.logStep("S2、节点一numa0上创建虚机A，虚机规格为1u2g，内存分配策略均为立即分配")
        vm_name = api.create_vm_object(self.nodemaster, 'A').vm_name
        self.logStep("E2、创建虚机成功")

        self.logStep("S3、在节点一观察虚机进程、虚机内存信息、虚机配置信息，记录基础信息")
        vm_ground_truths = {}
        vm_ground_truths[vm_name] = {}
        # 物理节点hostName
        hostname = basic.run(self.nodemaster, "hostname").stdout.strip("\n")
        vm_ground_truths[vm_name]['hostname'] = hostname
        # 物理节点id
        vm_ground_truths[vm_name]['nodeId'] = mempooling_common.get_node_id_by_hostname(self.nodemaster, hostname)
        # 虚机进程PID
        vm_pid = lv_api.get_pid(self.nodemaster, vm_name)
        vm_ground_truths[vm_name]['pid'] = vm_pid
        # 虚拟机uuid,虚机状态,虚拟机name,虚机申请内存
        vm_dominfo = mempooling_common.get_vm_dominfo(self.nodemaster, vm_name)
        vm_ground_truths[vm_name]['uuid'] = vm_dominfo["UUID"]
        vm_ground_truths[vm_name]['name'] = vm_dominfo["Name"]
        vm_ground_truths[vm_name]['state'] = vm_dominfo["State"].upper()
        vm_ground_truths[vm_name]['maxMem'] = int(vm_dominfo["Max memory"].split()[0])

        # 虚机创建时间
        vm_create_time_str = basic.run(self.nodemaster, f"ps -o lstart -p {vm_pid}").stdout.split("\n")[1]
        vm_ground_truths[vm_name]['vmCreateTime'] = basic.run(self.nodemaster, f"date -d '{vm_create_time_str}' +%s 2>/dev/null").stdout.strip('\n')
        # 本地numaid、本地使用内存、页大小
        numa_maps_str = basic.run(self.nodemaster, f"cat /proc/{vm_pid}/numa_maps | grep libvirt").stdout.strip("\n")
        pattern = r'N(\d+)=(\d+).*kernelpagesize_kB=(\d+)'
        match = re.search(pattern, numa_maps_str)
        if match:
            vm_ground_truths[vm_name]['numaId'] = int(match.group(1))
            vm_ground_truths[vm_name]['socketId'] = mempooling_common.get_socketid(self.nodemaster, int(match.group(1)))
            vm_ground_truths[vm_name]['localNumaId'] = int(match.group(1))
            vm_ground_truths[vm_name]['localUsedMem'] = int(match.group(2)) * 2048
            vm_ground_truths[vm_name]['pageSize'] = int(match.group(3))
        else:
            raise Exception("虚机numa maps匹配不成功")
        # cpu对应socketID、NumaId
        vm_ground_truths[vm_name]['socketId'] = mempooling_common.get_socketid(self.nodemaster, vm_ground_truths[vm_name]['localNumaId'])

        self.logStep("E3、记录查询到的信息")

        self.logStep("S4、在节点一调用查询vm信息南向接口，获取以下信息")
        # raw_vm_info = basic.run(self.nodemaster, query_vm_infos, timeout=60).stdout.strip("\n")
        code, vm_info_dict = api.function_vm_info(self.nodemaster)
        self.assertEqual(code, 200, "虚机查询接口调用失败")
        vm_infos = {}
        tmp_vm_infos = vm_info_dict['vmDomainInfos']
        self.assertEqual(len(tmp_vm_infos), 1, '虚机数量有误，预期只有一个虚机')
        for vm_info in tmp_vm_infos:
            vm_infos[vm_name] = {}
            vm_infos[vm_name]['state'] = vm_info['state']
            vm_infos[vm_name]['hostname'] = vm_info['hostname']
            vm_infos[vm_name]['nodeId'] = vm_info['nodeId']
            vm_infos[vm_name]['name'] = vm_info['name']
            vm_infos[vm_name]['uuid'] = vm_info['uuid']
            vm_infos[vm_name]['pid'] = int(vm_info['pid'])
            vm_infos[vm_name]['vmCreateTime'] = vm_info['vmCreateTime']
            vm_infos[vm_name]['maxMem'] = int(vm_info['maxMem'])
            local_numa = None
            for numa in vm_info.get('numaInfo', []):
                if numa.get('isLocal') == "True":
                    local_numa = numa
                    break
            vm_infos[vm_name]['numaId'] = int(local_numa['numaId'])
            vm_infos[vm_name]['localNumaId'] = int(local_numa['numaId'])
            vm_infos[vm_name]['socketId'] = int(local_numa['socketId'])
            vm_infos[vm_name]['pageSize'] = int(local_numa['pageSize'])
            vm_infos[vm_name]['localUsedMem'] = int(local_numa['usedMem'])
        self.logStep("E4、记录状态码和虚机信息")

        self.logStep("S5、校对S3和S4的信息的信息一致性")
        fields = {'state', 'hostname', 'nodeId', 'name', 'uuid', 'pid', 'pageSize', 'vmCreateTime', 'maxMem', 'localNumaId', 'localUsedMem'}
        ret = mempooling_common.check_info(vm_ground_truths, vm_infos, vm_name, fields)
        self.assertEqual(ret, True, '信息不一致')
        self.logStep("S5、校对S3和S4的信息的信息一致性")

    def teardown_method(self):
        """Legacy: postTestCase"""
        mempooling_common.delete_all_vms(self.nodemaster)
        mempooling_common.post_test(self.nodes)

