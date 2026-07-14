import time


def apitest_update_page_flow_and_status(node, filepath, opt, uuid, hostname, numaId):
    params = {'opt': opt, 'uuid': uuid, 'hostname': hostname, 'numaId': numaId}
    node.run({'command': [f'touch {filepath}']})
    node.run({'command': [f'echo "from ubs_virt_agent_vm_migrate import update_page_flow_and_status" > {filepath}']})
    node.run({'command': [f"sed -i \"1a print(update_page_flow_and_status({params}))\" {filepath}"]})
    res = node.run({'command': [f'python {filepath}'], "timeout":300}).get('stdout')
    node.run({'command': [f'rm -f {filepath}']})
    return res

def apitest_ubs_mem_borrow_strategy(node, file, param):
    """
    功能：调用API接口获取内存借用策略
    参数：
        node: 节点
        file：创建文件的路径和名称
        param：传入API接口的参数
    返回值：API接口调用的结果
    """
    node.run({'command': [f'touch {file}']})
    node.run({'command': [f'echo "from ubs_virt_agent_fragmentation import ubs_mem_borrow_strategy" > {file}']})
    node.run({'command': [f"sed -i \"1a print(ubs_mem_borrow_strategy({param}))\" {file}"]})
    res = node.run({'command': [f'python {file}'], "timeout":300}).get('stdout')
    node.run({'command': [f'rm -f {file}']})
    return res


def apitest_ubs_mem_borrow_execute(node, file, param):
    """
    功能：调用API接口根据借用决策结果来执行内存借用
    参数：
        node: 节点
        file：创建文件的路径和名称
        param：传入API接口的参数
    返回值：API接口调用的结果
    """
    node.run({'command': [f'touch {file}']})
    node.run({'command': [f'echo "from ubs_virt_agent_fragmentation import ubs_mem_borrow_execute" > {file}']})
    node.run({'command': [f"sed -i \"1a print(ubs_mem_borrow_execute({param}))\" {file}"]})
    res = node.run({'command': [f'python {file}'], "timeout":300}).get('stdout')
    node.run({'command': [f'rm -f {file}']})
    return res


def apitest_ubs_mem_return(node, file, is_async: bool = False):
    """
    功能：调用API接口进行内存归还
    参数：
        node: 节点
        file：创建文件的路径和名称
        is_async: 是否异步归还
    返回值：API接口调用的结果
    """
    node.run({'command': [f'touch {file}']})
    node.run({'command': [f'echo "from ubs_virt_agent_fragmentation import ubs_mem_return" > {file}']})
    node.run({'command': [f"sed -i \"1a print(ubs_mem_return({is_async}))\" {file}"]})
    res = node.run({'command': [f'python {file}'], "timeout":300}).get('stdout')
    node.run({'command': [f'rm -f {file}']})
    return res


def apitest_ubs_case_conf_info(node, file):
    """
    功能：调用API接口获取当前虚拟化场景配置信息
    参数：
        node: 节点
        file：创建文件的路径和名称
    返回值：API接口调用的结果
    """
    node.run({'command': [f'touch {file}']})
    node.run({'command': [f'echo "from ubs_virt_agent_case_conf import ubs_case_conf_info" > {file}']})
    node.run({'command': [f"sed -i \"1a print(ubs_case_conf_info())\" {file}"]})
    res = node.run({'command': [f'python {file}'], "timeout":300}).get('stdout')
    node.run({'command': [f'rm -f {file}']})
    return res


def apitest_ubs_case_conf_set(node, file, param):
    """
    功能：调用API接口设置当前虚拟化场景配置
    参数：
        node: 节点
        file：创建文件的路径和名称
        param：传入API接口的参数
    返回值：API接口调用的结果
    """
    node.run({'command': [f'touch {file}']})
    node.run({'command': [f'echo "from ubs_virt_agent_case_conf import ubs_case_conf_set" > {file}']})
    node.run({'command': [f"sed -i \"1a print(ubs_case_conf_set({param}))\" {file}"]})
    res = node.run({'command': [f'python {file}'], "timeout":300}).get('stdout')
    node.run({'command': [f'rm -f {file}']})
    return res


