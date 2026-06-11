# -*- coding: utf-8 -*-
import logging
import re
import uuid
import os

import time

CI_RESOURCE_PATH = "/home/ci_home/migrate/vmimage/resource/"
CI_DOWN_PATH = "/home/ci_home/migrate/vmimage/vmimage/resource/"
VM_2U2G_CONFIG_FILE = "automation_ham_2U2G.xml"
VM_2U16G_CONFIG_FILE = "automation_ham_2U16G.xml"


def set_qemu_config(node_src, node_dst):
    """
    配置两端的qemu.conf
    """
    node_src.run({
        'command': ["""echo enable_dmmu = '"on"' > /etc/libvirt/qemu.conf"""],
        'waitstr': '#'
    })
    node_src.run({
        'command': ["cat /home/ham_automation/qemu_ham.conf >> /etc/libvirt/qemu.conf"],
        'waitstr': '#'
    })

    node_dst.run({
        'command': ["""echo enable_dmmu = '"on"' > /etc/libvirt/qemu.conf"""],
        'waitstr': '#'
    })
    node_dst.run({
        'command': ["cat /home/ham_automation/qemu_ham.conf >> /etc/libvirt/qemu.conf"],
        'waitstr': '#'
    })


def set_src_libvritd_config(node_src):
    """
    配置源端的libvirtd.conf
    """
    node_src.run({
        'command': ["cat /home/ham_automation/libvirtd_source.conf > /etc/libvirt/libvirtd.conf"],
        'waitstr': '#'
    })


def set_dst_libvritd_config(node_dst):
    """
    配置目的端的libvirtd.conf
    """
    node_dst.run({
        'command': ["cat /home/ham_automation/libvirtd_dst.conf > /etc/libvirt/libvirtd.conf"],
        'waitstr': '#'
    })


def set_src_libvirtd(node_src):
    """
    源端重启libvirt
    """
    node_src.run({
        'command': [
            """sed -i 's/^Environment=LIBVIRTD_ARGS=.*/Environment=LIBVIRTD_ARGS="--listen"/g' /usr/lib/systemd/system/libvirtd.service"""],
        'waitstr': '#'
    })

    node_src.run({
        'command': [
            "systemctl mask libvirtd.socket libvirtd-ro.socket libvirtd-admin.socket libvirtd-tcp.socket libvirtd-tls.socket"],
        'waitstr': '#'
    })

    node_src.run({
        'command': ["systemctl daemon-reload"],
        'waitstr': '#'
    })

    node_src.run({
        'command': ["systemctl restart libvirtd"],
        'waitstr': '#'
    })


def set_dst_libvirtd(node_dst):
    """
    目的端端重启libvirt
    """
    node_dst.run({
        'command': [
            """sed -i 's/^Environment=LIBVIRTD_ARGS=.*/Environment=LIBVIRTD_ARGS="--listen"/g' /usr/lib/systemd/system/libvirtd.service"""],
        'waitstr': '#'
    })

    node_dst.run({
        'command': [
            "systemctl mask libvirtd.socket libvirtd-ro.socket libvirtd-admin.socket libvirtd-tcp.socket libvirtd-tls.socket"],
        'waitstr': '#'
    })

    node_dst.run({
        'command': ["systemctl daemon-reload"],
        'waitstr': '#'
    })

    node_dst.run({
        'command': ["systemctl restart libvirtd"],
        'waitstr': '#'
    })


def allocate_src_hugepages_2048kB(node_src):
    """
    源端分配大页
    """
    hugepages_count_63 = node_src.run({
        'command': ["cat /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"],
        'waitstr': '#'
    })['stdout'].split('\r\n')[0]
    if int(hugepages_count_63) <= 1024:
        node_src.run({
            'command': ["echo 20000 >/sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"],
            'waitstr': '#'
        })


def allocate_dst_hugepages_2048kB(node_dst):
    """
    目的端端分配大页
    """
    hugepages_count_64 = node_dst.run({
        'command': ["cat /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"],
        'waitstr': '#'
    })['stdout'].split('\r\n')[0]
    if int(hugepages_count_64) <= 1024:
        node_dst.run({
            'command': ["echo 20000 >/sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"],
            'waitstr': '#'
        })


def analysis_migrate_log(node, vm_name):
    """
    解析最近一次虚机迁移日志，获取性能数据
    """
    migrate_log = node.run({
        'command': ["tail -n 1000 /var/log/libvirt/qemu/" + vm_name + ".log"],
        'waitstr': '#'
    })['stdout'].split('\r\n')
    migrate_data = {}
    for index in range(len(migrate_log)):
        line = migrate_log[index]
        if line.startswith("""qmp hcom resource initialization and connection"""):
            migrate_data["down_time"] = int(migrate_log[index + 3].split(' ')[2].split('(')[0])
            migrate_data["setup_time"] = int(migrate_log[index + 4].split(' ')[3].split('(')[0])
            migrate_data["total_time"] = int(migrate_log[index + 5].split(' ')[3].split('(')[0])
            index += 12

    return migrate_data


