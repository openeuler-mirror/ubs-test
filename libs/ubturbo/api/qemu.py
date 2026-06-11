import time
import uuid
from xml.etree.ElementTree import tostring, XML

from libs.ubturbo.common import basic, file_transport, env
from libs.ubturbo.common.file_transport import dump_text
from libs.ubturbo.common.string_utils import STR_ENTER
from libs.ubturbo.model import libvirt as lv_model
import libs.ubturbo.api.libvirt as lv_api
import libs.ubturbo.api.integration as integration

DEFAULT_IMG_PATH = '/home/vm/img/openEuler-22.03-LTS-SP1-aarch64.qcow2'


def set_max_downtime(node, vm, time: int = 30):
    basic.run(node, f'virsh migrate-setmaxdowntime {vm.vm_name} {time}')


def get_migrate_down_time(node, vm):
    """
    获取迁移下线时间
    """
    keyword = "qmp hcom resource initialization and connection"
    log_path = "/var/log/libvirt/qemu"
    time = basic.run(node, f'grep -A 5 "{keyword}" "{log_path}/{vm.vm_name}.log"'
                           f' | tail -7 | grep "qmp downtime" | grep -oP "\d+"', timeout=40).stdout
    return int(time)


def batch_create_vm(node, init_xml, work_path, vm_start_index: int = 1,
                    vm_end_index: int = 1):
    """
    批量创建虚机
    """
    vms = []
    for i in range(vm_start_index, vm_end_index + 1):
        img_path = f'{work_path}img_{i}.qcow2'
        fp_local = f'{file_transport.THIS_PROJECT_PATH}/resource/vm_xml_template/{init_xml}.xml'
        content = open(fp_local, encoding='utf-8').read()
        tree = XML(content)

        # 获取xml文件中numa_index对应的cpuset范围
        begin_index, end_index = integration.get_cpuset_range_at_numa(0, node)

        # 分别更改vcpu的cpuset号
        for offset in range(len(tree.findall(".//vcpupin"))):
            integration.change_cpuset_at_vcpu(offset, end_index - offset, tree)

        # 更改emulatorpin里的cpuset范围
        integration.change_emulatorpin_cpuset(f'{begin_index}-{end_index}', tree)

        # 更新 <name> 标签
        generated_uuid = uuid.uuid4()
        # 获取最后 12 个字符
        last_12_chars = str(generated_uuid).replace("-", "")[-12:]
        lv_api.update_vm_config_text(tree, 'name', init_xml + last_12_chars)
        # 更新 <source file="..."> 标签
        lv_api.update_vm_config_attribute(tree, 'source', 'file', img_path)
        # 更新 <mac address="..."> 标签
        lv_api.update_vm_config_attribute(tree, 'mac', 'address', f"52:54:00:64:23:{22 + i}")
        xml_path = work_path + init_xml + last_12_chars + '.xml'
        file_transport.dump_text(node, tostring(tree).decode('utf8'), xml_path)
        vms.append(lv_model.VirtualMachine(node=node, fn=xml_path, init_login=False))
    if len(vms) == 1:
        return vms[0]
    else:
        return vms


def migrate_vm_device(node, vm, parallel_flag: bool = False):
    """
    虚机设备迁移
    """
    migrate_cmd = (f'virsh qemu-monitor-command {vm.vm_name} \'{{"execute":"migrate-set-capabilities",'
                   f'"arguments":{{"capabilities":[{{"capability":"devices-parallel","state":{parallel_flag}}}]}}}}\'')
    basic.run(node, migrate_cmd, timeout=40)


def build_migrate_cmd(to_ip, vm, parallel_connections: int = 2, onecopy_flag: bool = False,
                      tcp_flag: bool = False, cold_flag: bool = False, daemon_flag: bool = False,
                      env_flag: str = env.HCCS) -> str:
    """
    装配迁移命令
    """
    migrate_way = 'tcp' if tcp_flag else 'hcom'
    migrate_cmd = (
        f"virsh migrate --p2p --live --unsafe --migrateuri {migrate_way}://{to_ip} {vm.vm_name} "
        f"--listen-address {to_ip} qemu+tcp://{to_ip}/system "
        f"--verbose --parallel --parallel-connections {parallel_connections}")

    if not tcp_flag:
        migrate_cmd += " --rdma-pin-all"
        if env_flag == env.HCCS:
            migrate_cmd += " --enable-hccs"
        if onecopy_flag:
            migrate_cmd += " --onecopy"
        if cold_flag:
            migrate_cmd += " –-enable-cold"
    if daemon_flag:
        migrate_cmd = "nohup " + migrate_cmd + " &"
    return migrate_cmd


def migrate_vm(from_node, to_ip, vm, check_exist: bool = True, parallel_connections: int = 2,
               onecopy_flag: bool = False, tcp_flag: bool = False,
               cold_flag: bool = False, daemon_flag: bool = False, env_flag: str = env.HCCS):
    """
    迁移虚机
    :param check_exist: 迁移完成后，是否检测虚机迁移成功
    """
    if isinstance(vm, lv_model.VirtualMachine):
        file_path = "/var/log/libvirt/qemu"
        migrate_cmd = build_migrate_cmd(to_ip, vm=vm, parallel_connections=parallel_connections,
                                        onecopy_flag=onecopy_flag, tcp_flag=tcp_flag,
                                        cold_flag=cold_flag, env_flag=env_flag, daemon_flag=daemon_flag)
        timeout = {
            env.UB_simulation: 60000
        }.get(env_flag, 35)
        result = basic.run(from_node, migrate_cmd, timeout=timeout)
        time.sleep({
                       env.UB_simulation: 240
                   }.get(env_flag, 10))
        log_cmd = f'tail -100 "{file_path}/{vm.vm_name}.log"'
        basic.run(from_node, log_cmd, timeout=timeout)
        if result.rc != 0:
            raise Exception(result.stderr)
        if check_exist:
            check_vm(from_node, vm, False)
    else:
        for v in vm:
            migrate_vm(from_node, to_ip, v, check_exist, parallel_connections, onecopy_flag, tcp_flag, cold_flag,
                       daemon_flag,
                       env_flag)


def check_vm(node, vm, is_exist):
    """
    虚机迁移后检测虚机是否存在
    :param is_exist: 迁移完成后，理论上(预期)虚机是否存在
    """
    names = lv_api.get_all_vm_names(node)
    is_found = vm.vm_name in names
    if not is_exist and is_found:
        raise Exception(f'{node.getIpAddress()}: 虚拟机 {vm.vm_name} 存在')
    elif is_exist and not is_found:
        raise Exception(f'{node.getIpAddress()}: 虚拟机 {vm.vm_name} 不存在')


def get_cmd_exec_time(node, cmd, file_path):
    dump_text(node=node, text=GET_CMD_EXEC_TIME_SHELL.format(cmd), fn=file_path)
    time_data = basic.run(node, f"chmod +x {file_path}; bash {file_path}").stdout.split(STR_ENTER)[-2]
    return int(time_data.split(' ')[1])


GET_CMD_EXEC_TIME_SHELL = """
# 设置目标迁移命令
CMD="{0}"

echo "Starting migration..."
start_time=$(date +%s%3N)

# 执行命令
eval $CMD

end_time=$(date +%s%3N)
elapsed=$((end_time - start_time))

if [ $? -eq 0 ]; then
  echo "命令执行成功"
else
  echo "命令执行失败"
fi

echo "执行时间(ms): $elapsed"
"""
