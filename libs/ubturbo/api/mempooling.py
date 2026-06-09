# -*- coding: utf-8 -*-
import time
import datetime
import re
import os
import json
import ast
from libs.ubturbo.common import basic, file_transport, env
from libs.ubturbo.common import string_utils
import libs.ubturbo.api.system as system
import libs.ubturbo.api.numa as numa
import libs.ubturbo.api.docker as docker
import libs.ubturbo.api.os_reliability as os_reliability
import libs.ubturbo.api.rack_manager as rack_manager
from libs.ubturbo.api.system import is_path_exist, ls, rm
from libs.ubturbo.api.rack_manager import RACK_CONF_PATH, RACK_INSTALL_PATH
from libs.ubturbo.model import libvirt
from typing import Any, Dict, Optional, Tuple


payload = {
    "caseType": "memFragmentation",
    "overCommitment": 1.0
}
vm_set_memFragment = f"python3 /home/mempooling-test/sdk/call_virt.py call_set_caseconf '{json.dumps(payload)}'"
vm_mem_borrow_mode = '''python3 /home/mempooling-test/sdk/call_virt.py call_get_caseconf ""'''
VM_2U2G_1_CONFIG_FILE = "vm_redis_1.xml"
VM_2U2G_2_CONFIG_FILE = "vm_redis_2.xml"
VM_2U4G_3_CONFIG_FILE = "vm_redis_3.xml"
VM_1U2G_A_CONFIG_FILE = "mempooling-A-ub.xml"
VM_1U2G_B_CONFIG_FILE = "mempooling-B-ub.xml"
VM_1U2G_C_CONFIG_FILE = "mempooling-C-ub.xml"
VM_1U2G_D_CONFIG_FILE = "mempooling-D-ub.xml"
VM_1U2G_E_CONFIG_FILE = "mempooling-E-ub.xml"
VM_2U2G_A_CONFIG_FILE = "mempooling-A.xml"
VM_2U2G_B_CONFIG_FILE = "mempooling-B.xml"
VM_2U2G_C_CONFIG_FILE = "mempooling-C.xml"
VM_2U2G_D_CONFIG_FILE = "mempooling-D.xml"
RACK_RESTART_FILE = "shutdown.sh"
UBSE_RESTART_FILE = "restart_ubse.sh"
UBSE_CONF_FILE = "ubse_conf.sh"
IMAGE_INIT_FILE = "init_images.sh"
REMOTE_WORK_PATH = "/home/mempooling-test"
REMOTE_VM_XML_PATH = "/home/mempooling-test/xml/"
MP_PATH = os.path.join(file_transport.THIS_PROJECT_PATH, "resource/ubsrmrs/MemPooling/")
MEM_INFO_PATH = '/home/mempooling-test/mem_info/getAllBorrowInfo'
BORROW_1024_FILE = 'borrow_exe.sh'
WORK_PATH = '/home/mempooling-test/'
SDK_LOCAL_PATH = os.path.join(MP_PATH, "sdk/")
SDK_REMOTE_PATH = os.path.join(WORK_PATH, "sdk")


def upload_sh_files(node):
    file_transport.send2remote(node, MP_PATH + RACK_RESTART_FILE, RACK_INSTALL_PATH)
    file_transport.send2remote(node, MP_PATH + UBSE_RESTART_FILE, RACK_INSTALL_PATH)
    file_transport.send2remote(node, MP_PATH + UBSE_CONF_FILE, RACK_INSTALL_PATH)
    file_transport.send2remote(node, MP_PATH + IMAGE_INIT_FILE, REMOTE_WORK_PATH)
    file_transport.send2remote(node, MP_PATH + BORROW_1024_FILE, REMOTE_WORK_PATH)
    # 消除不同系统行尾对shell文件的影响
    basic.run(node, "yum install -y dos2unix")
    basic.run(node, f'cd {RACK_INSTALL_PATH}')
    basic.run(node, f"dos2unix {RACK_RESTART_FILE}")
    basic.run(node, f"dos2unix {UBSE_RESTART_FILE}")
    basic.run(node, f"dos2unix {UBSE_CONF_FILE}")
    basic.run(node, f'cd -')
    basic.run(node, f'cd {REMOTE_WORK_PATH}')
    basic.run(node, f"dos2unix {IMAGE_INIT_FILE}")
    basic.run(node, f"dos2unix {BORROW_1024_FILE}")
    basic.run(node, f'cd -')
    basic.logger.info(f"文件上传完毕")