def analysis_dp_migrate_log(node, vm_name):
    """
    解析最近一次device-parallel虚机迁移日志，获取性能数据
    """
    migrate_log = node.run({
        'command': ["tail -n 1000 /var/log/libvirt/qemu/" + vm_name + ".log"],
        'waitstr': '#'
    })['stdout'].split('\r\n')
    migrate_data = {}
    for index in range(len(migrate_log)):
        line = migrate_log[index]
        if line.startswith("""qmp hcom resource initialization and connection"""):
            migrate_data["down_time"] = int(migrate_log[index + 3].split(' ')[2].split('(')[0])
            migrate_data["setup_time"] = int(migrate_log[index + 4].split(' ')[3].split('(')[0])
            migrate_data["total_time"] = int(migrate_log[index + 5].split(' ')[3].split('(')[0])
            index += 12

    return migrate_data


def create_vm(node, vm_name, vm_config):
    work_dir = CI_RESOURCE_PATH + vm_name + "/"
    node.run({
        'command': ["rm -rf  " + work_dir],
        'waitstr': '#'
    })
    node.run({'command': ["mkdir -p " + work_dir], 'waitstr': '#'})
    node.run({'command': ["cp --force " + CI_DOWN_PATH + vm_config + " " + work_dir + vm_config],
              'waitstr': '#'})

    node.run({'command': ["yes | cp  -rf " + CI_DOWN_PATH + "normal_qcow" + " " + CI_RESOURCE_PATH],
              'waitstr': '#'})
    # 修改创建虚机名字
    command = """sed -i "s/<name>.*<\/name>/<name>""" + vm_name + """<\/name>/" """ + work_dir + vm_config
    node.run({'command': [command], 'waitstr': '#', 'timeout': 0.5})
    # 修改创建虚机uuid
    vm_uuid = str(uuid.uuid1())
    command = """sed -i "s/<uuid>.*<\/uuid>/<uuid>""" + vm_uuid + """<\/uuid>/" """ + work_dir + vm_config
    node.run({'command': [command], 'waitstr': '#', 'timeout': 0.5})
    time.sleep(5)
    command_result = node.run({
        'command': ["virsh create " + work_dir + vm_config],
        'waitstr': '#'
    })
    vm_created = node.run({
        'command': ["virsh list | grep " + vm_name + " | wc -l"],
        'waitstr': '#'
    })['stdout'].split('\r\n')[0]

    return int(vm_created) > 0


def touch_file(node, vm_name, vm_config):
    work_dir = CI_RESOURCE_PATH + vm_name + "/"
    image_path = node.run({'command': ["""sed -n '/<source file=/p' """ + work_dir + vm_config],
                           'waitstr': '#', 'timeout': 0.5})['stdout'].split('\r\n')[0].split('"')[1]
    image_name = os.path.basename(image_path)
    node.run({'command': ["touch -c " + work_dir + image_name], 'waitstr': '#'})


def refresh_hugePage(node, numa_id: int, numa_num: int):
    numa_infos = get_numaInfo(node)
    numa_node = next((numa for numa in numa_infos if numa['name'] == 'Node ' + str(numa_id)), None)
    if not numa_node:
        return False

    if int(numa_node['HugePages_Total']) == numa_num * 2:
        return True

    if int(numa_node['MemFree']) + int(numa_node['HugePages_Total']) < numa_num * 2:
        return False

    ret = echo_hugePage(node, numa_id, numa_num)
    return ret.get('rc') != 0


def get_numaInfo(node):
    res = node.run({'command': ['numastat -vmc']}).get('stdout').rstrip('root@#>')
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
                    numa_node[attribute] = values[index]
    return numa_nodes


def echo_hugePage(node, numa_id, num):
    # 变更大页前，刷新大页缓存
    node.run({'command': ['echo 3 > /proc/sys/vm/drop_caches'], "timeout": 60})
    command = f"echo {num} > /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages"
    return node.run({'command': [command]})


def migrate_vm(node, command):
    create_result = node.run({
        'command': [command],
        'waitstr': '#',
        "timeout": 2000
    })

    vm_migrated = node.run({
        'command': ["echo $?"],
        'waitstr': '#'
    })['stdout'].split('\r\n')[0]
    return vm_migrated == '0'


def vm_press(node):
    node.run({
        'command': [
            "sysbench --threads=6 --mysql-user=root --mysql-host=localhost --mysql-db=mig --tables=8 --time=1200 --rand-type=gaussian --report-interval=2 /usr/share/sysbench/oltp_read_write.lua run"],
        'waitstr': '#'
    })