def apitest_ubs_virt_vm_info_list(node, file):
    """
    功能：调用API接口查询节点虚拟机信息
    参数：
        node: 节点
        file：创建文件的路径和名称
    返回值：API接口调用的结果
    """
    node.run({'command': [f'touch {file}']})
    node.run({'command': [f'echo "from ubs_virt_agent_query import ubs_vm_info_list" > {file}']})
    node.run({'command': [f"sed -i \"1a print(ubs_vm_info_list())\" {file}"]})
    res = node.run({'command': [f'python {file}'], "timeout":300}).get('stdout')
    node.run({'command': [f'rm -f {file}']})
    return res


def apitest_ubs_virt_node_info_list(node, file):
    """
    功能：调用API接口查询节点信息
    参数：
        node: 节点
        file：创建文件的路径和名称
    返回值：API接口调用的结果
    """
    node.run({'command': [f'touch {file}']})
    node.run({'command': [f'echo "from ubs_virt_agent_query import ubs_node_info_list" > {file}']})
    node.run({'command': [f"sed -i \"1a print(ubs_node_info_list())\" {file}"]})
    res = node.run({'command': [f'python {file}'], "timeout":300}).get('stdout')
    node.run({'command': [f'rm -f {file}']})
    return res


def apitest_ubs_virt_delete_vm(node, vm_id, token):
    """
    功能：调用API接口删除节点虚拟机信息
    参数：
        node: 节点
        vm_id：虚机id
        token：token
    返回值：API接口调用的结果
    """
    command = (
        f'curl -X \'DELETE\' \'http://controller:7878/vm/{vm_id}\' -H "X-Auth-Token: {token}" -w "%{{http_code}}"'
    )
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res


def apitest_creation_hostname(node, vm_id, vm_allocated, token):
    """
    功能：调用API接口查询节点碎片场景虚拟机创建的hostname
    参数：
        node: 节点
        vm_id：虚机id
        vm_allocated：虚机大小
        token：token
    返回值：API接口调用的结果
    """
    command =(
        f'curl -X \'POST\' \'http://controller:7878/notOverAllocation/creation/hostname\' -d \''
        f'{{"vm_flavor": {{"uuid": "{vm_id}", "vm_allocated": {vm_allocated}}}, "host_numa_list": '
        f'[["controller", 0], ["computer01", 0], ["computer02", 0], ["computer03", 0], ["computer04", 0]]}}\'  '
        f'-H "X-Auth-Token: {token}"  -H "Content-Type: application/json"  -w \'%{{http_code}}\''
    )
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res


def apitest_creation_numa_info(node, vm_id, token):
    """
    功能：调用API接口查询节点碎片场景虚拟机创建的numa信息
    参数：
        node: 节点
        vm_id：虚机id
        token：token
    返回值：API接口调用的结果
    """
    command = (
        f'curl -X \'GET\' \'http://controller:7878/notOverAllocation/creation/numaInfo?uuid={vm_id}\' '
        f'-H "X-Auth-Token: {token}" -H "Content-Type: application/json" -w "%{{http_code}}"'
    )
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res


def wait_apitest_creation_numa_info(node, vm_id, token, key, timeout=600, sleep_time=10):
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        return_res = apitest_creation_numa_info(node, vm_id, token)
        if key in return_res:
            return return_res
        time.sleep(sleep_time)
    return False