def upload_vm_files(node):
    if env.get_env_type(node) == env.UB_simulation:
        basic.logger.info(f"上传xml文件：{MP_PATH + 'xml'}")
        file_transport.send2remote(node, MP_PATH + 'xml', REMOTE_WORK_PATH)
    elif env.get_env_type(node) == env.UB_hardware:
        basic.logger.info(f"上传xml文件：{MP_PATH + 'hardware_xml'}")
        file_transport.send2remote(node, MP_PATH + 'hardware_xml', REMOTE_WORK_PATH)
    basic.logger.info(f"文件上传完毕")


def upload_sdk_scripts(node):
    file_transport.send2remote(node, SDK_LOCAL_PATH + "call_virt.py", SDK_REMOTE_PATH)
    basic.run(node, f"ll {SDK_REMOTE_PATH}")


def uplode_restart_file(node):
    file_transport.send2remote(node, MP_PATH + UBSE_RESTART_FILE, RACK_INSTALL_PATH)


def save_error_log_for_failed_case(node, case_name):
    timestamp = int(time.time())
    log_name = f"{case_name}_{timestamp}_ubse"
    os_turbo_log_name = f"{case_name}_{timestamp}_osturbo"
    if not system.is_path_exist(node, f"/home/mempooling-test/log/{log_name}", is_folder=True):
        basic.run(node, "date")
        basic.logger.info(f"保存{log_name}日志")
        basic.run(node, f"cp -r /var/log/ubse /home/mempooling-test/log/{log_name}", timeout=30)
        basic.run(node, f"cp -r /var/log/ubturbo /home/mempooling-test/log/{os_turbo_log_name}", timeout=30)


def check_plugin_ready(node):
    ret = basic.run(node, "sudo -u ubse ubsectl display cluster")
    if ret.rc != 0:
        return False
    return True


def check_restart_success(node):
    ret = is_path_exist(node, "/var/log/ubse/mempooling_plugin.log")
    if ret:
        basic.logger.info(f"内存碎片插件加载成功！")
        return True
    else:
        return False


def check_clean_up(node):
    basic.logger.info(f"清空文件...")
    rm(node, "/var/lib/ubse/data/*")
    ret = ls(node, "/var/lib/ubse/data")
    if len(ret) != 0:
        return False
    else:
        return True


def get_borrowIds(node, filename):
    basic.logger.info(f"解析内存借用结果...")
    try:
        json_str = basic.run(node, f"cat {filename}").stdout.strip(string_utils.STR_ENTER)
        basic.logger.info(f"Json string:{json_str}")
        data = json.loads(json_str.strip(string_utils.STR_ENTER))
        borrow_ids = data["borrowIds"]
        if isinstance(borrow_ids, list):
            formatted_ids = [f'"{str(bid)}"' for bid in borrow_ids]
            result_str = ", ".join(formatted_ids)
        return result_str
    except FileNotFoundError:
        raise FileNotFoundError(f"文件 {filename} 未找到")
    except KeyError:
        raise KeyError("borrowIds 字段不存在于 JSON 文件中")


def get_node_memory_borrow_info(nodes, file_path="/home/mempooling-test/mem_info.json"):
    """
    查询完整的账本信息，返回borrowid列表
    :param nodes: 集群中所有的节点
    :param file_path: 账本信息存放的josn路径，默认值/home/mempooling-test/mem_info.json
    :return: 完整账本信息的borrowid列表/空列表
    """
    basic.logger.info("开始查询内存账本")
    borrows_list = []
    for node in nodes:
        basic.run(node, f"{MEM_INFO_PATH} > {file_path}")
        basic.wait_until(lambda: "borrows" in basic.run(node, f"cat {file_path}").stdout)
        borrows_list += json2dict(node, jsonfile_path=file_path)['borrows']
    borrowids = []
    for item in borrows_list:
        borrowids.append(item['name'])
    basic.logger.info(f"borrowid列表：{borrowids}")
    return borrowids


def restart_rack(node):
    basic.run(node, "sh " + RACK_CONF_PATH + RACK_RESTART_FILE, timeout=30)
    start_time = time.time()
    clean_up = False
    while not clean_up:
        clean_up = check_clean_up(node)
        end_time = time.time()
        if end_time - start_time > 300:
            basic.logger.error(f"清空文件等待超时")
            raise Exception(f"清空文件等待超时，timeout:{int(end_time - start_time)}")
        basic.logger.info(f"清空文件中，等待：{end_time - start_time} 秒")
        time.sleep(2)
    basic.run(node, "systemctl restart ubse.service", timeout=60)
    rack_on = False
    while not rack_on:
        rack_on = check_restart_success(node)
        end_time = time.time()
        if end_time - start_time > 400:
            basic.logger.error(f"rack重启等待超时")
            raise Exception(f"插件加载等待超时，timeout:{int(end_time - start_time)}")
        basic.logger.info(f"等待rack重启中，等待：{end_time - start_time} 秒")
        time.sleep(2)
    plugin_ready = False
    while not plugin_ready:
        plugin_ready = check_plugin_ready(node)
        end_time = time.time()
        if end_time - start_time > 500:
            basic.logger.error(f"插件加载等待超时")
            raise Exception(f"插件加载等待超时，timeout:{int(end_time - start_time)}")
        basic.logger.info(f"等待插件加载中，等待：{end_time - start_time} 秒")
        time.sleep(2)
    basic.logger.info(f"rack重启成功，共等待{end_time - start_time} 秒")


