#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025
import re
import time
from typing import List, Dict, Union
from libs.ubturbo.common import basic
from libs.ubturbo.common import string_utils
import libs.ubturbo.api.system as system


def xml_parse(node, fn_xml, xpath) -> str:
    """返回xpath解析xml文件结果的第一个"""
    return basic.run(node, f'xmllint --xpath "{xpath}" {fn_xml}').stdout.split(string_utils.STR_ENTER)[0]


def xml_parse_memory(node, fn_xml) -> int:
    """解析虚拟机内存规格"""
    return int(xml_parse(node, fn_xml, '//memory/text()'))


def xml_alter_memory(node, fn_xml: str, target_memory: int, unit: str = 'GiB'):
    """修改虚拟机内存规格"""
    basic.logger.info(f'修改虚拟机内存规格为{target_memory} {unit}')
    basic.run(
        node,
        rf"sed -i 's/<memory unit=[\"'\''].*[\"'\'']>.*</<memory unit='\''{unit}'\''>{target_memory}</g' {fn_xml}"
    )


def xml_alter_memnode(
        node,
        fn_xml: str,
        local_mem_numa_id: List[Union[int, str]] = None,
        remote_mem_numa_id: List[Union[int, str]] = None,
):
    """
    修改远近端内存配置
    示例：
        # 文件名：aaa.xml
        # 原配置：<memnode cellid='0' mode='strict' proportion='2000-node0:48-node2' />
        # 修改内容：指定本端使用3000MB的numa0，对端使用100MB的numa0
        xml_alter_memnode(node, 'aaa.xml', [3000, 0], [100， 0])
        # 修改后配置：<memnode cellid='0' mode='strict' proportion='3000-node0:100-node0' />
    :param node: 节点对象
    :param fn_xml: 虚拟机xml配置文件
    :param local_mem_numa_id: 近（本）端numa内存、numa编号的列表、字典
    :param remote_mem_numa_id: 远（对）端numa内存、numa编号的列表、字典
    :return:
    """
    basic.run(
        node,
        f'sed -i -E "s/(<memnode cellid=\'0\' mode=\'strict\' proportion=\')'
        '[0-9]+(-node)[0-9]+:[0-9]+(-node)[0-9]+(\'.*\\/>)/'
        rf'\1{local_mem_numa_id[0]}\2{local_mem_numa_id[1]}:'
        rf'{remote_mem_numa_id[0]}\3{remote_mem_numa_id[1]}\4/g" {fn_xml}'
    )


def xml_alter_cpu_num(node, fn_xml: str, target_cpu_config: Dict[int, int], emulatorpin_cpuset: str = None):
    """
    修改虚拟机配置中的cpu数和实际cpu映射
    前提条件：
        xml配置中必须包含/domain/cputune标签
        示例：
          <cputune>
            <vcpupin vcpu="0" cpuset="0" />
            <vcpupin vcpu="1" cpuset="1" />
          </cputune>

    :param node:
    :param fn_xml: 文件路径
    :param target_cpu_config: cpu映射 {vcpu编号: 宿主机cpu编号}
    :param emulatorpin_cpuset:
        /domain/cputune/emulatorpin QEMU模拟器进程的配置，影响性能。默认清除掉该配置，让系统自己决定。
        目前的问题：如果模板里没有这个配置，那么传入这个参数，也不会加上对应的配置
    :return:
    """
    basic.logger.info(f'修改虚拟机vcpu数量为{len(target_cpu_config)}')
    # 删除原有vcpu配置
    basic.run(node, f"sed -i '/<vcpupin.*\/>/d' {fn_xml}")
    # 增加vcpu配置
    cmd = r'sed -i "/<cputune>/a\\"'
    for index, (vcpu_index, host_cpu_index) in enumerate(target_cpu_config.items()):
        cmd += f'$\'\\n\'"<vcpupin vcpu=\\"{vcpu_index}\\" cpuset=\\"{host_cpu_index}\\" \\/>'
        if index + 1 < len(target_cpu_config):
            cmd += r'\\'
        cmd += '"'
    cmd += f' {fn_xml}'
    basic.run(node, cmd)

    # 修改其他vcpu数量相关配置
    # /domain/vcpu
    basic.logger.info('检查vcpu标签')
    if not basic.run(node, f'grep \'</vcpu>\' {fn_xml}').rc:
        basic.run(
            node,
            f'sed -i '
            f'\'s/\\(<vcpu.*>\\)[0-9]\\+\\(<\\/vcpu>\\)/\\1{len(target_cpu_config)}\\2/g\' '
            f'{fn_xml}'
        )
    # /domain/cpu/topology[@cores]
    if not basic.run(node, f'grep "<topology .*cores=" {fn_xml}').rc:
        basic.run(
            node,
            f'sed -i '
            f"'s/\\(<topology .*cores='\\''\\)[0-9]\\+\\('\\''.*\\/>\\)/\\1{len(target_cpu_config)}\\2/g' "
            f"{fn_xml}"
        )
    # /domain/cputune/emulatorpin
    if not basic.run(node, f'grep "<emulatorpin .*cpuset" {fn_xml}').rc:
        if emulatorpin_cpuset:
            basic.run(
                node,
                f'sed -i '
                f"'s/\\(<emulatorpin cpuset=\\)\\S\\+\\( \\/>\\)/\\1\"{emulatorpin_cpuset}\"\\2/g' "
                f'{fn_xml}'
            )
        else:
            # 清除对应配置
            basic.run(node, f"sed -i '/<emulatorpin.*\/>/d' {fn_xml}")


