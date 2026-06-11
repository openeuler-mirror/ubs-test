import os
from libs.ubturbo.common.xml_tool import (
    create_node,
    find_nodes_list,
    add_child_node,
    read_xml,
    write_xml,
)
from libs.ubturbo.common.file_transport import dump_text
from libs.utils.logger_compat import Log
logger = Log.getLogger("AT_Common")


def ub_test_init(self, node):
    # cd /home/ub_native/ub
    target_path = "/home/ub_native/ub/ub_test_dep"
    node.run({'command': ["cd {}".format(target_path)], 'waitstr': '#'})

    # 执行virsh list --all命令
    show_ub_vm_res = node.run({'command': ["virsh list --all"], 'waitstr': '#'})

    # 查看ub_vm是否已经创建
    if 'ub_vm' in show_ub_vm_res['stdout']:
        logger.info("ub_vm exists")
        is_destroy_res = node.run({'command': ["virsh destroy ub_vm"], 'waitstr': '#'})
        if is_destroy_res['rc'] != 0:
            # 执行virsh list --all命令
            show_ub_vm_res_again = node.run({'command': ["virsh list --all"], 'waitstr': '#'})
            if 'ub_vm' in show_ub_vm_res_again['stdout']:
                is_destroy_res_again = node.run({'command': ["virsh destroy ub_vm"], 'waitstr': '#'})
                self.assertEqual(0, is_destroy_res_again['rc'], msg='销毁虚机失败')
            logger.info('ub_vm销毁成功')
    else:
        logger.info('ub_vm未创建')

    # 执行install.sh脚本
    node.run({'command': ["sh install.sh"], 'waitstr': '#'})

    check_ub_test_xml(node)


def amend_ub_xml(self, node, lineno, originaltest, newtest, command, filename):
    if command == 'update':
        # 使用sed命令修改指定行的内容
        node.run({'command': ["sed -i '{}s/{}/{}/' {}".format(lineno, originaltest, newtest, filename)], 'waitstr': '#'})
    elif command == 'delete':
        # 使用sed命令删除指定行
        node.run({'command': ["sed -i '{}d' {}".format(lineno, filename)], 'waitstr': '#'})
    elif command == 'insert':
        # 使用sed命令在指定行插入内容
        node.run({'command': ["sed -i '{}i {}' {}".format(lineno, newtest, filename)], 'waitstr': '#'})
    else:
        logger.error('Invalid command')
    logger.info('成功修改文件')


def fail_ub_vm(self, node, xml_file):
    start_vm = node.run({'command': ["virsh create {}".format(xml_file)], 'waitstr': '#'})
    self.assertEqual(1, start_vm['rc'], msg='错误配置但启动成功，非正常场景！')
    logger.info('错误配置且启动失败，正常场景')


def success_ub_vm(self, node, xml_file):
    start_vm = node.run({'command': ["virsh create {}".format(xml_file)], 'waitstr': '#'})
    self.assertEqual(0, start_vm['rc'], msg='正确配置但启动失败，非正常场景！')
    logger.info('正确配置且启动成功，正常场景')


def check_ub_test_xml(node):
    ls_res = node.run({'command': ["ls"], 'waitstr': '#'})
    # 检查是否有ub_test.xml文件，如果有则删除
    if 'ub_test.xml' in ls_res['stdout']:
        node.run({'command': ["rm -rf ub_test.xml"], 'waitstr': '#'})
        logger.info('成功删除ub_test.xml文件')
    else:
        logger.info('ub_test.xml不存在')

    # 检查是否有ub4D_test.xml文件，如果有则删除
    if 'ub4D_test.xml' in ls_res['stdout']:
        node.run({'command': ["rm -rf ub4D_test.xml"], 'waitstr': '#'})
        logger.info('成功删除ub4D_test.xml文件')
    else:
        logger.info('ub4D_test.xml不存在')

    # 检查是否有ub_init_test.xml文件，如果有则删除
    if 'ub_init_test.xml' in ls_res['stdout']:
        node.run({'command': ["rm -rf ub_init_test.xml"], 'waitstr': '#'})
        logger.info('成功删除ub_init_test.xml文件')
    else:
        logger.info('ub_init_test.xml不存在')


def backup_ub_xml(node):
    # 备份ub.xml文件
    node.run({'command': ["cp ub.xml ub_test.xml"], 'waitstr': '#'})
    # 备份ub4D.xml
    node.run({'command': ["cp ub4D.xml ub4D_test.xml"], 'waitstr': '#'})
    logger.info('成功备份')
    # 备份ub_init.xml
    node.run({'command': ["cp ub_init.xml ub_init_test.xml"], 'waitstr': '#'})
    logger.info('成功备份')


def create_ports_nodes(port_list=None):
    if port_list is None:
        ports = create_node("ports", {"num": "10"})
        return ports

    ports = create_node("ports", {"num": f"{len(port_list)}"})
    for index, teid, tport in port_list:
        ports.append(create_node("port", {"index": f"{index}", "teid": f"{teid}", "tport": f"{tport}"}))
    return ports