def check_memfree_finish(node):
    start_time = time.time()
    end_time = time.time()
    remote_numa_ready = False
    env_type = env.get_env_type(node)
    local_numa_counts = numa.get_numa_count_with_cpu(node)
    while not remote_numa_ready:
        numa_infos = get_numaInfos(node)
        if env_type == env.HCCS:
            for numa_info in numa_infos:
                if numa_info['name'] == 'Node 4' or numa_info['name'] == 'Node 5':
                    remote_memtotal = numa_info['MemTotal']
                    end_time = time.time()
                    if remote_memtotal > 0:
                        basic.logger.info(f"内存未归还完成，等待{end_time - start_time}秒 ")
                        remote_numa_ready = False
                        time.sleep(2)
                    else:
                        remote_numa_ready = True
        elif env_type == env.UB_simulation or env_type == env.UB_hardware:
            if len(numa_infos) != local_numa_counts:
                end_time = time.time()
                basic.logger.info(f"内存未归还完成，等待{end_time - start_time}秒 ")
                remote_numa_ready = False
                time.sleep(2)
            else:
                remote_numa_ready = True
        else:
            raise Exception("未知环境类型")

        if end_time - start_time > 200:
            basic.logger.error(f"内存未归还等待超时")
            timestamp = int(time.time())
            ubse_log_name = f"ubse_check_memfree_finish_timeout_{timestamp}"
            turbo_log_name = f"turbo_check_memfree_finish_timeout_{timestamp}"
            basic.run(node, f"cp -r /var/log/ubse /home/mempooling-test/log/{ubse_log_name}", timeout=30)
            basic.run(node, f"cp -r /var/log/ubturbo /home/mempooling-test/log/{turbo_log_name}", timeout=30)
            raise Exception(f"内存未归还等待超时，timeout:{int(end_time - start_time)}")


def free_hugePage_all_numa(node):
    start_time = time.time()
    for i in range(4):
        free_hugePage(node, i)
        ret = basic.run(node, f"cat /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/nr_hugepages",
                        timeout=120).stdout
        while int(ret):
            end_time = time.time()
            basic.run(node, f"numastat -vmc", timeout=30)
            basic.logger.info(f"等待大页清零中，等待：{end_time - start_time} 秒")
            basic.run(node,
                      f"echo {int(ret) + 1} > /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/nr_hugepages",
                      timeout=120)
            time.sleep(2)
            free_hugePage(node, i)
            ret = basic.run(node, f"cat /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/nr_hugepages",
                            timeout=120).stdout
            if (end_time - start_time > 60):
                basic.logger.error("有部分大页无法清零")
                break


def set_hugePage_all_numa(node, size=8192):
    for i in range(numa.get_numa_count(node)):
        # 分配16G大页
        basic.run(node, "echo 3 > /proc/sys/vm/drop_caches", timeout=120)
        set_cmd = f"echo {size} > /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/nr_hugepages"
        basic.run(node, set_cmd, timeout=60)


# 检查rack状态
def check_plugin_status(node):
    start_time = time.time()
    plugin_ready = False
    while not plugin_ready:
        plugin_ready = check_plugin_ready(node)
        end_time = time.time()
        if end_time - start_time > 180:
            basic.logger.error(f"验证插件等待超时")
            raise Exception(f"验证插件超时，timeout:{int(end_time - start_time)}")
        basic.logger.info(f"验证插件中，等待：{end_time - start_time} 秒")
        time.sleep(2)
    basic.logger.info(f"插件就绪，等待：{end_time - start_time} 秒")


# 测试前处理，包含检查rack状态，销毁虚机，清空大页
def pre_test(node):
    start_time = time.time()
    libvirt.TempVirtualMachine.clear_all(node)
    check_plugin_status(node)
    check_memfree_finish(node)
    if env.get_env_type(node) == env.HCCS:
        free_hugePage_all_numa(node)
    elif env.get_env_type(node) == env.UB_simulation:
        set_hugePage_all_numa(node)
    clean_config_file(node)
    end_time = time.time()
    basic.logger.info(f"测试前处理完成，共计 {end_time - start_time} 秒")