def xml_alter_cpu_numa_bind(node, fn_xml: str, numa_index: int):
    """

    :param node:
    :param fn_xml:
    :param numa_index:
    :return:
    """
    basic.run(
        node,
        f"sed -i 's/\\(<memory.*nodeset=\\).*\\(.*\\/>\\)/\\1'\\''{numa_index}'\\'' \\2/g' {fn_xml}"
    )


def xml_open_FPR(node, fn_xml):
    """修改xml文件，打开FPR特性"""
    return basic.run(
        node,
        rf"sed -i 's/model='\''virtio'\''>/model='\''virtio'\'' freePageReporting='\''on'\''>/g' {fn_xml}"
    )


def xml_close_FPR(node, fn_xml):
    basic.run(
        node,
        rf"sed -i 's/model='\''virtio'\'' freePageReporting='\''on'\''>/model='\''virtio'\''>/g' {fn_xml}"
    )


def xml_alter_mac(node, fn_xml: str, target_mac: str):
    """修改虚拟机mac地址"""
    return basic.run(node, f"sed -i 's/mac address=.*\\/>/mac address=\"{target_mac}\" \\/>/g' {fn_xml}")


def xml_alter_uuid(node, fn_xml: str, target_uuid: str):
    """修改虚拟机mac地址"""
    basic.run(node, f"sed -i 's/<uuid>.*<\\/uuid>/<uuid>{target_uuid}<\\/uuid>/g' {fn_xml}")


def xml_set_random_mac(node, fn_xml: str, macs: set = None) -> str:
    """
    修改xml中mac地址为随机
    :param node:
    :param fn_xml: xml文件路径
    :param macs: 已有物理地址，防止重复（重复会导致无法获取虚拟机ip）
    :return:
    """
    if macs is None:
        macs = set()
    basic.logger.info('检测mac')
    raw_mac = basic.run(node, f"grep 'mac address=' {fn_xml}").stdout.split('"')[1]
    # 仅修改最后两个字符
    while True:
        random_mac = raw_mac[:-2] + string_utils.generate_random_string(2, '0123456789ABCDEF')
        basic.logger.info(f'随机mac：{random_mac}')
        if random_mac not in macs:
            macs.add(random_mac)
            break
    xml_alter_mac(node, fn_xml, random_mac)
    return random_mac


def xml_set_random_uuid(node, fn_xml: str, uuids: set = None) -> str:
    """
    修改虚拟机xml文件中uuid，防止与已有uuid冲突
    :param node:
    :param fn_xml: xml文件路径
    :param uuids: 已有uuid，防止重复
    :return: 本次使用的uuid
    """
    if uuids is None:
        uuids = set()
    basic.logger.info('检测uuid')
    raw_uuid = basic.run(node, f"grep '<uuid>' {fn_xml}").stdout.split('<uuid>')[-1].split('</uuid>')[0]
    # 仅修改最后两个字符
    while True:
        random_uuid = raw_uuid[:-2] + string_utils.generate_random_string(2, '0123456789abcdef')
        basic.logger.info(f'随机uuid：{random_uuid}')
        if random_uuid not in uuids:
            uuids.add(random_uuid)
            break
    xml_alter_uuid(node, fn_xml, random_uuid)
    return random_uuid


def get_all_vm_names(node, show_all=False) -> List[str]:
    """
    获取当前所有虚拟机名称
    通过virsh list查找虚拟机名称，通过正则表达式捕获虚拟机名

    命令和回显示例：

    root@#>virsh list --all
     Id   Name           State
    ------------------------------
     2    mempooling-A   running
     3    mempooling-B   running
     4    mempooling-D   running
     5    mempooling-E   running
     6    mempooling-G   running
     7    mempooling-H   running
     8    mempooling-J   running
     9    mempooling-K   running
     30   mempooling-C   running

    root@#>

    :param node:
    :param show_all: 展示非运行状态虚拟机
    :return: 当前虚拟名称列表
    """
    cmd = 'virsh list'
    if show_all:
        cmd += ' --all'
    # 获取回显中的虚拟机名
    vm_names = re.findall(r' \d+\s+(\S+)\s+\S+', basic.run(node, cmd).stdout)

    basic.logger.info(f'当前虚拟机列表: {vm_names}')
    return vm_names