def add_UBController(tree, index, ports_list=None, address=None):
    # 创建UBController节点
    UBctler = create_node("controller", {"type": "ub", "index": f"{index}", "model": "ubc"})

    # 创建其他子节点并加入UBController节点
    if address is None:
        eid = f"0x{index}"
        guid = f"111111-8-0-1111-0000-{122+index:0{10}d}"
    else:
        eid = address['eid']
        guid = address['guid']

    ports = create_ports_nodes(ports_list)
    UBctler.append(ports)
    UBctler.append(create_node("alias", {"name": "ubc.0"}))
    UBctler.append(create_node("address", {"type": "ub", "eid": f"{eid}", "guid": f"{guid}"}))

    # 将UBController节点加入父节点devices
    devices = find_nodes_list(tree, "devices")
    add_child_node(devices, UBctler)


def add_UBHostdev(tree, index, ports_list=None, address=None):
    # 创建UBHostdev节点
    UBHostdev = create_node("hostdev", {"mode": "subsystem", "type": "ub", "managed": "yes"})

    # 创建其他子节点并加入UBHostdev节点
    source = create_node("source", {})
    source.append(create_node("address", {"guid": "00e0fc-2-0-a001-0008-0000000000"}))
    ports = create_ports_nodes(ports_list)
    if address is None:
        eid = f"0x{index}"
        guid = f"00e0fc-2-0-a001-0008-{index:0{10}d}"
    else:
        eid = address['eid']
        guid = address['guid']

    UBHostdev.append(create_node("driver", {"name": "vfio"}))
    UBHostdev.append(source)
    UBHostdev.append(ports)
    UBHostdev.append(create_node("alias", {"name": "ubc.0"}))
    UBHostdev.append(create_node("address", {"type": "ub", "eid": f"{eid}", "guid": f"{guid}"}))

    # 将UBHostdev节点加入父节点devices
    devices = find_nodes_list(tree, "devices")
    add_child_node(devices, UBHostdev)


def generate_and_get_xml_init(path):
    file_path = f"{path}/ub_init.xml"
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(xml_init)
    tree = read_xml(file_path)
    return tree


def apply_change_and_update_to_server(node, tree, path):
    file_path = f"{path}/ub_init_test.xml"
    write_xml(tree, file_path)
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        dump_text(node, content, "ub_init_test.xml")
        logger.info(content)
    os.remove(f"{path}/ub_init_test.xml")
    os.remove(f"{path}/ub_init.xml")


xml_init = '''
<domain type='kvm'
  xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>
  <name>ub_vm</name>
  <memory unit='GiB'>4</memory>
  <currentMemory unit='GiB'>4</currentMemory>
  <vcpu placement='static'>2</vcpu>
  <resource>
    <partition>/machine</partition>
  </resource>
  <os>
    <type arch='aarch64' machine='virt-6.2'>hvm</type>
    <kernel>/home/ub/Image_self_0920</kernel>
    <initrd>/home/ub/minifs_full_self_0920.cpio.gz</initrd>
    <loader type="pflash">/home/ub/QEMU_EFI_NOLOG_64M.fd</loader>
    <cmdline>acpi=on</cmdline>
  </os>
  <features>
    <gic version='3'/>
    <iommufd state='on'/>
    <acpi/>
  </features>
  <cpu mode='host-passthrough' check='none'>
  </cpu>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-stub</emulator>
    <controller type='pci' index='0' model='pcie-root'>
      <alias name='abc.999'/>
    </controller>

    <controller type='usb' index='0' model='nec-xhci'>
      <alias name='usb'/>
    </controller>
    <input type='tablet' bus='usb'>
      <alias name='input0'/>
      <address type='usb' bus='0' port='1'/>
    </input>
    <input type='keyboard' bus='usb'>
      <alias name='input1'/>
      <address type='usb' bus='0' port='2'/>
    </input>
    <serial type='pty'>
      <source path='/dev/pts/4'/>
      <target type='system-serial' port='0'>
        <model name='pl011'/>
      </target>
      <alias name='serial0'/>
    </serial>
    <console type='pty' tty='/dev/pts/4'>
      <source path='/dev/pts/4'/>
      <target type='serial' port='0'/>
      <alias name='serial0'/>
    </console>

    <video>
      <model type='virtio' heads='1' primary='yes'/>
      <alias name='video0'/>
    </video>

    <interface type='bridge'>
      <mac address='52:54:00:12:34:56'/> <!-- 虚拟机的MAC地址，需要是唯一的 -->
      <model type='virtio'/> <!-- 网络模型，virtio通常提供更好的性能 -->
      <source bridge='virbr0'/> <!-- 指定桥接的物理网卡，确保br0在宿主机上存在且已启用 -->
    </interface>

  </devices>
</domain>
'''