def post_test(nodes):
    time.sleep(2)
    return_mem(nodes)
    reset_anti_node(nodes)


def reset_anti_node(nodes):
    affinity_set = {}
    for i in range(len(nodes)):
        affinity_set[f"{i + 1}"] = []
    affinity_set_str = json.dumps(affinity_set)
    cmd = f"python3 /home/mempooling-test/sdk/call_virt.py call_anti_affinity '{affinity_set_str}'"
    for node in nodes:
        basic.run(node, cmd, timeout=120)


def read_numa_maps(node, file_path):
    line = basic.run(node, "cat {} | grep hugepages/libvirt/qemu".format(file_path)).stdout
    matchs = re.findall(r'N(\d+)=(\d+)', line)
    return len(matchs), matchs


def get_pid(node, vm_name):
    """通过匹配qemu进程的“guest=<vm_name>,”字段寻找虚拟机pid"""
    ret = system.find_process(node, f'qemu.*{vm_name},')
    if ret is None:
        basic.logger.error(f"未找到虚机{vm_name}对应进程")
    return ret


def xml_parse(node, fn_xml, xpath) -> str:
    """返回xpath解析xml文件结果的第一个"""
    return basic.run(node, f'xmllint --xpath "{fn_xml}" {xpath}').stdout.split(string_utils.STR_ENTER)[0]


def xml_parse_memory(node, xpath) -> int:
    """解析虚拟机内存规格"""
    return int(xml_parse(node, '//memory/text()', xpath))


def xml_parse_numaId(node, xpath) -> int:
    """解析虚拟机内存规格"""
    return int(xml_parse(node, 'string(//numatune/memory/@nodeset)', xpath))


def check_file_with_timeout(directory, filename, timeout):
    start_time = time.time()  # 获取当前时间
    while time.time() - start_time < timeout:  # 在超时内循环
        file_path = os.path.join(directory, filename)  # 拼接文件的完整路径
        if os.path.exists(file_path):  # 检查文件是否存在
            return True
        time.sleep(1)  # 每秒检查一次文件是否存在
    return False  # 超时未找到文件


def alloc_hugePage(node, numa_id, num):
    # 分配大页
    basic.run(node, 'timeout 55s echo 3 > /proc/sys/vm/drop_caches', timeout=120)
    command = f"timeout 55s echo {num} > /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages"
    basic.run(node, command, timeout=180)
    basic.run(node, 'numastat -cvm')
    return numa_id


def alloc_hugePage_with_check(node, numa_id, num):
    # 分配大页
    basic.run(node, "timeout 55s echo 3 > /proc/sys/vm/drop_caches", timeout=60)
    basic.run(node,
              f"timeout 55s echo {num} > /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages",
              timeout=60)
    res = basic.run(node, f"cat /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages",
                    timeout=60).stdout
    if int(res) != num:
        basic.logger.error(f"numa{numa_id} 分配大页{num}有误，当前大页{res}")
        return False
    basic.logger.info(f"numa{numa_id} 分配大页{num}成功，当前大页{res}")
    return True


def free_hugePage(node, numa_id):
    # 分配大页
    basic.run(node, "echo 3 > /proc/sys/vm/drop_caches", timeout=60)
    free_cmd = f"echo 0 > /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages"
    basic.run(node, free_cmd, timeout=60)

    return numa_id


def get_numaInfos(node, delete_numa_which_memtotal_is_0=True):
    """
    :param delete_numa_which_memtotal_is_0:当设置为True时，会从节点numa信息中删除memTotal=0的numa
    """
    # 获取节点numa信息
    res = basic.run(node, 'numastat -vmc').stdout
    lines = res.split('\n')
    start_flag = False
    pattern = r'Node \d+'
    numa_nodes = []
    match_attribute = ['MemFree', 'HugePages_Total', 'HugePages_Free', 'MemTotal']
    for line in lines:
        if "Node 0" in line:
            start_flag = True
            matches = re.findall(pattern, line)
            numa_nodes = [{"name": node_name} for node_name in matches]
            continue

        if not start_flag:
            continue

        for attribute in match_attribute:
            if attribute in line:
                values = line.split()
                for index in range(1, len(values) - 1):
                    numa_node = numa_nodes[index - 1]
                    numa_node[attribute] = int(values[index])
    if delete_numa_which_memtotal_is_0:
        for numa_node in numa_nodes:
            if numa_node['MemTotal'] == 0:
                numa_nodes.remove(numa_node)
    return numa_nodes