def migrate_vm_ham(src_node, dst_node, vm_name, vm_config, params):
    command = "virsh migrate {} --live --p2p qemu+tcp://{}/system tcp://{}/system --verbose --unsafe" \
              " --xml {} --ldst --parallel".format(vm_name, dst_node.localIP, dst_node.localIP,
                                                   CI_RESOURCE_PATH + vm_name + "/" + vm_config)
    for param in params:
        command = command + " " + param
    return migrate_vm(src_node, command)


def migrate_vm_base(src_node, dst_node, vm_name, vm_config, params):
    command = "virsh migrate {} --live --p2p qemu+tcp://{}/system tcp://{}/system --verbose --unsafe" \
              " --xml {}".format(vm_name, dst_node.localIP, dst_node.localIP,
                                 CI_RESOURCE_PATH + vm_name + "/" + vm_config)
    for param in params:
        command = command + " " + param
    return migrate_vm(src_node, command)


def get_stdout(result, start_index: int = 0, end_index: int = None) -> str:
    if not result['stdout']:
        return ""
    return '\n'.join([x.strip() for x in result['stdout'].split('\n')][start_index:end_index])


def get_ub_ip(node):
    result = node.run({'command': ["ip a | grep ubl0"], 'waitstr': '#'})
    output = get_stdout(result)
    pattern = r"inet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"

    match = re.search(pattern, output)
    if match:
        ip_address = match.group(1)
        return ip_address
    else:
        logging.info("Error: Failed to get IP address")
        return None


def migrate_vm_qemu(src_node, dst_node, vm_name, params, is_hccs=False):
    dst_ub_ip = get_ub_ip(dst_node)
    command = "virsh migrate {} --p2p --live --unsafe --verbose --migrateuri hcom://{} --listen-address {}" \
              " qemu+tcp://{}/system --rdma-pin-all" \
        .format(vm_name, dst_node.localIP, dst_node.localIP, dst_node.localIP)
    command_ub = "virsh migrate {} --p2p --live --unsafe --verbose --migrateuri hcom://{} --listen-address {}" \
                 " qemu+tcp://{}/system --rdma-pin-all" \
        .format(vm_name, dst_ub_ip, dst_ub_ip, dst_ub_ip)
    for param in params:
        command = command + " " + param
        command_ub = command_ub + " " + param
    command_hccs = command + " --enable-hccs"
    if is_hccs:
        return migrate_vm(src_node, command_hccs)
    else:
        return migrate_vm(src_node, command_ub)


def migrate_vm_qemu_(src_node, dst_node, vm_name, is_onecopy=True, is_hccs=False):
    dst_ub_ip = get_ub_ip(dst_node)
    command_onecopy_hccs = f"virsh migrate --p2p --live --unsafe --migrateuri hcom://{dst_node.localIP} {vm_name} --listen-address {dst_node.localIP} qemu+tcp://{dst_node.localIP}/system --verbose --parallel --parallel-connections 2 --rdma-pin-all --onecopy --enable-hccs"
    command_itercopy_hccs = f"virsh migrate --p2p --live --unsafe --migrateuri hcom://{dst_node.localIP} {vm_name} --listen-address {dst_node.localIP} qemu+tcp://{dst_node.localIP}/system --verbose --parallel --parallel-connections 2 --rdma-pin-all --enable-hccs"
    command_onecopy = ("virsh migrate --p2p --live --unsafe --migrateuri hcom://{} {} --listen-address {} qemu+tcp://{"
                       "}/system --verbose --parallel --parallel-connections 2 --rdma-pin-all --onecopy").format(
        dst_ub_ip, vm_name, dst_ub_ip, dst_ub_ip)
    command_itercopy = ("virsh migrate --p2p --live --unsafe --migrateuri hcom://{} {} --listen-address {} "
                        "qemu+tcp://{}/system --verbose --parallel --parallel-connections 2 --rdma-pin-all").format(
        dst_ub_ip, vm_name, dst_ub_ip, dst_ub_ip)
    if is_onecopy and is_hccs:
        return migrate_vm(src_node, command_onecopy_hccs)
    elif is_onecopy and not is_hccs:
        return migrate_vm(src_node, command_onecopy)
    elif not is_onecopy and is_hccs:
        return migrate_vm(src_node, command_itercopy_hccs)
    else:
        return migrate_vm(src_node, command_itercopy)


def query_vm_running(node, vm_name):
    vm_count = node.run({
        'command': ["virsh list | grep " + vm_name + " | grep running | wc -l"],
        'waitstr': '#'
    })['stdout'].split('\r\n')[0]
    return int(vm_count) > 0


def destroy_vm(node, vm_name):
    node.run({
        'command': ["virsh destroy " + vm_name],
        'waitstr': '#'
    })


def clear_work_dir(node, vm_name):
    node.run({
        'command': ["rm -rf  " + CI_RESOURCE_PATH + vm_name],
        'waitstr': '#'
    })