def apitest_migration_numa_info(node, vm_id, token):
    """
    功能：调用API接口查询节点碎片场景虚拟机迁移的numa信息
    参数：
        node: 节点
        vm_id：虚机id
        token：token
    返回值：API接口调用的结果
    """
    command = (
        f'curl -X \'GET\' \'http://controller:7878/notOverAllocation/migration/numaInfo?uuid={vm_id}\' '
        f'-H "X-Auth-Token: {token}" -H "Content-Type: application/json" -w "%{{http_code}}"'
    )
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res


def wait_apitest_migration_numa_info(node, vm_id, token, key, timeout=600, sleep_time=10):
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        return_res = apitest_migration_numa_info(node, vm_id, token)
        if key in return_res:
            return return_res
        time.sleep(sleep_time)
    return False


def apitest_migration_hostname(node, vm_id, vm_allocated, token):
    """
    功能：调用API接口查询节点碎片场景虚拟机迁移的hostname
    参数：
        node: 节点
        vm_id：虚机id
        vm_allocated：虚机大小
        token：token
    返回值：API接口调用的结果
    """
    command =(
        f'curl -X \'POST\' \'http://controller:7878/notOverAllocation/migration/hostname\' -d \''
        f'{{"vm_flavor": {{"uuid": "{vm_id}", "vm_allocated": {vm_allocated}}}, "host_numa_list": '
        f'[["controller", 0], ["computer01", 0], ["computer02", 0], ["computer03", 0], ["computer04", 0]]}}\'  '
        f'-H "X-Auth-Token: {token}"  -H "Content-Type: application/json"  -w \'%{{http_code}}\''
    )
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res


def apitest_ubs_scheduler_status(node, token):
    """
    功能：调用API接口查询UBS-Scheduler当前服务状态及场景(超分/碎片)
    参数：
        node: 节点
        token：token
    返回值：API接口调用的结果
    """
    command = f'curl -X \'GET\' \'http://controller:7878/status\' -H "X-Auth-Token: {token}"  -w "%{{http_code}}"'
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res

def apitest_vm_suspend(node, vm_id, token):
    """
    功能：调用API接口挂起虚拟机
    参数：
        node: 节点
        vm_id：虚机id
        token：token
    返回值：API接口调用的结果
    """
    command = (
        f'curl -X \'POST\' \'http://controller:7878/notOverAllocation/suspend\' '
        f'-d \'{{"uuid": "{vm_id}"}}\' '
        f'-H "X-Auth-Token: {token}"  '
        f'-H "Content-Type: application/json" '
        f'-w "%{{http_code}}"'
    )
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res


def apitest_vm_power_off(node, vm_id, token):
    """
    功能：调用API接口关闭虚拟机
    参数：
        node: 节点
        vm_id：虚机id
        token：token
    返回值：API接口调用的结果
    """
    command = (
        f'curl -X \'POST\' \'http://controller:7878/notOverAllocation/powerOff\' '
        f'-d \'{{"uuid": "{vm_id}"}}\' '
        f'-H "X-Auth-Token: {token}"  '
        f'-H "Content-Type: application/json" '
        f'-w "%{{http_code}}"'
    )
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res


def apitest_vm_resum(node, vm_id, vm_allocated, computer_name, token):
    """
    功能：调用API接口恢复虚拟机
    参数：
        node: 节点
        vm_id：虚机id
        vm_allocated：虚拟机大小
        computer_name：虚拟机所在节点的hostname
        token：token
    返回值：API接口调用的结果
    """
    command = (
        f'curl -X \'POST\' \'http://controller:7878/notOverAllocation/resume\' '
        f'-d \'{{"vm_flavor": {{"vm_allocated": {vm_allocated},"uuid": "{vm_id}", "remote_mem_size": 0}}, '
        f'"hostname": "{computer_name}", "src_numa_id": 0, "host_numa_list": [["{computer_name}", 0]]}}\' '
        f'-H "X-Auth-Token: {token}" '
        f'-H "Content-Type: application/json" '
        f'-w "%{{http_code}}"'
    )
    res = node.run({'command': [command], "timeout": 60}).get('stdout')
    return res