def parse_response(response):
    # 解析原始信息
    json_part, status_code_str = response.rsplit("}", 1)
    status_code = int(status_code_str.strip())
    json_data = json_part + '}'
    data = json.loads(json_data)
    return data, status_code


def check_info(golden, info, name, fields):
    for field in fields:
        try:
            golden_value = golden[name][field]
            info_value = info[name][field]
            # ==用于比对字符串，
            if golden_value == info_value or abs(float(golden_value) - float(info_value)) < float(golden_value)*0.001:
                basic.logger.info(f"match {name} {field}: {golden_value} == {info_value}")
            else:
                basic.logger.error(f"Mismatch found for {name} {field}: {golden_value} != {info_value}")
                return False
        except KeyError as e:
            basic.logger.error(f"KeyError: {e} not found in one of the dictionaries for field {field}")
            return False
    return True


def vm_destroy(node, vm_name):
    """销毁虚拟机"""
    basic.run(node, f'virsh destroy {vm_name}', timeout=60)
    get_all_vm_names(node, show_all=True)  # 检测虚拟机


def get_all_vm_names(node, show_all=True):
    """
    获取当前所有虚拟机名称
    :param node:
    :param show_all: 展示非运行状态虚拟机
    :return: 包含当前所有虚拟名称机的列表
    """
    cmd = 'virsh list'
    if show_all:
        cmd += ' --all'
    vm_info = basic.run(node, cmd).stdout
    vm_list = [i[0] for i in string_utils.get_table_content(vm_info, slice(2, -2), slice(1, 2))]
    basic.logger.info(f'当前虚拟机列表: {vm_list}')
    return vm_list


def delete_all_vms(node):
    """删除所有运行中的虚拟机"""
    basic.logger.info('删除所有虚拟机')
    for vm_name in get_all_vm_names(node):
        vm_destroy(node, vm_name)
        time.sleep(2)


def clean_config_file(node):
    system.rm(node, REMOTE_WORK_PATH + "/config")
    system.mkdir(node, REMOTE_WORK_PATH + "/config")


def reset_anti_affinity(nodes: list, master):
    """
    重置环境的节点反亲和性，会自动识别4P/8P节点，例：reset_anti_affinity(self.nodes)
    :param nodes: 节点列表
    :param master: 主节点
    """
    affinity_set = {}
    for i in range(len(nodes)):
        affinity_set[f"{i + 1}"] = []
    affinity_set_str = json.dumps(affinity_set)
    cmd = f"python3 /home/mempooling-test/sdk/call_virt.py call_anti_affinity '{affinity_set_str}'"
    for node in nodes:
        basic.run(node, cmd, timeout=120)


def json2dict(node, jsonfile_path='/home/mempooling-test/response.json'):
    """
    将服务器上的json文件转换成python字典
    """
    basic.run(node, "ll")
    json_str = basic.run(node, f"cat {jsonfile_path};echo").stdout
    json_dict = json.loads(json_str)
    return json_dict


def return_mem(nodes):
    mem_return_node0 = f"python3 /home/mempooling-test/sdk/call_virt.py call_mem_return '1'"
    mem_return_node1 = f"python3 /home/mempooling-test/sdk/call_virt.py call_mem_return '2'"
    basic.run(nodes[0], mem_return_node0, timeout=6000)
    basic.run(nodes[1], mem_return_node1, timeout=6000)


def parse_mem_mode_output(raw: str) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """
    解析 ubse 输出日志：
    - 倒数第二行：Python 字典字符串 -> json_dict
    - 倒数第一行：包含 3 位返回码，例如 200 -> ret_code
    """
    # 去掉空行，只保留非空行
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) < 2:
        # 格式不对
        return None, None

    # 倒数第二行：结果 dict
    json_line = lines[-2]
    # 倒数第一行：返回码
    ret_line = lines[-1]

    # 解析 dict（安全替代 eval）
    json_dict: Optional[Dict[str, Any]]
    try:
        obj = ast.literal_eval(json_line)
        json_dict = obj if isinstance(obj, dict) else None
    except (SyntaxError, ValueError):
        json_dict = None

    # 解析返回码：取最后一行中的 3 位数字
    m = re.search(r'(\d{3})', ret_line)
    ret_code: Optional[int] = int(m.group(1)) if m else None

    return json_dict, ret_code