def vm_create(node, fn_xml, timeout=20) -> str:
    """
    创建虚拟机并返回虚拟机名称
    :param node:
    :param fn_xml: 虚拟机xml文件路径
    :param timeout: 超时时间
    :return: 虚拟机名称
    """
    res = basic.run(node, f'virsh create {fn_xml}', timeout=timeout)
    get_all_vm_names(node, show_all=True)  # 检测虚拟机
    if res.rc:
        raise Exception('虚拟机创建失败')

    return res.stdout.split("'")[1]


def vm_suspend(node, vm_name) -> basic.Result:
    """暂停虚拟机"""
    return basic.run(node, f'virsh suspend {vm_name}')


def vm_resume(node, vm_name) -> basic.Result:
    """恢复虚拟机"""
    return basic.run(node, f'virsh resume {vm_name}')


def vm_destroy(node, vm_name):
    """销毁虚拟机"""
    basic.run(node, f'virsh destroy {vm_name}')
    get_all_vm_names(node, show_all=True)  # 检测虚拟机


def delete_all_vms(node):
    """删除所有运行中的虚拟机"""
    basic.logger.info('删除所有虚拟机')
    for vm_name in get_all_vm_names(node):
        vm_destroy(node, vm_name)


def get_vm_ip(node, vm_name, timeout=60, sep=5, cmd_timeout=30) -> str:
    """
    获取虚拟机ip
    通过正则表达式获取

    回显示例:
    root@#>virsh domifaddr 虚拟机名
     Name       MAC address          Protocol     Address
    -------------------------------------------------------------------------------
     vnet5      xx:xx:xx:xx:e8:f0    ipv4         ip/24

    root@#>

    :param node:
    :param vm_name: 虚拟机名称
    :param timeout: 超时时间
    :param sep: 检查时间间隔
    :param cmd_timeout: 单次命令超时时间
    :return:
    """
    ip_list = []

    def try2get_vm_ip():
        nonlocal ip_list
        stdout = basic.run(node, f'virsh domifaddr {vm_name}', timeout=cmd_timeout).stdout
        ip_list = re.findall(r'(\S+)/', stdout)
        basic.logger.info(f'虚拟机IP表: {ip_list}')
        return bool(ip_list)

    basic.wait_until(try2get_vm_ip, check_sep=sep, timeout=timeout, msg='虚拟机ip')

    if not ip_list:
        raise Exception(f'获取虚拟机{vm_name} ip地址失败')

    vm_ip = ip_list[0]  # 默认取第一个ip
    basic.logger.info(f'虚拟机ip：{vm_ip}')
    return vm_ip


def get_pid(node, vm_name):
    """通过匹配qemu进程的“guest=<vm_name>,”字段寻找虚拟机pid"""
    return system.find_process(node, f'qemu.*{vm_name},')


def vm_get_default_network_status(node) -> bool:
    """
    获取虚拟机默认网络是否处于开启状态
    openstack开启时，该网络处于关闭状态
    关闭状态无法使用virsh命令创建虚拟机

    回显示例：
    关闭状态：
    virsh net-list --all
     Name      State    Autostart   Persistent
    --------------------------------------------
     default   inactive   yes         yes

    当状态为“开启”时，State列值为active。

    :param node:
    :return:
        True: 网络处于开启状态
        False: 网络处于关闭状态
    """
    return not re.findall(r'default\s+inactive\s+', basic.run(node, 'virsh net-list --all').stdout)


def vm_default_network_activate(node, check_status_before_change=True) -> Union[bool, None]:
    """
    确保默认网络激活
    :param node:
    :param check_status_before_change: 改变状态前检查状态，并发出日志
    :return: 历史遗留原因，这里返回值设为状态检查的结果
    """
    is_default_net_active = None
    if check_status_before_change:
        is_default_net_active = vm_get_default_network_status(node)

    if not is_default_net_active:
        basic.logger.info('激活default网络')
        basic.run(node, 'virsh net-start default')
    else:
        basic.logger.info('已激活default网络，跳过激活命令')

    return is_default_net_active


def vm_default_network_destroy(node):
    return basic.run(node, 'virsh net-destroy default')


def update_vm_config_text(tree, tag, text):
    """
    更新虚机xml里标签下的text
    """
    tags = tree.findall(f".//{tag}")
    for tag in tags:
        tag.text = text


def update_vm_config_attribute(tree, tag, key, value):
    """
    更新虚机xml里标签的属性
    """
    tags = tree.findall(f".//{tag}")
    for tag in tags:
        if f'{key}' in tag.attrib:
            tag.attrib[f'{key}'] = f'{value}'


def vm_va_get(
        node,
        pid,
):
    """
    查询虚机的va
    :param node:创建虚机节点
    :param pid:虚机的pid
    """
    cmd = f"cat /proc/{pid}/numa_maps | grep huge"
    ret = basic.run(node, cmd).stdout.split()
    return ret[0]
