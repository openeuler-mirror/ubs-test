from uuid import uuid4
from typing import List

from poc_tools.common.constant import MemConvertEnum
from poc_tools.common.xml_tag import Uuid, Name, Memory, Page, HugePages, MemoryBacking, MemNode, NumaTune, Vcpu, \
    Type, Loader, Boot, OS, Acpi, Gic, Features, Topology, Cell, Numa, Cpu, Clock, OnPowerOff, OnReboot, OnCrash, \
    ControllerAlias, ControllerAddress, Controller, Emulator, Driver, DiskSource, DiskTarget, DiskAddress, Disk, \
    Console, ChannelSource, ChannelTarget, Channel, Stats, MemBalloonAlias, MemBalloonAddress, MemBalloon, Devices, \
    Domain
from poc_tools.common.utils import send_pipe_scripts
from poc_tools.common.log import LOG
from poc_tools.common.params import GenerateXmlParams, MemInfo

PAGE_SIZE = "2048"


async def get_thread_per_core():
    return await send_pipe_scripts([["lscpu"], ["grep", "Thread(s) per core"], ["awk", "{print $4}"]])


async def get_cpu_core_num():
    return await send_pipe_scripts([["lscpu"], ["grep", "Core(s) per socket"], ["awk", "{print $4}"]])


async def get_node_cpu_info():
    return await send_pipe_scripts([["lscpu"], ["grep", "NUMA node0 CPU(s)"], ["awk", "{print $4}"]])


async def generate_mem_backing_xml():
    page = Page(size=PAGE_SIZE, nodeset="0", unit="KiB")
    huge_pages = HugePages(page=page)
    memory_backing = MemoryBacking(huge_pages=huge_pages)
    return memory_backing


async def generate_numa_tune_xml(numa_info: List[MemInfo]):
    new_proportion_list = []
    for numa in numa_info:
        new_proportion_list.append(f"{numa.size}-node{numa.numa_id}")
    mem_node = MemNode(cell_id="0", mode="preferred", proportion=":".join(new_proportion_list))
    numa_tune = NumaTune(mem_node=mem_node)
    return numa_tune


async def generate_os_xml():
    os_type = Type(arch="aarch64", machine="virt", value="hvm")
    os_loader = Loader(readonly="yes", type="pflash", value="/usr/share/edk2/aarch64/QEMU_EFI-pflash.raw")
    os_boot = Boot(dev="hd")
    os_in_xml = OS(type=os_type, loader=os_loader, boot=os_boot)
    return os_in_xml


async def generate_features_xml():
    acpi = Acpi()
    gic = Gic(value="3")
    features = Features(acpi=acpi, gic=gic)
    return features


async def generate_cpu_xml(cpu_core_num: str, thread_per_core: str, node_cpu_info: str, vm_size: int):
    topology = Topology(sockets="1", cores=cpu_core_num, threads=thread_per_core)
    cell = Cell(id="0", cpus=node_cpu_info, memory=str(vm_size * MemConvertEnum.GB_TO_KB), mem_access="shared")
    numa = Numa(cell=cell)
    cpu = Cpu(mode="host-passthrough", match="exact", topology=topology, numa=numa)
    return cpu


async def generate_disk_xml(image_full_path: str):
    controller_alias = ControllerAlias(name="scsi0")
    controller_address = ControllerAddress(type="pci", domain="0x0000", bus="0x00", slot="0x04", function="0x0")
    controller = Controller(type="scsi", index="0", model="virtio-scsi", alias=controller_alias,
                            address=controller_address)

    emulator = Emulator(value="/usr/bin/qemu-kvm")

    driver = Driver(name="qemu", type="qcow2", cache="none", io="native")
    disk_source = DiskSource(file=image_full_path)
    disk_target = DiskTarget(dev="sda", bus="scsi")
    disk_address = DiskAddress(type="drive", controller="0", bus="0", target="0", unit="0")
    disk = Disk(type="file", device="disk", driver=driver, source=disk_source, target=disk_target, address=disk_address)

    console = Console(type="pty")

    channel_source = ChannelSource(mode="bind")
    channel_target = ChannelTarget(type="virtio", name="org.qemu.guest_agent.0")
    channel = Channel(type="unix", source=channel_source, target=channel_target)

    stats = Stats(period="10")
    mem_balloon_alias = MemBalloonAlias(name="balloon0")
    mem_balloon_address = MemBalloonAddress(type="pci", domain="0x0000", bus="0x04", slot="0x00", function="0x0")
    mem_balloon = MemBalloon(model="virtio", free_page_reporting="off", stats=stats, alias=mem_balloon_alias,
                             address=mem_balloon_address)

    devices = Devices(controller=controller, emulator=emulator, disk=disk, console=console, channel=channel,
                      mem_balloon=mem_balloon)
    return devices


async def generate_xml(xml_params: GenerateXmlParams):
    vm_name = xml_params.vm_name
    vm_size = xml_params.vm_size
    numa_info = xml_params.numa_infos
    image_full_path = xml_params.image_full_path
    uuid = str(uuid4())
    LOG.info(f"Generate vm random uuid: {uuid}.")
    vm_uuid_item = Uuid(value=uuid)
    name = Name(value=vm_name)
    memory = Memory(value=str(vm_size * MemConvertEnum.GB_TO_KB))
    memory_backing = await generate_mem_backing_xml()
    numa_tune = await generate_numa_tune_xml(numa_info)

    cpu_core_num = await get_cpu_core_num()
    thread_per_core = await get_thread_per_core()
    vcpu_core_num = str(int(cpu_core_num) * int(thread_per_core))
    node_cpu_info = await get_node_cpu_info()

    vcpu = Vcpu(value=vcpu_core_num)
    os_in_xml = await generate_os_xml()
    features = await generate_features_xml()
    cpu = await generate_cpu_xml(cpu_core_num, thread_per_core, node_cpu_info, vm_size)
    clock = Clock(offset="utc")
    on_power_off = OnPowerOff(value="destroy")
    on_reboot = OnReboot(value="restart")
    on_crash = OnCrash(value="restart")
    devices = await generate_disk_xml(image_full_path)

    domain = Domain(
        domain_type="kvm",
        uuid=vm_uuid_item,
        name=name,
        memory=memory,
        memory_backing=memory_backing,
        numa_tune=numa_tune,
        vcpu=vcpu,
        os=os_in_xml,
        features=features,
        cpu=cpu,
        clock=clock,
        on_power_off=on_power_off,
        on_reboot=on_reboot,
        on_crash=on_crash,
        devices=devices
    )
    return uuid, domain


async def write_to_xml_file(xml_file_path: str, domain: Domain):
    xml_content = domain.to_xml()
    with open(xml_file_path, "w") as f:
        f.write(xml_content)
    LOG.info(f"Xml file generate successfully.")