def check_memborrow_mode(nodes: object) -> object:
    """
    通过vm接口检查借用场景
    """
    start_time = time.time()
    stop_time = time.time()
    fragment_mode = {}
    for idx, node in enumerate(nodes):
        while stop_time - start_time < 300:
            set_ret = basic.run(node, vm_set_memFragment, timeout=20).stdout
            set_ret_code = int([x for x in set_ret.splitlines() if x.strip()][-1])
            if set_ret_code != 200:
                time.sleep(2)
                stop_time = time.time()
                basic.logger.warn(f"node{idx} rack启动中，调用场景注入失败，等待 {stop_time - start_time}s")
                continue
            get_ret = basic.run(node, vm_mem_borrow_mode, timeout=20).stdout
            borrow_mode_dict, get_ret_code = parse_mem_mode_output(get_ret)
            if get_ret_code != 200:
                time.sleep(2)
                stop_time = time.time()
                basic.logger.warn(f"node{idx} rack启动中，调用场景查询失败，等待 {stop_time - start_time}s")
                continue
            if int(borrow_mode_dict['data']['overCommitment']) == 1:
                basic.logger.info(f"node{idx} 碎片模式, overCommitment={borrow_mode_dict['data']['overCommitment']}")
                fragment_mode[idx] = int(borrow_mode_dict['data']['overCommitment'])
                break
            else:
                basic.logger.warn(f"node{idx} 非碎片模式, overCommitment={borrow_mode_dict['data']['overCommitment']}")
                return False
    if len(fragment_mode) == len(nodes) and fragment_mode.get(0) == 1:
        basic.logger.info(f"集群以碎片模式启动成功")
        # 20251202 RMRS B021变更串讲会议结论：注入1.0成功后需要硬延时10s使场景切换生效
        time.sleep(10)
        return True
    else:
        basic.logger.error(f"集群未以碎片模式启动")
        return False


def restart_rack_no_delete_data(master, slave):
    """
    重启rack，不删除持久化数据
    """
    system.rm(master, "/var/lib/ubse/psk/*")
    basic.run(master, "ll /var/lib/ubse/psk/")
    system.rm(slave, "/var/lib/ubse/psk/*")
    basic.run(slave, "ll /var/lib/ubse/psk/")

    basic.run(slave, "systemctl stop ubse.service", timeout=300)
    basic.run(master, "systemctl stop ubse.service", timeout=300)

    basic.run(master, "systemctl restart ubse.service", timeout=120)
    basic.run(slave, "systemctl restart ubse.service", timeout=120)
    basic.run(master, "ll /var/lib/ubse/psk/")
    basic.run(slave, "ll /var/lib/ubse/psk/")


def execut_BMC_poweroff(node, msgld=''):
    """
    通过插入ko，模拟BMC下电事件
    """
    tool_path = os.path.join(file_transport.THIS_PROJECT_PATH, "resource/TestStub/Tools/")
    file_transport.send2remote(node, tool_path + "RA_mock", REMOTE_WORK_PATH)
    basic.run(node, f"cd {REMOTE_WORK_PATH}")
    basic.run(node, "chmod 777 RA_mock")
    if msgld == '':
        basic.run(node, "./RA_mock", timeout=300)
    else:
        basic.run(node, f"./RA_mock {msgld}", timeout=300)


def execut_memid_error(node, node_id, mem_id):
    """
    通过南向接口模拟memid级故障，需输入故障node id和mem id
    """
    cmd = f'curl --unix-socket "/var/run/ubse/ubseAgentUds.socket" "http://localhost/rest/rackagent/v1/memorypooling/pub_fault_event_memId?importMemId={mem_id}&importNodeId={node_id}" -w "%{{http_code}}"'
    ret = basic.run(node, cmd).stdout
    if int(ret[-3:]) != 200:
        basic.logger.error(f"模拟memid级故障失败，返回值{ret[-3:]}")


def check_log_events(nodemaster):
    # 获取初始时间并处理Result对象
    date_result = basic.run(nodemaster, 'date')
    date_str = date_result.stdout.strip().replace('CST', '').strip()
    initial_time = datetime.datetime.strptime(date_str, "%a %b %d %I:%M:%S %p %Y")  # 忽略时区信息

    for _ in range(30):  # 最多30次循环（30*10秒=300秒/5分钟）
        # 执行日志查询命令
        log_result = basic.run(nodemaster,
                               'cat -t /var/log/ubse/rackmem_manager.log | grep "Mem manager RackMemRegResourceAllocator end successful"')
        log_lines = log_result.stdout.splitlines()

        # 检查日志时间戳
        for line in log_lines:
            if not line.startswith('['):
                continue
            log_time_str = line[1:].split(']')[0]
            # 提取日期时间部分（忽略时区）
            datetime_part = ' '.join(log_time_str.split()[:2])  # 获取前三个分割部分
            try:
                log_time = datetime.datetime.strptime(datetime_part, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                continue  # 跳过格式不正确的日志行

            if log_time > initial_time:
                return f"主备切换完成"

        time.sleep(10)

    return "五分钟内未发现符合条件的日志条目"


def check_numa_total_mem(node, numa_id, expect_mem):
    """
    检查节点特定numa的MemTotal内存是否等于预设值，不等时抛出异常，单位MB
    例： check_numa_total_mem(node, 4, 512)
    """
    numa_infos = get_numaInfos(node)
    if not any(numa_info['name'] == f'Node {numa_id}' and numa_info['MemTotal'] == expect_mem
               for numa_info in numa_infos):
        raise Exception(f"numa{numa_id} free内存检查失败")


def check_vm_mem_in_numa(node, pid, numa_id):
    """
    检查特定虚机在特定numa上是否占用内存，未占用时抛出异常
    例： check_numa_total_mem(node, 24520, 4)
    :param pid: 待查询虚机进程号
    :param numa_id: 带检测numa id
    """
    basic.run(node, f"numastat -p {pid}")
    res = basic.run(node, f"numastat -p {pid} | grep Huge | awk '{{print ${numa_id + 2}}}' ").stdout
    huge = int(float(res.strip(string_utils.STR_ENTER)))
    if huge == 0:
        raise Exception(f"虚机{pid}未占用numa{numa_id}内存")


def check_vm_valid(node, vm_ip, timewait=60):
    """
    检查虚机是否可以正常ping通，在timeout时间段内反复尝试，若超时仍不能正常ping通则抛出异常;
    """
    basic.wait_until(condition_func=lambda: basic.run(node, f"ping -c 5 {vm_ip}").rc == 0,
                     check_sep=15, timeout=timewait, expect_times=1)
    ret = basic.run(node, f"ping -c 5 {vm_ip}").rc
    if ret != 0:
        raise Exception(f"{vm_ip}对应虚机无法访问")


def get_socketid(node, numa_id):
    """
        获取传入的numa_id对应的真实socketid,以对应numa的第一个cpu编号去读取文件
        :param node
        :param numa_id:需要获取真实socketid的numa的id，示例：0/1/2/3
        :return:返回numa_id对应的真实socketid，示例：36
    """
    cpuid = -1
    cpuset = numa.get_numa_cpuset(node, numa_id)
    cpuid = cpuset.split('-')[0]

    if cpuid == -1:
        raise Exception("未获取到传入numa的cpuid,传入numaid：" + numa_id)
    ret = basic.run(node, f"cat /sys/devices/system/cpu/cpu{cpuid}/topology/physical_package_id", timeout=120)
    if ret.rc != 0:
        raise Exception(f"cat /sys/devices/system/cpu/cpu{cpuid}/topology/physical_package_id失败：{ret.stderr}")
    return ret.stdout.split(string_utils.STR_ENTER)[0]


def node_to_num(num_id):
    if num_id in [0, 1, 2, 3] or num_id in ["0", "1", "2", "3"]:
        node_dict = {"Node0": "1", "Node1": "2", "Node2": "3", "Node3": "4"}
        return node_dict.get(f"Node{num_id}")
    else:
        return num_id


def wait_for_urma_22(nodes, timeout_minutes=15, interval_seconds=5) -> bool:
    """
    循环检查各节点的urma设备，直到加载完成或等待超时
    :param nodes: 节点列表
    :param timeout_minutes: 最大等待时间（分钟）
    :param interval_seconds: 每次轮询间隔（秒）
    :return: bool -> (各节点urma设备是否加载完成)
    """
    start_time = time.time()
    times = 0
    if env.get_env_type(nodes[0]) == env.UB_simulation:
        num_of_urma_bonding = 23
    else:
        num_of_urma_bonding = 15

    def check_urma_22():
        nonlocal times
        times += 1
        basic.logger.info(f"这是第{times}次循环")
        num_of_nodes = 0
        for node in nodes:
            result = basic.run(node, "urma_admin show", timeout=300)
            if result.stdout is None or result.rc != 0:
                basic.logger.info(f"[{node}] 查询失败")
            lines = [line.strip() for line in result.stdout.strip().splitlines()]
            # 只保留包含 urma或bonding_dev_0 的数据行
            data_lines = [line for line in lines if 'udma' in line or 'bonding_dev_0' in line]
            basic.logger.info(f"{data_lines}")
            if len(data_lines) == num_of_urma_bonding:
                num_of_nodes += 1

        if num_of_nodes == len(nodes):
            basic.logger.info("各节点urma设备、bonding_dev_0设备已加载完成")
            return True
        else:
            basic.logger.info("各节点urma设备、bonding_dev_0设备未加载完成")
            if time.time() - start_time > timeout_minutes * 60:
                raise Exception("等待超时，各节点urma设备未加载完成")
            return False

    return basic.wait_until(check_urma_22, timeout=timeout_minutes * 60, check_sep=interval_seconds,
                            msg='检查环境上各节点的urma设备、bonding_dev_0设备是否加载完成') > 0


def wait_ub_recover(node, timeout: int = 30 * 60):
    node.waitForReboot(waitForShutdown=False, timeout=timeout)

    def confirm_sys_ready():
        res = basic.run(node, 'systemd-analyze', timeout=20)
        if 'Startup finished in' in res.stdout:
            basic.logger.info(res.stdout)
            return True
        return False

    # 保证auto-config等操作完成
    basic.wait_until(confirm_sys_ready, check_sep=20, timeout=timeout)


def recover_ub_status(host_node,
                      ub_node_list,
                      container_name: str = 'qemu-ub',
                      stop_cmd: str = 'sh -c "bash /workdir/scripts/stop.sh"',
                      start_cmd: str = 'sh -c "bash /workdir/scripts/start.sh -n 4 --extra-disk=0-3:sata:1:500 --ram=128:numa:2,8  --extra-nic=1 --mem-ipc=2 --tcg-accel --2die --mesh-type=1"',
                      timeout: int = 30 * 60):
    docker.exec_out_of_container(host_node, container_name, stop_cmd)
    basic.wait_until(lambda: int(docker.exec_out_of_container(host_node, container_name,
                                                              'ps -ef | grep qemu-system-aarch64 | wc -l').stdout.strip()) == 0,
                     timeout=1300)
    basic.logger.info(f"仿真环境已完成停止")
    docker.exec_out_of_container(host_node, container_name, start_cmd)
    for node in ub_node_list:
        wait_ub_recover(node, timeout=15 * 60)


def real_bmc_poweroff(node, port):
    """
    真实bmc下电执行
    """
    os_reliability.ub_graceful_shutdown(node, qmp_port=port)
    return True


def update_rackmanager_conf(node, group_value, provider_value, timeout=300):
    # 构造修改命令：如果已有就替换，否则追加
    script_path = f"{RACK_INSTALL_PATH}/{UBSE_CONF_FILE}"
    cmd = f"sh {script_path} {group_value} {provider_value}"
    return basic.run(node, cmd, timeout=timeout)


def restart_rack_with_ReconfigureConf(nodes: list, group_value: str, provider_value: str):
    """
    修改配置文件/etc/ubse/ubse.conf中的配置项group、provider，原先存在该配置则替换，否则添加，并重启ubse，重启之后等待所有节点上线
    :param nodes: 节点列表
    :param group_value: group更新值，数据类型str
    :param provider_value: provider更新值，数据类型str
    """
    for node in nodes:
        if update_rackmanager_conf(node, group_value, provider_value).rc != 0:
            raise Exception("节点修改conf文件失败！")
    # 重启ubse
    rack_manager.restart_rack_no_delete_data_8p(nodes)
    success, master = rack_manager.wait_for_master_consistency(nodes, timeout_minutes=20, interval_seconds=10)
    if success:
        basic.logger.info(f"一致成功，master节点是 {master}")
    else:
        raise Exception(f"10分钟内主节点未一致")


def get_node_id_by_hostname(node, hostname, timeout=240):
    """
    查寻ubse主节点
    """
    pattern = r'\(([^)]+)\)'
    ret = basic.run(node, f"sudo -u ubse ubsectl display cluster | grep {hostname}", timeout=timeout).stdout.strip("\n")
    match = re.search(pattern, ret)
    if match:
        node_id = match.group(1)
        return node_id
    else:
        return None


def get_vm_dominfo(node, vm_name):
    ret = basic.run(node, f"virsh dominfo {vm_name}").stdout.split('\n')
    dominfo_dict = {}
    for line in ret:
        line = line.strip()
        if not line:
            continue
        parts = line.split(':', 1)
        if len(parts) != 2:
            continue
        key = parts[0].strip()
        value = parts[1].strip()
        dominfo_dict[key] = value
        basic.logger.info(f"key = {key}, value = {value}")
    return dominfo_dict


def getHugePageTotal(node, numa_id) -> int:
    """
    通过系统文件获取特定numaid大页总数量
    :param node:
    :param numa_id: 要查询的numa id
    :return: 返回string，大页数量，失败返回-1
    """
    cmd = f"cat /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages"
    ret = basic.run(node, cmd, timeout=120).stdout.strip(string_utils.STR_ENTER)
    if ret is not None:
        return int(ret)
    basic.logger.error(f"获取numa{numa_id}大页总数量失败")
    return -1
